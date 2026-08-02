"""Task lifecycle states and mirrored order/project workflow statuses.

Order and project persistence keeps its Issue #005 status vocabulary
(``OrderStatus``, ``ProjectStatus`` in ``database.models``); it is not
replaced here. ``OrderIntakeStatus`` and ``ProjectWorkflowStatus`` are
core-facing mirrors of those persisted values so services and their fakes
can reason about status without importing SQLAlchemy. A received order is
persisted as ``OrderStatus.OPEN`` (mirrored as ``OrderIntakeStatus.OPEN``);
its project is persisted as ``ProjectStatus.PLANNED`` (mirrored as
``ProjectWorkflowStatus.PLANNED``). Neither status advances further within
this issue: activation and completion belong to Issues #010 and #011.
"""

from enum import StrEnum

from freelance_agents.core.workflow.errors import TaskTransitionError


class TaskStatus(StrEnum):
    """Lifecycle states for one persisted project task."""

    RECEIVED = "received"
    ACCEPTED = "accepted"
    PLANNING = "planning"
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class OrderIntakeStatus(StrEnum):
    """Core-facing mirror of the persisted freelance-order status."""

    DRAFT = "draft"
    OPEN = "open"
    ACCEPTED = "accepted"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ProjectWorkflowStatus(StrEnum):
    """Core-facing mirror of the persisted project status."""

    PLANNED = "planned"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


_TERMINAL_STATUSES = frozenset(
    {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED}
)

_FORWARD_TRANSITIONS: dict[TaskStatus, TaskStatus] = {
    TaskStatus.RECEIVED: TaskStatus.ACCEPTED,
    TaskStatus.ACCEPTED: TaskStatus.PLANNING,
    TaskStatus.PLANNING: TaskStatus.PLANNED,
    TaskStatus.PLANNED: TaskStatus.IN_PROGRESS,
    TaskStatus.IN_PROGRESS: TaskStatus.COMPLETED,
}

ALLOWED_TASK_TRANSITIONS: dict[TaskStatus, frozenset[TaskStatus]] = {
    status: frozenset({forward, TaskStatus.FAILED, TaskStatus.CANCELLED})
    for status, forward in _FORWARD_TRANSITIONS.items()
} | dict.fromkeys(_TERMINAL_STATUSES, frozenset())


def ensure_valid_task_transition(current: TaskStatus, target: TaskStatus) -> None:
    """Raise ``TaskTransitionError`` unless ``target`` is a legal next state."""
    allowed = ALLOWED_TASK_TRANSITIONS.get(current, frozenset())
    if target not in allowed:
        raise TaskTransitionError(
            f"Cannot transition task from {current.value!r} to {target.value!r}"
        )
