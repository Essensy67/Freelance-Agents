"""Build a bounded analysis prompt and parse its structured plan response.

Pure functions only: no SQLAlchemy, no httpx, no AI SDK. ``AnalysisService``
is the only caller; these are kept separate so the prompt/response contract
can be tested without a provider, a database, or an event bus.
"""

import json
from uuid import UUID, uuid4

from freelance_agents.core.analysis.errors import (
    AnalysisResponseError,
    AnalysisValidationError,
)
from freelance_agents.core.providers.types import (
    CompletionMessage,
    CompletionRequest,
    CompletionRole,
)
from freelance_agents.core.workflow.value_objects import TaskInput

MAX_TITLE_CHARS = 300
MAX_DESCRIPTION_CHARS = 6000
MAX_COMPLETION_TOKENS = 2000

ANALYSIS_SYSTEM_PROMPT = """\
You are a project planning assistant for a freelance software agency. Given
a client order's title and description, decompose it into an ordered list of
concrete, actionable tasks.

Respond with ONLY a JSON array (no markdown fences, no commentary). Each
element must be an object with:
- "title": a short, non-empty string (required)
- "description": a string with implementation detail (required, may be \
empty)
- "capability": a short string naming the skill needed (e.g. "backend",
  "design"), or null if none applies (optional, defaults to null)
- "depends_on": a list of 0-based indices into this array naming tasks that
  must complete before this one (optional, defaults to an empty list)

Order the array so that, where possible, prerequisite tasks appear before
the tasks that depend on them. Do not include any text outside the JSON
array."""


def build_analysis_request(
    title: str, description: str, model: str
) -> CompletionRequest:
    """Build a bounded, structured completion request for one order.

    Raises ``AnalysisValidationError`` when the title or description
    exceeds its configured character bound, so a single oversized order
    cannot produce an unbounded prompt or provider cost.
    """
    if len(title) > MAX_TITLE_CHARS:
        raise AnalysisValidationError(
            f"Order title exceeds {MAX_TITLE_CHARS} characters and cannot be analyzed"
        )
    if len(description) > MAX_DESCRIPTION_CHARS:
        raise AnalysisValidationError(
            f"Order description exceeds {MAX_DESCRIPTION_CHARS} characters "
            "and cannot be analyzed"
        )

    user_content = f"Order title: {title}\n\nOrder description:\n{description}"
    return CompletionRequest(
        model=model,
        messages=(
            CompletionMessage(
                role=CompletionRole.SYSTEM, content=ANALYSIS_SYSTEM_PROMPT
            ),
            CompletionMessage(role=CompletionRole.USER, content=user_content),
        ),
        temperature=0.0,
        max_tokens=MAX_COMPLETION_TOKENS,
    )


def parse_plan_response(content: str) -> tuple[TaskInput, ...]:
    """Parse a provider's raw response into ordered, dependency-resolved tasks.

    Fails closed with ``AnalysisResponseError`` on anything other than a
    JSON array of task objects with a string ``title`` and in-range integer
    ``depends_on`` indices. Content-level validation (blank titles, dangling
    or self-referential dependencies) is left to
    ``core.workflow.value_objects.TaskPlan.create``, which the caller runs
    on the tasks this function returns.
    """
    try:
        data = json.loads(content)
    except json.JSONDecodeError as error:
        raise AnalysisResponseError("Provider response was not valid JSON") from error

    if not isinstance(data, list):
        raise AnalysisResponseError("Provider response must be a JSON array of tasks")

    task_ids = [uuid4() for _ in data]
    tasks: list[TaskInput] = []
    for index, item in enumerate(data):
        if not isinstance(item, dict):
            raise AnalysisResponseError(f"Task {index} must be a JSON object")

        title = item.get("title")
        if not isinstance(title, str):
            raise AnalysisResponseError(f"Task {index} is missing a string title")

        description = item.get("description", "")
        if not isinstance(description, str):
            raise AnalysisResponseError(f"Task {index} has a non-string description")

        capability = item.get("capability")
        if capability is not None and not isinstance(capability, str):
            raise AnalysisResponseError(f"Task {index} has a non-string capability")

        depends_on_raw = item.get("depends_on", [])
        if not isinstance(depends_on_raw, list):
            raise AnalysisResponseError(f"Task {index} has a non-array depends_on")

        depends_on_ids: list[UUID] = []
        for dependency_index in depends_on_raw:
            if (
                not isinstance(dependency_index, int)
                or isinstance(dependency_index, bool)
                or not (0 <= dependency_index < len(data))
            ):
                raise AnalysisResponseError(
                    f"Task {index} has an out-of-range dependency index"
                )
            depends_on_ids.append(task_ids[dependency_index])

        tasks.append(
            TaskInput(
                id=task_ids[index],
                title=title,
                description=description,
                capability=capability,
                depends_on=tuple(depends_on_ids),
            )
        )

    return tuple(tasks)
