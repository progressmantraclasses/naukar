# Naukar Agent Guide

This file documents how to work with the Naukar autonomous agents.

## What makes Naukar different

Naukar is **not** a fixed-agent system. It creates agents on demand based on what the task requires.

### The Orchestration Loop

```
User Task
    ↓
TaskIntelligenceEngine → structured analysis
    ↓
WorkforcePlanner → minimum viable team
    ↓
EmployeeFactory → instantiate employees
    ↓
TaskDecomposer → DAG of steps
    ↓
DynamicModelRouter → select cheapest capable model per step
    ↓
EmployeeExecutor → run step, extract confidence
    ↓
QualityController → independent evaluation
    ↓ (fail → retry with next cascade model)
AssembleFinalResult → synthesize all steps
    ↓
FinalQualityGate → final review
    ↓
DONE
```

## Key Files

| File | Purpose |
|------|---------|
| `backend/app/orchestrator/executive.py` | Main autonomous loop |
| `backend/app/orchestrator/task_analyzer.py` | LLM-based task analysis |
| `backend/app/workforce/planner.py` | LLM-based workforce design |
| `backend/app/workforce/factory.py` | Employee creation |
| `backend/app/tasks/decomposer.py` | Task → DAG |
| `backend/app/router/model_router.py` | Model selection |
| `backend/app/employees/executor.py` | Step execution |
| `backend/app/evaluation/quality.py` | QC evaluation |
| `backend/app/core/events.py` | Event bus |
| `frontend/src/store/taskStore.ts` | Frontend state |

## Running the system

```powershell
# Terminal 1: Infrastructure
cd c:\Users\HP\Desktop\Naukar
docker compose up -d

# Terminal 2: Backend
cd backend
.venv\Scripts\activate
uvicorn main:app --reload

# Terminal 3: Frontend  
cd frontend
npm run dev:vite    # Just the web UI (no Electron needed for testing)
```

## Testing with curl

```powershell
# Create a task
$body = '{"user_input": "Summarize the benefits of Python for data science"}'
Invoke-RestMethod -Method POST -Uri "http://localhost:8000/api/tasks" -Body $body -ContentType "application/json"

# Check status (use the id from above)
Invoke-RestMethod -Uri "http://localhost:8000/api/tasks/{TASK_ID}"
```
