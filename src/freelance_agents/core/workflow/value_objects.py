"""Order intake and task-plan value objects.

These types validate and normalize input before persistence. They contain
no SQLAlchemy, Telegram, or AI-provider dependencies so services can be
exercised entirely through fakes.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID, uuid4

from freelance_agents.core.workflow.errors import (
    OrderValidationError,
    PlanValidationError,
)


@dataclass(frozen=True, slots=True)
class OrderDetails:
    """Validated, transport-neutral order-intake content."""

    title: str
    description: str
    budget: Decimal | None = None

    @classmethod
    def create(
        cls, title: str, description: str, budget: Decimal | None = None
    ) -> "OrderDetails":
        """Validate and construct order details.

        Rejects a blank title or description and a budget that is not a
        positive amount.
        """
        clean_title = title.strip()
        clean_description = description.strip()
        if not clean_title:
            raise OrderValidationError("Order title must not be blank")
        if not clean_description:
            raise OrderValidationError("Order description must not be blank")
        if budget is not None and budget <= 0:
            raise OrderValidationError(
                "Order budget must be a positive amount when provided"
            )
        return cls(title=clean_title, description=clean_description, budget=budget)


@dataclass(frozen=True, slots=True)
class TaskInput:
    """Raw, transport-neutral task content submitted as part of a plan."""

    title: str
    description: str = ""
    capability: str | None = None
    id: UUID | None = None
    depends_on: tuple[UUID, ...] = ()


@dataclass(frozen=True, slots=True)
class TaskDraft:
    """One validated task within a plan, ready for persistence."""

    id: UUID
    title: str
    description: str
    capability: str | None
    position: int
    depends_on: tuple[UUID, ...] = ()


@dataclass(frozen=True, slots=True)
class TaskPlan:
    """A validated, ordered list of tasks for one project."""

    project_id: UUID
    tasks: tuple[TaskDraft, ...]

    @classmethod
    def create(cls, project_id: UUID, task_inputs: Sequence[TaskInput]) -> "TaskPlan":
        """Validate raw task inputs into an ordered, dependency-checked plan.

        Rejects an empty plan, blank titles, duplicate task ids, and
        dependency references that do not resolve within the same plan.
        """
        if not task_inputs:
            raise PlanValidationError("A plan must include at least one task")

        seen_ids: set[UUID] = set()
        drafts: list[TaskDraft] = []
        for position, task_input in enumerate(task_inputs):
            title = task_input.title.strip()
            if not title:
                raise PlanValidationError("Task title must not be blank")
            task_id = task_input.id if task_input.id is not None else uuid4()
            if task_id in seen_ids:
                raise PlanValidationError(f"Duplicate task id: {task_id}")
            seen_ids.add(task_id)
            drafts.append(
                TaskDraft(
                    id=task_id,
                    title=title,
                    description=task_input.description.strip(),
                    capability=task_input.capability,
                    position=position,
                    depends_on=tuple(task_input.depends_on),
                )
            )

        for draft in drafts:
            for dependency_id in draft.depends_on:
                if dependency_id == draft.id:
                    raise PlanValidationError(
                        f"Task {draft.id} cannot depend on itself"
                    )
                if dependency_id not in seen_ids:
                    raise PlanValidationError(
                        f"Task {draft.id} depends on unknown task {dependency_id}"
                    )

        return cls(project_id=project_id, tasks=tuple(drafts))
