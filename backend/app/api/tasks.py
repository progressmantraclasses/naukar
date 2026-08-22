"""
Tasks API — REST endpoints for creating and querying tasks.
"""
import uuid
import asyncio
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.events import event_bus, Event, EventType
from app.db import models as db_models
from app.orchestrator.executive import ExecutiveOrchestrator
import structlog

log = structlog.get_logger()
router = APIRouter(prefix="/api/tasks", tags=["tasks"])


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------
class CreateTaskRequest(BaseModel):
    user_input: str
    max_budget_usd: Optional[float] = 5.0


class TaskResponse(BaseModel):
    id: str
    user_input: str
    status: str
    title: Optional[str]
    task_type: Optional[str]
    complexity_score: Optional[float]
    final_result: Optional[str]
    quality_score: Optional[float]
    created_at: str
    completed_at: Optional[str]


# ---------------------------------------------------------------------------
# Background task runner
# ---------------------------------------------------------------------------
async def _run_orchestration(task_id: str, user_input: str):
    """Run the autonomous loop in the background."""
    from app.core.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        orchestrator = ExecutiveOrchestrator(db)
        try:
            await orchestrator.run(task_id, user_input)
        except Exception as e:
            log.exception("orchestration_background_error", task_id=task_id, error=str(e))


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@router.post("", response_model=TaskResponse)
async def create_task(
    body: CreateTaskRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new task and immediately start autonomous execution.
    The task runs in the background; use WebSocket for live updates.
    """
    task_id = str(uuid.uuid4())

    # Persist task
    task = db_models.Task(
        id=task_id,
        user_input=body.user_input,
        max_budget_usd=body.max_budget_usd or 5.0,
        status="pending",
        created_at=datetime.now(timezone.utc),
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)

    # Emit created event
    await event_bus.publish(Event(
        event_type=EventType.TASK_CREATED,
        task_id=task_id,
        payload={"user_input": body.user_input, "task_id": task_id},
    ))

    # Start autonomous loop in background
    background_tasks.add_task(_run_orchestration, task_id, body.user_input)

    log.info("task_created", task_id=task_id)
    return _task_to_response(task)


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str, db: AsyncSession = Depends(get_db)):
    """Get task status and result."""
    task = await db.get(db_models.Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return _task_to_response(task)


@router.get("/{task_id}/employees")
async def get_task_employees(task_id: str, db: AsyncSession = Depends(get_db)):
    """Get all employees created for a task."""
    result = await db.execute(
        select(db_models.Employee).where(db_models.Employee.task_id == task_id)
    )
    employees = result.scalars().all()
    return [
        {
            "id": e.id,
            "role": e.role,
            "objective": e.objective,
            "skills": e.skills,
            "tools": e.tools,
            "status": e.status,
            "current_task": e.current_task,
            "current_model": e.current_model,
            "confidence": e.confidence,
            "hierarchy_level": e.hierarchy_level,
            "manager_id": e.manager_id,
        }
        for e in employees
    ]


@router.get("/{task_id}/steps")
async def get_task_steps(task_id: str, db: AsyncSession = Depends(get_db)):
    """Get all task steps (DAG nodes) for a task."""
    result = await db.execute(
        select(db_models.TaskStep).where(db_models.TaskStep.task_id == task_id)
        .order_by(db_models.TaskStep.step_index)
    )
    steps = result.scalars().all()
    return [
        {
            "id": s.id,
            "step_index": s.step_index,
            "objective": s.objective,
            "status": s.status,
            "assigned_employee_id": s.assigned_employee_id,
            "model_used": s.model_used,
            "quality_threshold": s.quality_threshold,
            "confidence": s.confidence,
            "retry_count": s.retry_count,
            "result_preview": s.result[:200] if s.result else None,
        }
        for s in steps
    ]


@router.get("")
async def list_tasks(db: AsyncSession = Depends(get_db)):
    """List all tasks."""
    result = await db.execute(
        select(db_models.Task).order_by(db_models.Task.created_at.desc()).limit(50)
    )
    tasks = result.scalars().all()
    return [_task_to_response(t) for t in tasks]


def _task_to_response(task: db_models.Task) -> dict:
    return {
        "id": task.id,
        "user_input": task.user_input,
        "status": task.status,
        "title": task.title,
        "task_type": task.task_type,
        "complexity_score": task.complexity_score,
        "final_result": task.final_result,
        "quality_score": task.quality_score,
        "created_at": task.created_at.isoformat() if task.created_at else "",
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
    }
