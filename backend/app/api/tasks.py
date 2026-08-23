"""
Tasks API — REST endpoints for creating and querying tasks.
"""
import uuid
import asyncio
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.events import event_bus, Event, EventType
from app.core.redis_store import redis_store
from app.db import models as db_models
from app.orchestrator.executive import ExecutiveOrchestrator
from app.tools.deterministic import try_deterministic
from app.core.config import settings
from app.core.security import Identity, assert_owner, get_identity
from app.security.rate_limiter import task_rate_limit, api_rate_limit
import structlog

log = structlog.get_logger()
router = APIRouter(prefix="/api/tasks", tags=["tasks"])


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------
class CreateTaskRequest(BaseModel):
    user_input: str = Field(min_length=1, max_length=10_000)
    max_budget_usd: Optional[float] = Field(default=5.0, ge=0.0, le=100.0)
    # user_id is NOT accepted from client — always taken from JWT identity

    @field_validator("user_input")
    @classmethod
    def _strip_input(cls, v: str) -> str:
        return v.strip()


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
async def _run_orchestration(task_id: str, user_input: str, user_id: str):
    """Run the autonomous loop in the background."""
    from app.core.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        orchestrator = ExecutiveOrchestrator(db)
        try:
            await orchestrator.run(task_id, user_input, user_id=user_id)
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
    identity: Identity = Depends(get_identity),
    _rate: None = Depends(task_rate_limit),
):
    """
    Create a new task and immediately start autonomous execution.
    The task runs in the background; use WebSocket for live updates.
    """
    task_id = str(uuid.uuid4())
    user_id = identity.user_id  # always from JWT, never from request body

    # Persist task
    task = db_models.Task(
        id=task_id,
        user_input=body.user_input,
        user_id=user_id,
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
    deterministic_result = await try_deterministic(body.user_input)
    if deterministic_result is not None:
        task.status = "completed"
        task.title = "Deterministic calculation"
        task.final_result = deterministic_result
        task.quality_score = 1.0
        task.completed_at = datetime.now(timezone.utc)
        await db.commit()
        await event_bus.publish(Event(
            event_type=EventType.FINAL_RESULT_READY,
            task_id=task_id,
            payload={"result": deterministic_result, "quality_score": 1.0, "deterministic": True},
        ))
        return _task_to_response(task)
    try:
        await redis_store.set_json(
            f"naukar:task:{user_id}:{task_id}",
            {"task_id": task_id, "status": "pending", "user_id": user_id},
            86400,
        )
    except Exception as exc:
        log.warning("task_state_cache_write_failed", task_id=task_id, error=str(exc))

    # Use a durable worker when configured; retain local fallback for development.
    if settings.TASK_QUEUE_MODE.lower() == "celery":
        from app.core.task_queue import enqueue_orchestration
        enqueue_orchestration(task_id, body.user_input, user_id)
    else:
        background_tasks.add_task(_run_orchestration, task_id, body.user_input, user_id)

    log.info("task_created", task_id=task_id)
    return _task_to_response(task)


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str, db: AsyncSession = Depends(get_db), identity: Identity = Depends(get_identity)):
    """Get task status and result."""
    task = await db.get(db_models.Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    assert_owner(task.user_id, identity)
    return _task_to_response(task)


@router.get("/{task_id}/employees")
async def get_task_employees(task_id: str, db: AsyncSession = Depends(get_db), identity: Identity = Depends(get_identity)):
    """Get all employees created for a task."""
    task = await db.get(db_models.Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    assert_owner(task.user_id, identity)
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
async def get_task_steps(task_id: str, db: AsyncSession = Depends(get_db), identity: Identity = Depends(get_identity)):
    """Get all task steps (DAG nodes) for a task."""
    task = await db.get(db_models.Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    assert_owner(task.user_id, identity)
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
async def list_tasks(db: AsyncSession = Depends(get_db), identity: Identity = Depends(get_identity)):
    """List all tasks."""
    result = await db.execute(
        select(db_models.Task).where(db_models.Task.user_id == identity.user_id).order_by(db_models.Task.created_at.desc()).limit(50)
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


@router.get("/{task_id}/analytics")
async def get_task_analytics(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    identity: Identity = Depends(get_identity),
):
    """
    Get full token usage analytics for a task.
    Returns per-step token breakdown, cumulative costs, web search stats.
    """
    task = await db.get(db_models.Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    assert_owner(task.user_id, identity)

    from app.llm.token_tracker import token_tracker
    summary = token_tracker.get_summary(task_id)
    if summary is None:
        # Return empty summary if task not in memory (completed long ago)
        return {
            "task_id": task_id,
            "available": False,
            "message": "Analytics only available for tasks completed in the current server session.",
            "total_tokens": 0,
            "total_cost_usd": 0.0,
            "entries": [],
        }
    data = summary.to_dict()
    data["available"] = True
    return data

