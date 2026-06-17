# CapEx Human-in-the-Loop AI Agent on Azure Functions

An enterprise-grade, event-driven Capital Expenditure (CapEx) purchasing assistant built with **LangGraph**, **FastAPI**, **Azure OpenAI**, and persistent state checkpointing via **Azure Cosmos DB**. This entire stack is optimized for serverless execution using **Azure Functions (v2 Python ASGI worker)**.

[Image of LangGraph state machine with FastAPI endpoints and Cosmos DB persistence]

---

## 🔍 Project Overview & Problem Solved

In corporate finance, Capital Expenditure (CapEx) requests involve strict approval guardrails to keep spending aligned with corporate budgets. Traditional procurement systems are rigid, forcing users into tedious form filling and creating communication silos over email or chat tools.

This project solves this by introducing **Human-in-the-Loop (HITL) Conversational Automation**:
* **Conversational Procurement:** Employees interact naturally with an AI agent to specify equipment orders and delivery details.
* **Autonomous Guardrails:** The agent processes and auto-approves requests below a strict organizational limit ($50,000).
* **State Interruption (HITL):** If a transaction exceeds $50,000, the LangGraph engine automatically alters the status to `Pending`, halts execution, stores the exact session snapshot to Cosmos DB, and enters an idle "waiting room" until a human manager approves it via a webhook.

---

## 🏗️ Core Architecture & Component Integration

The application functions as a decoupled, reactive state machine:

1. **FastAPI Layer (`api.py`):** Exposes async endpoints (`/chat` and `/approve`) handling incoming interaction payloads.
2. **LangGraph Engine:** Orchestrates a cyclical state graph. If a transaction is flagged as `Pending`, the graph routes to an inactive waiting node rather than terminating at `END`. 
3. **Azure Cosmos DB (`CosmosDBSaverSync`):** Serves as the external memory backend. The entire conversational history and graph execution state are dehydrated into a document store under a unique `thread_id` when an interruption occurs, consuming zero compute resources while waiting.
4. **Azure Functions Bridge (`function_app.py`):** Wraps the FastAPI ASGI app into a serverless execution model, routing HTTP traffic dynamically and scaling down to zero when idle.

---

## 🛠️ Tech Stack & Key Libraries

| Component | Technology | Role |
| :--- | :--- | :--- |
| **Serverless Host** | Azure Functions (v2 Python) | Serverless host utilizing `AsgiFunctionApp` |
| **API Framework** | FastAPI + Pydantic | Endpoint routing and request validation |
| **Agent Orchestration**| LangGraph | State management, conditional routing, and graph loops |
| **LLM Brain** | Azure OpenAI (`gpt-4o` / `gpt-chat-latest`) | Intent parsing and responsive dialogue generation |
| **Persistence** | Azure Cosmos DB (NoSQL) | External transactional checkpoint saver for state hydration |

---

## 🚀 Setup & Local Installation

### 1. Prerequisites
Ensure you have the following installed locally:
* Python 3.10 or 3.11
* Azure Functions Core Tools

### 2. Clone and Install Dependencies
```bash
git clone [https://github.com/YOUR_USERNAME/CapEx-Human-in-the-Loop-agent-on-Azure-Functions.git](https://github.com/YOUR_USERNAME/CapEx-Human-in-the-Loop-agent-on-Azure-Functions.git)
cd CapEx-Human-in-the-Loop-agent-on-Azure-Functions

# Set up virtual environment
python -m venv venv
./venv/Scripts/activate  # On Windows

# Install required frameworks
pip install -r requirements.txt
