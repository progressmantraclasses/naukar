"""
Pydantic models for the orchestration layer.
These are the internal data structures, not DB models.
"""
from __future__ import annotations
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
import uuid


def gen_id(prefix: str = "") -> str:
    return f"{prefix}{str(uuid.uuid4())[:8]}"


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
class TaskStatus(str, Enum):
    PENDING = "pending"
    ANALYZING = "analyzing"
    PLANNING = "planning"
    EXECUTING = "executing"
    REVIEWING = "reviewing"
    COMPLETED = "completed"
    FAILED = "failed"


class EmployeeStatus(str, Enum):
    IDLE = "idle"
    PLANNING = "planning"
    WORKING = "working"
    WAITING = "waiting"
    REVIEWING = "reviewing"
    BLOCKED = "blocked"
    RETRYING = "retrying"
    COMPLETED = "completed"
    FAILED = "failed"


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class WorkforceTopology(str, Enum):
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    HIERARCHICAL = "hierarchical"
    DEBATE = "debate"
    ITERATIVE = "iterative"


# ---------------------------------------------------------------------------
# Task Analysis
# ---------------------------------------------------------------------------
class ComplexityProfile(BaseModel):
    complexity_score: float = Field(ge=0, le=1)
    risk_score: float = Field(ge=0, le=1)
    reasoning_requirement: float = Field(ge=0, le=1)
    research_requirement: float = Field(ge=0, le=1)
    tool_requirement: float = Field(ge=0, le=1)
    accuracy_requirement: float = Field(ge=0, le=1)


class TaskAnalysis(BaseModel):
    task_id: str
    user_input: str
    title: str
    task_type: str
    description: str
    required_skills: List[str]
    required_tools: List[str]
    required_knowledge: List[str]
    expected_output_format: str
    complexity: ComplexityProfile
    estimated_workload_minutes: int
    subtask_count_estimate: int
    needs_research: bool
    needs_review: bool
    risk_level: str  # low|medium|high


# ---------------------------------------------------------------------------
# Employee
# ---------------------------------------------------------------------------
class EmployeeDefinition(BaseModel):
    """Blueprint for creating an employee."""
    role: str
    name: str = "Employee"
    avatar: Optional[str] = None
    objective: str
    responsibilities: List[str]
    skills: List[str]
    tools: List[str]
    quality_requirement: float = 0.80
    hierarchy_level: int = 0
    reports_to_role: Optional[str] = None


class Employee(BaseModel):
    """Live employee instance."""
    id: str = Field(default_factory=lambda: gen_id("emp-"))
    task_id: str
    role: str
    name: str = "Employee"
    avatar: str = "👨‍💼"
    objective: str
    responsibilities: List[str] = []
    skills: List[str] = []
    tools: List[str] = []
    model_policy: Dict[str, Any] = {}
    manager_id: Optional[str] = None
    hierarchy_level: int = 0
    status: EmployeeStatus = EmployeeStatus.IDLE
    current_task: Optional[str] = None
    current_model: Optional[str] = None
    confidence: Optional[float] = None
    last_action: Optional[str] = None
    quality_requirement: float = 0.80


# ---------------------------------------------------------------------------
# Task Step (DAG node)
# ---------------------------------------------------------------------------
class TaskStep(BaseModel):
    id: str = Field(default_factory=lambda: gen_id("step-"))
    task_id: str
    step_index: int
    objective: str
    description: str = ""
    status: StepStatus = StepStatus.PENDING
    assigned_employee_id: Optional[str] = None
    assigned_employee_role: Optional[str] = None
    model: Optional[str] = None
    dependencies: List[str] = []
    required_tools: List[str] = []
    quality_threshold: float = 0.80
    result: Optional[str] = None
    confidence: Optional[float] = None
    retry_count: int = 0
    context_from_steps: List[str] = []  # step IDs whose results feed into this


# ---------------------------------------------------------------------------
# Workforce Plan
# ---------------------------------------------------------------------------
class WorkforcePlan(BaseModel):
    task_id: str
    topology: WorkforceTopology
    roles: List[EmployeeDefinition]
    hierarchy: Dict[str, Any] = {}  # tree structure {role: {children: [...]}}
    rationale: str = ""
    estimated_cost_usd: float = 0.0


# ---------------------------------------------------------------------------
# Quality Result
# ---------------------------------------------------------------------------
class QualityResult(BaseModel):
    score: float
    passed: bool
    issues: List[str] = []
    feedback: str = ""
    checker_model: Optional[str] = None


# ---------------------------------------------------------------------------
# Employee Message
# ---------------------------------------------------------------------------
class EmployeeMessage(BaseModel):
    from_employee_id: str
    to_employee_id: str
    message_type: str  # task_result|request_help|status_update
    result: Optional[str] = None
    confidence: Optional[float] = None
    sources: List[str] = []
    issues: List[str] = []
    metadata: Dict[str, Any] = {}
