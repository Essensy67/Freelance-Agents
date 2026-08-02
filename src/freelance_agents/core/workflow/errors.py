"""Domain errors for order intake and task workflow operations."""


class WorkflowError(Exception):
    """Base class for order-intake and task-workflow domain errors."""


class OrderValidationError(WorkflowError):
    """Raised when order-intake input fails validation."""


class IdempotencyConflictError(WorkflowError):
    """Raised when a reused idempotency key carries materially different content."""


class PlanValidationError(WorkflowError):
    """Raised when a submitted task plan fails validation."""


class PlanAlreadyExistsError(PlanValidationError):
    """Raised when a project already has a persisted task plan."""


class TaskTransitionError(WorkflowError):
    """Raised when a task status transition is not permitted."""


class ProjectNotFoundError(WorkflowError):
    """Raised when a referenced project does not exist."""


class TaskNotFoundError(WorkflowError):
    """Raised when a referenced task does not exist."""
