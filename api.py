import os
import operator
from typing import TypedDict, Annotated, Sequence
from dotenv import load_dotenv

# FastAPI Imports
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# LangChain / LangGraph Imports
from langchain_openai import AzureChatOpenAI
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langgraph.graph import StateGraph, END

# Azure Cosmos DB Import
from langchain_azure_cosmosdb import CosmosDBSaverSync

# Load environment variables
load_dotenv()

# --- 1. SETUP THE BRAIN (Azure OpenAI) ---
deployment_name = os.environ.get("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME", "gpt-4o")

llm = AzureChatOpenAI(
    azure_deployment=deployment_name,
    api_version=os.environ.get("AZURE_OPENAI_API_VERSION"),
    max_retries=2
)

# --- 2. SETUP THE GRAPH STATE & NODES ---
class CapExAgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    approval_status: str

def agent_logic(state: CapExAgentState):
    """The real LLM brain evaluating the conversation."""
    
    if state.get("approval_status") == "Approved":
        response = llm.invoke([
            SystemMessage(content="The manager has approved this purchase. Inform the user gracefully and ask for their shipping address.")
        ] + state["messages"])
        return {"messages": [response]}

    system_prompt = SystemMessage(content=(
        "You are an AI purchasing assistant. Help the user buy equipment. "
        "CRITICAL RULE: If the user requests an item that costs more than $50,000, "
        "you must say 'This exceeds the auto-approval limit. I am pausing this request for manager approval.' "
        "If it is under $50,000, just say 'Request approved and processed!'"
    ))
    
    response = llm.invoke([system_prompt] + state["messages"])
    
    if "pausing this request" in response.content.lower():
        return {"messages": [response], "approval_status": "Pending"}
    
    return {"messages": [response], "approval_status": "Not_Needed"}

def process_approval(state: CapExAgentState):
    """Halts execution and acts as our anchoring state waiting room."""
    return state

# Build the Graph
workflow = StateGraph(CapExAgentState)
workflow.add_node("agent_logic", agent_logic)
workflow.add_node("process_approval", process_approval)
workflow.set_entry_point("agent_logic")

def route_next(state: CapExAgentState):
    if state.get("approval_status") == "Pending":
        return "process_approval"
    return END

workflow.add_conditional_edges("agent_logic", route_next)
workflow.add_edge("process_approval", "agent_logic")

# --- 3. SETUP FASTAPI ---
app = FastAPI(title="CapEx Human-in-the-Loop API")

class ChatRequest(BaseModel):
    thread_id: str
    message: str

class ApprovalRequest(BaseModel):
    thread_id: str

@app.post("/chat")
def chat_with_agent(request: ChatRequest):
    """Send a message to the AI."""
    cosmos_endpoint = os.environ.get("COSMOS_DB_ENDPOINT")
    cosmos_key = os.environ.get("COSMOS_DB_KEY")
    
    if not cosmos_endpoint or not cosmos_key:
        raise HTTPException(status_code=500, detail="Missing Cosmos DB credentials.")
    
    with CosmosDBSaverSync.from_conn_info(
        endpoint=cosmos_endpoint, 
        key=cosmos_key, 
        database_name="AgentStateDB", 
        container_name="ActiveSessions"
    ) as checkpointer:
        
        agent = workflow.compile(checkpointer=checkpointer)
        config = {"configurable": {"thread_id": request.thread_id}}
        
        user_msg = {"messages": [HumanMessage(content=request.message)]}
        
        for event in agent.stream(user_msg, config):
            pass 
            
        final_state = agent.get_state(config).values
        
        if not final_state or "messages" not in final_state:
            return {"ai_response": "Graph execution paused or ended unexpectedly.", "current_status": "Unknown"}
            
        ai_response = final_state["messages"][-1].content
        status = final_state.get("approval_status", "Unknown")
        
        return {"ai_response": ai_response, "current_status": status}

@app.post("/approve")
def approve_request(request: ApprovalRequest):
    """Manager webhook to approve a paused request."""
    cosmos_endpoint = os.environ.get("COSMOS_DB_ENDPOINT")
    cosmos_key = os.environ.get("COSMOS_DB_KEY")
    
    if not cosmos_endpoint or not cosmos_key:
        raise HTTPException(status_code=500, detail="Missing Cosmos DB credentials.")
    
    with CosmosDBSaverSync.from_conn_info(
        endpoint=cosmos_endpoint, 
        key=cosmos_key, 
        database_name="AgentStateDB", 
        container_name="ActiveSessions"
    ) as checkpointer:
        
        agent = workflow.compile(checkpointer=checkpointer)
        config = {"configurable": {"thread_id": request.thread_id}}
        
        agent.update_state(config, {"approval_status": "Approved"})
        
        for event in agent.stream(None, config):
            pass
            
        final_state = agent.get_state(config).values
        
        final_response = ""
        if final_state and "messages" in final_state:
            final_response = final_state["messages"][-1].content
                
        return {"status": "Successfully Hydrated & Approved", "ai_follow_up": final_response}