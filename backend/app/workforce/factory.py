"""
EmployeeFactory — instantiates Employee objects from EmployeeDefinition blueprints.
Also manages dynamic employee creation/removal during task execution.
"""
import structlog
from typing import List, Dict, Optional
from app.tasks.models import Employee, EmployeeDefinition, WorkforcePlan
from app.workforce.role_catalog import apply_role_profile

log = structlog.get_logger()


class EmployeeFactory:
    """
    Creates, tracks, and removes employees for a task.
    Employees are temporary — scoped to the task lifecycle.
    """

    def __init__(self, task_id: str):
        self.task_id = task_id
        self._employees: Dict[str, Employee] = {}
        self._role_to_id: Dict[str, str] = {}

    def create_from_plan(self, plan: WorkforcePlan) -> List[Employee]:
        """Instantiate all employees defined in the workforce plan."""
        employees = []

        # First pass: create all employees
        for definition in plan.roles:
            emp = self._create_employee(definition)
            employees.append(emp)

        # Second pass: wire up manager relationships
        for emp in employees:
            definition = next((d for d in plan.roles if d.role == emp.role), None)
            if definition and definition.reports_to_role:
                manager_id = self._role_to_id.get(definition.reports_to_role)
                if manager_id:
                    emp.manager_id = manager_id
                    self._employees[emp.id] = emp

        log.info(
            "employees_created",
            task_id=self.task_id,
            count=len(employees),
            roles=[e.role for e in employees],
        )
        return employees

    def create_employee(self, definition: EmployeeDefinition) -> Employee:
        """Dynamically create a single employee during execution."""
        emp = self._create_employee(definition)
        log.info("employee_dynamically_created", task_id=self.task_id, role=emp.role, id=emp.id)
        return emp

    def remove_employee(self, employee_id: str):
        """Remove an unnecessary employee."""
        emp = self._employees.pop(employee_id, None)
        if emp:
            self._role_to_id.pop(emp.role, None)
            log.info("employee_removed", task_id=self.task_id, role=emp.role, id=employee_id)

    def get_employee(self, employee_id: str) -> Optional[Employee]:
        return self._employees.get(employee_id)

    def get_by_role(self, role: str) -> Optional[Employee]:
        eid = self._role_to_id.get(role)
        return self._employees.get(eid) if eid else None

    def get_all(self) -> List[Employee]:
        return list(self._employees.values())

    def get_manager(self) -> Optional[Employee]:
        """Return the top-level manager (hierarchy_level=0)."""
        tops = [e for e in self._employees.values() if e.hierarchy_level == 0]
        return tops[0] if tops else None

    def _create_employee(self, definition: EmployeeDefinition) -> Employee:
        definition = apply_role_profile(definition)
        emp = Employee(
            task_id=self.task_id,
            role=definition.role,
            name=definition.name,
            avatar=definition.avatar or "👨‍💼",
            objective=definition.objective,
            responsibilities=definition.responsibilities,
            skills=definition.skills,
            tools=definition.tools,
            quality_requirement=definition.quality_requirement,
            hierarchy_level=definition.hierarchy_level,
        )
        self._employees[emp.id] = emp
        self._role_to_id[emp.role] = emp.id
        return emp
