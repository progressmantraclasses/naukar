"""
Neo4j AuraDB graph operations for Naukar.
Stores workforce hierarchy and task DAG as a graph for visualization and analysis.
"""
import structlog
from typing import List, Optional
from app.core.database import get_neo4j_driver
from app.tasks.models import Employee, TaskStep, WorkforcePlan

log = structlog.get_logger()


class WorkforceGraph:
    """
    Manages the workforce graph in Neo4j AuraDB.
    Nodes: Task, Employee, TaskStep, Skill, Model
    Edges: REPORTS_TO, ASSIGNED_TO, DEPENDS_ON, HAS_SKILL
    """

    async def create_task_node(self, task_id: str, title: str, task_type: str):
        driver = get_neo4j_driver()
        async with driver.session() as session:
            await session.run(
                """
                MERGE (t:Task {task_id: $task_id})
                SET t.title = $title, t.task_type = $task_type, t.created_at = datetime()
                """,
                task_id=task_id, title=title, task_type=task_type,
            )

    async def create_employee_nodes(self, employees: List[Employee]):
        driver = get_neo4j_driver()
        async with driver.session() as session:
            for emp in employees:
                await session.run(
                    """
                    MERGE (e:Employee {employee_id: $employee_id})
                    SET e.role = $role, e.objective = $objective,
                        e.task_id = $task_id, e.hierarchy_level = $level
                    WITH e
                    MATCH (t:Task {task_id: $task_id})
                    MERGE (e)-[:WORKS_ON]->(t)
                    """,
                    employee_id=emp.id,
                    role=emp.role,
                    objective=emp.objective,
                    task_id=emp.task_id,
                    level=emp.hierarchy_level,
                )
                # Add REPORTS_TO relationships
                if emp.manager_id:
                    await session.run(
                        """
                        MATCH (e:Employee {employee_id: $emp_id})
                        MATCH (m:Employee {employee_id: $manager_id})
                        MERGE (e)-[:REPORTS_TO]->(m)
                        """,
                        emp_id=emp.id,
                        manager_id=emp.manager_id,
                    )
                # Add skill nodes
                for skill in emp.skills:
                    await session.run(
                        """
                        MERGE (s:Skill {name: $skill})
                        WITH s
                        MATCH (e:Employee {employee_id: $emp_id})
                        MERGE (e)-[:HAS_SKILL]->(s)
                        """,
                        skill=skill,
                        emp_id=emp.id,
                    )

    async def create_step_nodes(self, steps: List[TaskStep]):
        driver = get_neo4j_driver()
        async with driver.session() as session:
            for step in steps:
                await session.run(
                    """
                    MERGE (s:TaskStep {step_id: $step_id})
                    SET s.objective = $objective, s.task_id = $task_id,
                        s.step_index = $step_index
                    WITH s
                    MATCH (t:Task {task_id: $task_id})
                    MERGE (s)-[:PART_OF]->(t)
                    """,
                    step_id=step.id,
                    objective=step.objective,
                    task_id=step.task_id,
                    step_index=step.step_index,
                )
                # Add DEPENDS_ON edges
                for dep_id in step.dependencies:
                    await session.run(
                        """
                        MATCH (s:TaskStep {step_id: $step_id})
                        MATCH (d:TaskStep {step_id: $dep_id})
                        MERGE (s)-[:DEPENDS_ON]->(d)
                        """,
                        step_id=step.id,
                        dep_id=dep_id,
                    )
                # Add ASSIGNED_TO edge
                if step.assigned_employee_id:
                    await session.run(
                        """
                        MATCH (s:TaskStep {step_id: $step_id})
                        MATCH (e:Employee {employee_id: $emp_id})
                        MERGE (s)-[:ASSIGNED_TO]->(e)
                        """,
                        step_id=step.id,
                        emp_id=step.assigned_employee_id,
                    )

    async def record_model_usage(self, employee_id: str, model: str):
        driver = get_neo4j_driver()
        async with driver.session() as session:
            await session.run(
                """
                MERGE (m:Model {name: $model})
                WITH m
                MATCH (e:Employee {employee_id: $emp_id})
                MERGE (e)-[:USED_MODEL]->(m)
                """,
                model=model,
                emp_id=employee_id,
            )
