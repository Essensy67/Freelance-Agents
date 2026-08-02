"""Order analysis and task decomposition application service.

Implements the Issue #008 vertical slice: read an accepted order, send a
bounded, structured prompt through the provider port, persist the prompt and
raw provider output as private audit data, and delegate plan creation to
``OrderIntakeService.create_plan`` so an AI-produced plan is validated,
persisted, and published through exactly the same path as a manually
submitted one.
"""

from uuid import UUID

from freelance_agents.core.analysis.errors import AnalysisValidationError
from freelance_agents.core.analysis.prompting import (
    build_analysis_request,
    parse_plan_response,
)
from freelance_agents.core.providers.port import CompletionProvider
from freelance_agents.core.workflow.errors import (
    PlanAlreadyExistsError,
    ProjectNotFoundError,
)
from freelance_agents.core.workflow.statuses import MessageRole
from freelance_agents.services.dto import PlanCommand, PlanResult
from freelance_agents.services.order_intake import OrderIntakeService
from freelance_agents.services.ports import WorkflowTransactionManager


class AnalysisService:
    """Turn an accepted order into a validated task plan through the AI provider."""

    def __init__(
        self,
        transactions: WorkflowTransactionManager,
        order_intake: OrderIntakeService,
        provider: CompletionProvider,
        model: str,
    ) -> None:
        self._transactions = transactions
        self._order_intake = order_intake
        self._provider = provider
        self._model = model

    async def analyze_order(self, project_id: UUID) -> PlanResult:
        """Decompose a project's order into an ordered, persisted task plan.

        Reads the project's order and open conversation, sends a bounded
        prompt through the provider port, persists the prompt and raw
        response as private conversation messages, then parses and
        validates the response and delegates its persistence to
        ``OrderIntakeService.create_plan``.

        Fails closed: a provider error, a malformed response, an invalid
        plan, or a project that already has one leaves no tasks created and
        no order/project state changed, so the caller may retry. The
        private audit messages are only persisted once a response is
        received, so a failed parse still leaves a record of what the
        provider returned.

        Raises ``ProjectNotFoundError`` for an unknown project or one with
        no order or open conversation, ``AnalysisValidationError`` when the
        order text exceeds the bounded prompt limit,
        ``PlanAlreadyExistsError`` when the project already has a plan,
        ``AnalysisResponseError`` when the provider response is not the
        expected JSON shape, and ``PlanValidationError`` when the parsed
        plan itself is invalid.
        """
        async with self._transactions.begin() as uow:
            project = await uow.projects.get(project_id)
            if project is None:
                raise ProjectNotFoundError(f"Project {project_id} does not exist")
            if project.order_id is None:
                raise AnalysisValidationError(
                    f"Project {project_id} has no associated order to analyze"
                )
            order = await uow.orders.get(project.order_id)
            if order is None:
                raise ProjectNotFoundError(f"Order {project.order_id} does not exist")
            existing_tasks = await uow.tasks.list_for_project(project_id)
            if existing_tasks:
                raise PlanAlreadyExistsError(f"Project {project_id} already has a plan")
            conversation = await uow.conversations.find_open_for_project(project_id)
            if conversation is None:
                raise ProjectNotFoundError(
                    f"Project {project_id} has no open conversation"
                )

        request = build_analysis_request(order.title, order.description, self._model)

        response = await self._provider.complete(request)

        async with self._transactions.begin() as uow:
            for message in request.messages:
                await uow.messages.append(
                    conversation.id,
                    MessageRole(message.role.value),
                    message.content,
                )
            await uow.messages.append(
                conversation.id, MessageRole.AGENT, response.content
            )

        tasks = parse_plan_response(response.content)
        return await self._order_intake.create_plan(
            project_id, PlanCommand(tasks=tasks)
        )
