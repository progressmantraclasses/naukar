"""
SQLAlchemy ORM models for Naukar.
All entities stored in PostgreSQL.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from sqlalchemy import (
    String, Text, Float, Integer, Boolean, DateTime,
    ForeignKey, JSON, Index, Enum as SAEnum
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
from pgvector.sqlalchemy import Vector

from app.core.database import Base


def utcnow():
    return datetime.now(timezone.utc)


def new_uuid():
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Users (authentication)
# ---------------------------------------------------------------------------
class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(200), nullable=False)
    # workspace_id is derived from user id at registration time
    workspace_id: Mapped[str] = mapped_column(String(36), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False, default="user")  # user | admin
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_input: Mapped[str] = mapped_column(Text, nullable=False)
    user_id: Mapped[str] = mapped_column(String(200), nullable=False, default="anonymous", index=True)
    title: Mapped[Optional[str]] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(50), default="pending")  # pending|analyzing|planning|executing|reviewing|completed|failed

    # Analysis results
    task_type: Mapped[Optional[str]] = mapped_column(String(200))
    complexity_score: Mapped[Optional[float]] = mapped_column(Float)
    risk_score: Mapped[Optional[float]] = mapped_column(Float)
    reasoning_requirement: Mapped[Optional[float]] = mapped_column(Float)
    research_requirement: Mapped[Optional[float]] = mapped_column(Float)
    tool_requirement: Mapped[Optional[float]] = mapped_column(Float)
    accuracy_requirement: Mapped[Optional[float]] = mapped_column(Float)
    required_skills: Mapped[Optional[list]] = mapped_column(JSONB)
    required_tools: Mapped[Optional[list]] = mapped_column(JSONB)
    estimated_cost_usd: Mapped[Optional[float]] = mapped_column(Float)
    max_budget_usd: Mapped[float] = mapped_column(Float, default=5.0)
    actual_cost_usd: Mapped[float] = mapped_column(Float, default=0.0)

    # Result
    final_result: Mapped[Optional[str]] = mapped_column(Text)
    quality_score: Mapped[Optional[float]] = mapped_column(Float)
    error_message: Mapped[Optional[str]] = mapped_column(Text)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Relationships
    steps: Mapped[List["TaskStep"]] = relationship("TaskStep", back_populates="task", cascade="all, delete-orphan")
    employees: Mapped[List["Employee"]] = relationship("Employee", back_populates="task", cascade="all, delete-orphan")
    workforce_plan: Mapped[Optional["WorkforcePlan"]] = relationship("WorkforcePlan", back_populates="task", uselist=False)
    llm_calls: Mapped[List["LLMCall"]] = relationship("LLMCall", back_populates="task")
    quality_checks: Mapped[List["QualityCheck"]] = relationship("QualityCheck", back_populates="task")
    audit_logs: Mapped[List["AuditLog"]] = relationship("AuditLog", back_populates="task")


# ---------------------------------------------------------------------------
# Task Steps (DAG nodes)
# ---------------------------------------------------------------------------
class TaskStep(Base):
    __tablename__ = "task_steps"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    task_id: Mapped[str] = mapped_column(String(36), ForeignKey("tasks.id"), nullable=False)
    step_index: Mapped[int] = mapped_column(Integer, default=0)
    objective: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(50), default="pending")
    assigned_employee_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("employees.id"))
    model_used: Mapped[Optional[str]] = mapped_column(String(200))
    dependencies: Mapped[list] = mapped_column(JSONB, default=list)
    required_tools: Mapped[list] = mapped_column(JSONB, default=list)
    quality_threshold: Mapped[float] = mapped_column(Float, default=0.80)
    result: Mapped[Optional[str]] = mapped_column(Text)
    confidence: Mapped[Optional[float]] = mapped_column(Float)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    task: Mapped["Task"] = relationship("Task", back_populates="steps")
    assigned_employee: Mapped[Optional["Employee"]] = relationship("Employee", foreign_keys=[assigned_employee_id])


# ---------------------------------------------------------------------------
# Employees
# ---------------------------------------------------------------------------
class Employee(Base):
    __tablename__ = "employees"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    task_id: Mapped[str] = mapped_column(String(36), ForeignKey("tasks.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(200), nullable=False)
    name: Mapped[str] = mapped_column(String(100), default="Employee")
    avatar: Mapped[str] = mapped_column(String(50), default="👨‍💼")
    objective: Mapped[str] = mapped_column(Text, nullable=False)
    responsibilities: Mapped[list] = mapped_column(JSONB, default=list)
    skills: Mapped[list] = mapped_column(JSONB, default=list)
    tools: Mapped[list] = mapped_column(JSONB, default=list)
    model_policy: Mapped[Optional[dict]] = mapped_column(JSONB)
    manager_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("employees.id"))
    hierarchy_level: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(50), default="idle")
    current_task: Mapped[Optional[str]] = mapped_column(Text)
    current_model: Mapped[Optional[str]] = mapped_column(String(200))
    confidence: Mapped[Optional[float]] = mapped_column(Float)
    last_action: Mapped[Optional[str]] = mapped_column(Text)
    quality_requirement: Mapped[float] = mapped_column(Float, default=0.80)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    task: Mapped["Task"] = relationship("Task", back_populates="employees")
    manager: Mapped[Optional["Employee"]] = relationship("Employee", remote_side=[id], foreign_keys=[manager_id])
    runs: Mapped[List["EmployeeRun"]] = relationship("EmployeeRun", back_populates="employee")


# ---------------------------------------------------------------------------
# Employee Runs
# ---------------------------------------------------------------------------
class EmployeeRun(Base):
    __tablename__ = "employee_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    employee_id: Mapped[str] = mapped_column(String(36), ForeignKey("employees.id"), nullable=False)
    step_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("task_steps.id"))
    input_context: Mapped[Optional[str]] = mapped_column(Text)
    output: Mapped[Optional[str]] = mapped_column(Text)
    model: Mapped[Optional[str]] = mapped_column(String(200))
    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    confidence: Mapped[Optional[float]] = mapped_column(Float)
    error: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    employee: Mapped["Employee"] = relationship("Employee", back_populates="runs")


# ---------------------------------------------------------------------------
# Workforce Plans
# ---------------------------------------------------------------------------
class WorkforcePlan(Base):
    __tablename__ = "workforce_plans"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    task_id: Mapped[str] = mapped_column(String(36), ForeignKey("tasks.id"), unique=True)
    topology: Mapped[str] = mapped_column(String(50))  # sequential|parallel|hierarchical|debate|iterative
    roles: Mapped[list] = mapped_column(JSONB)  # list of role definitions
    hierarchy: Mapped[dict] = mapped_column(JSONB)  # tree structure
    rationale: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    task: Mapped["Task"] = relationship("Task", back_populates="workforce_plan")


# ---------------------------------------------------------------------------
# LLM Calls
# ---------------------------------------------------------------------------
class LLMCall(Base):
    __tablename__ = "llm_calls"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    task_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("tasks.id"))
    employee_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("employees.id"))
    step_id: Mapped[Optional[str]] = mapped_column(String(36))
    model: Mapped[str] = mapped_column(String(200))
    provider: Mapped[str] = mapped_column(String(100))
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    error: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    task: Mapped[Optional["Task"]] = relationship("Task", back_populates="llm_calls")


# ---------------------------------------------------------------------------
# AI usage / monthly budget ledger
# ---------------------------------------------------------------------------
class AIUsage(Base):
    __tablename__ = "ai_usage"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(String(200), nullable=False, default="anonymous")
    request_id: Mapped[str] = mapped_column(String(36), nullable=False, default=new_uuid)
    task_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("tasks.id"))
    model: Mapped[str] = mapped_column(String(200), nullable=False)
    task_type: Mapped[Optional[str]] = mapped_column(String(200))
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cached_tokens: Mapped[int] = mapped_column(Integer, default=0)
    estimated_cost: Mapped[float] = mapped_column(Float, default=0.0)
    actual_cost: Mapped[float] = mapped_column(Float, default=0.0)
    cache_hit: Mapped[bool] = mapped_column(Boolean, default=False)
    semantic_cache_hit: Mapped[bool] = mapped_column(Boolean, default=False)
    rag_used: Mapped[bool] = mapped_column(Boolean, default=False)
    search_used: Mapped[bool] = mapped_column(Boolean, default=False)
    tool_calls: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(30), default="completed")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (
        Index("ix_ai_usage_user_period", "user_id", "created_at"),
        Index("ix_ai_usage_task", "task_id"),
    )


# ---------------------------------------------------------------------------
# Model Metrics (learning)
# ---------------------------------------------------------------------------
class ModelMetric(Base):
    __tablename__ = "model_metrics"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    model: Mapped[str] = mapped_column(String(200), nullable=False)
    task_type: Mapped[str] = mapped_column(String(200), nullable=False)
    employee_role: Mapped[Optional[str]] = mapped_column(String(200))
    success_rate: Mapped[float] = mapped_column(Float, default=1.0)
    avg_quality: Mapped[float] = mapped_column(Float, default=0.8)
    avg_latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    avg_cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    retry_rate: Mapped[float] = mapped_column(Float, default=0.0)
    sample_count: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    __table_args__ = (
        Index("ix_model_metrics_model_tasktype", "model", "task_type"),
    )


# ---------------------------------------------------------------------------
# Quality Checks
# ---------------------------------------------------------------------------
class QualityCheck(Base):
    __tablename__ = "quality_checks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    task_id: Mapped[str] = mapped_column(String(36), ForeignKey("tasks.id"))
    step_id: Mapped[Optional[str]] = mapped_column(String(36))
    employee_id: Mapped[Optional[str]] = mapped_column(String(36))
    checker_model: Mapped[Optional[str]] = mapped_column(String(200))
    score: Mapped[float] = mapped_column(Float)
    passed: Mapped[bool] = mapped_column(Boolean)
    issues: Mapped[list] = mapped_column(JSONB, default=list)
    feedback: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    task: Mapped["Task"] = relationship("Task", back_populates="quality_checks")


# ---------------------------------------------------------------------------
# Document Chunks (pgvector RAG)
# ---------------------------------------------------------------------------
class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    task_id: Mapped[Optional[str]] = mapped_column(String(36))
    user_id: Mapped[str] = mapped_column(String(200), nullable=False, default="anonymous")
    workspace_id: Mapped[str] = mapped_column(String(200), nullable=False, default="default")
    source: Mapped[str] = mapped_column(String(500))
    content: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    embedding: Mapped[Optional[Any]] = mapped_column(Vector(1536))
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (
        Index("ix_document_chunks_content_hash", "content_hash"),
    )


# ---------------------------------------------------------------------------
# Semantic cache
# ---------------------------------------------------------------------------
class SemanticCache(Base):
    __tablename__ = "semantic_cache"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(String(200), nullable=False, default="anonymous")
    workspace_id: Mapped[str] = mapped_column(String(200), nullable=False, default="default")
    input_text: Mapped[str] = mapped_column(Text, nullable=False)
    response: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str] = mapped_column(String(200), nullable=False)
    task_type: Mapped[Optional[str]] = mapped_column(String(200))
    embedding: Mapped[Any] = mapped_column(Vector(1536), nullable=False)
    time_sensitive: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (
        Index("ix_semantic_cache_scope", "user_id", "workspace_id", "created_at"),
    )


class Memory(Base):
    __tablename__ = "memories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(String(200), nullable=False, default="anonymous")
    workspace_id: Mapped[str] = mapped_column(String(200), nullable=False, default="default")
    kind: Mapped[str] = mapped_column(String(50), nullable=False, default="fact")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    embedding: Mapped[Any] = mapped_column(Vector(1536), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (
        Index("ix_memories_scope", "user_id", "workspace_id", "kind"),
        Index("ix_memories_content_hash", "content_hash"),
    )


class ToolExecution(Base):
    __tablename__ = "tool_executions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(String(200), nullable=False, default="anonymous")
    task_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("tasks.id"))
    tool_name: Mapped[str] = mapped_column(String(200), nullable=False)
    input_payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    output_payload: Mapped[Optional[dict]] = mapped_column(JSONB)
    estimated_cost: Mapped[float] = mapped_column(Float, default=0.0)
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    error: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (
        Index("ix_tool_executions_user", "user_id", "created_at"),
        Index("ix_tool_executions_task", "task_id"),
    )


# ---------------------------------------------------------------------------
# Audit Logs
# ---------------------------------------------------------------------------
class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    task_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("tasks.id"))
    event_type: Mapped[str] = mapped_column(String(100))
    actor: Mapped[Optional[str]] = mapped_column(String(200))
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    task: Mapped[Optional["Task"]] = relationship("Task", back_populates="audit_logs")
