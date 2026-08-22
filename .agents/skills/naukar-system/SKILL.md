---
name: naukar-system
description: >
  Complete reference for the Naukar Autonomous AI Workforce Platform.
  Use this skill to understand the architecture, run the system locally,
  add new LLM providers, tools, or extend the workforce planning logic.
---

# Naukar — Autonomous AI Workforce Platform

## What is Naukar?

Naukar is an Autonomous AI Workforce Platform where the user provides only a task,
and the system autonomously designs, staffs, executes, reviews, and delivers results.

```
User: "Create a competitor analysis for my SaaS"
         ↓
   Naukar decides:
   - Task type & complexity
   - What skills are needed
   - How many workers to hire
   - Which workers to create
   - How they interact
   - Which models to use
   - Whether results are good enough
         ↓
   User receives final result
```

---

## Project Structure

```
c:\Users\HP\Desktop\Naukar\
├── docker-compose.yml          # PostgreSQL (pgvector) + Redis
├── backend/
│   ├── main.py                 # FastAPI entry point
│   ├── requirements.txt
│   ├── .env                    # Secrets (copy from .env.example)
│   └── app/
│       ├── core/
│       │   ├── config.py       # Pydantic settings
│       │   ├── database.py     # PG + Neo4j connections
│       │   └── events.py       # Event bus (Redis + in-process WS)
│       ├── db/models.py        # SQLAlchemy ORM
│       ├── llm/
│       │   ├── provider.py     # Abstract LLMProvider
│       │   ├── groq_provider.py
│       │   └── registry.py
│       ├── orchestrator/
│       │   ├── executive.py    # ExecutiveOrchestrator (main loop)
│       │   └── task_analyzer.py
│       ├── workforce/
│       │   ├── planner.py      # WorkforcePlanner
│       │   └── factory.py      # EmployeeFactory
│       ├── tasks/
│       │   ├── models.py       # Pydantic orchestration models
│       │   └── decomposer.py   # TaskDecomposer (DAG)
│       ├── router/
│       │   └── model_router.py # DynamicModelRouter
│       ├── employees/
│       │   └── executor.py     # EmployeeExecutor
│       ├── evaluation/
│       │   └── quality.py      # QualityController
│       └── api/
│           ├── tasks.py        # REST endpoints
│           └── ws.py           # WebSocket endpoint
└── frontend/
    ├── electron/main.ts        # Electron main process
    ├── src/
    │   ├── store/taskStore.ts  # Zustand state
    │   ├── components/
    │   │   ├── TaskInput.tsx
    │   │   ├── ExecutionView.tsx
    │   │   ├── EmployeeCard.tsx
    │   │   └── ResultDisplay.tsx
    │   ├── App.tsx
    │   └── index.css           # Full design system
    └── package.json
```

---

## Running Locally

### Step 1: Infrastructure (Docker)
```powershell
cd c:\Users\HP\Desktop\Naukar
docker compose up -d
```
This starts PostgreSQL (with pgvector) on port 5432 and Redis on port 6379.

### Step 2: Backend
```powershell
cd backend
# Set up virtual environment
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env: add GROQ_API_KEY, NEO4J_URI, NEO4J_PASSWORD

# Start server
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Step 3: Frontend
```powershell
cd frontend
npm install
npm run dev        # Starts Vite (port 5173) + Electron
```

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `GROQ_API_KEY` | Groq API key (required) |
| `NEO4J_URI` | AuraDB URI: `neo4j+s://xxx.databases.neo4j.io` |
| `NEO4J_USER` | Neo4j username (usually `neo4j`) |
| `NEO4J_PASSWORD` | Neo4j password |
| `DATABASE_URL` | PostgreSQL async URL (auto-set for Docker) |
| `REDIS_URL` | Redis URL (auto-set for Docker) |

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/tasks` | Create task, start autonomous execution |
| `GET` | `/api/tasks/{id}` | Get task status + result |
| `GET` | `/api/tasks/{id}/employees` | List all employees for task |
| `GET` | `/api/tasks/{id}/steps` | List all DAG steps for task |
| `GET` | `/api/tasks` | List all tasks |
| `WS` | `/ws/{task_id}` | Live event stream for task |
| `WS` | `/ws` | Global event stream |

---

## Key Architectural Decisions

### Minimum Workforce Principle
The system creates the SMALLEST team that can reliably complete the task.
- Simple task (complexity < 0.3): 1-2 employees
- Medium (0.3-0.6): 2-4 employees  
- Complex (> 0.6): 4-10 employees with hierarchy

### Model Cascade
Cheapest model first, escalate on quality failure:
```
groq/compound-mini → groq/compound → (retry with compound)
```
Never default to expensive models; use them as fallback only.

### Event-Driven Architecture
Every action emits an event. The frontend subscribes via WebSocket.
Events flow: orchestrator → Redis Pub/Sub → WebSocket → Electron UI.

### Quality Gates
Every step result is evaluated by an independent QC call (different from the worker).
If quality fails, the worker retries with the next model in the cascade.

---

## Adding a New LLM Provider

1. Create `backend/app/llm/your_provider.py`
2. Extend `LLMProvider` from `app/llm/provider.py`
3. Implement `generate()`, `stream()`, `estimate_cost()`
4. Register in `app/llm/registry.py`:
   ```python
   from app.llm.your_provider import YourProvider
   your = YourProvider()
   for model in your.available_models:
       self._providers[model] = your
   ```
5. Update `MODEL_CASCADE` in `app/router/model_router.py`

---

## Adding New Tools

1. Create `backend/app/tools/your_tool.py`
2. Employees reference tools by name string in their `tools` list
3. The executor can inject tool results into the LLM context
4. Tools are assigned by the WorkforcePlanner based on task analysis

---

## AuraDB Graph Schema

Nodes: `Task`, `Employee`, `TaskStep`, `Skill`, `Model`

Key relationships:
- `(:Employee)-[:REPORTS_TO]->(:Employee)` — hierarchy
- `(:TaskStep)-[:DEPENDS_ON]->(:TaskStep)` — DAG
- `(:TaskStep)-[:ASSIGNED_TO]->(:Employee)` — assignment
- `(:Employee)-[:USED_MODEL]->(:Model)` — model usage

---

## Phase 2 Roadmap

- [ ] Parallel step execution (asyncio.gather for independent steps)
- [ ] Real tool execution (web search via SerpAPI, browser via Playwright)
- [ ] RAG: document ingestion + pgvector similarity search
- [ ] Dynamic workforce adjustment during execution
- [ ] Model performance learning (update model_metrics table)
- [ ] Cost tracking per task
- [ ] Human approval gates for high-risk actions
- [ ] Task history & analytics dashboard
