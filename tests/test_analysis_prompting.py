"""Tests for the pure analysis prompt-building and response-parsing logic.

No provider, database, or event bus involved — these exercise only
``core.analysis.prompting``.
"""

import pytest

from freelance_agents.core.analysis.errors import (
    AnalysisResponseError,
    AnalysisValidationError,
)
from freelance_agents.core.analysis.prompting import (
    MAX_COMPLETION_TOKENS,
    MAX_DESCRIPTION_CHARS,
    MAX_TITLE_CHARS,
    build_analysis_request,
    parse_plan_response,
)
from freelance_agents.core.providers.types import CompletionRole


def test_build_analysis_request_produces_system_and_user_messages() -> None:
    request = build_analysis_request(
        "Build a landing page", "One page marketing site", model="gpt-test"
    )

    assert request.model == "gpt-test"
    assert len(request.messages) == 2
    system_message, user_message = request.messages
    assert system_message.role is CompletionRole.SYSTEM
    assert "JSON array" in system_message.content
    assert user_message.role is CompletionRole.USER
    assert "Build a landing page" in user_message.content
    assert "One page marketing site" in user_message.content
    assert request.temperature == 0.0
    assert request.max_tokens == MAX_COMPLETION_TOKENS


def test_build_analysis_request_rejects_title_over_bound() -> None:
    with pytest.raises(AnalysisValidationError):
        build_analysis_request("x" * (MAX_TITLE_CHARS + 1), "details", model="gpt-test")


def test_build_analysis_request_rejects_description_over_bound() -> None:
    with pytest.raises(AnalysisValidationError):
        build_analysis_request(
            "Title", "x" * (MAX_DESCRIPTION_CHARS + 1), model="gpt-test"
        )


def test_build_analysis_request_accepts_content_at_the_bound() -> None:
    request = build_analysis_request(
        "x" * MAX_TITLE_CHARS, "y" * MAX_DESCRIPTION_CHARS, model="gpt-test"
    )

    assert request.model == "gpt-test"


def test_parse_plan_response_resolves_index_dependencies_to_matching_ids() -> None:
    tasks = parse_plan_response(
        '[{"title": "Design"}, {"title": "Build", "depends_on": [0]}]'
    )

    assert [task.title for task in tasks] == ["Design", "Build"]
    assert tasks[1].depends_on == (tasks[0].id,)
    assert tasks[0].depends_on == ()
    assert len({task.id for task in tasks}) == 2


def test_parse_plan_response_defaults_description_and_capability() -> None:
    tasks = parse_plan_response('[{"title": "Design"}]')

    assert tasks[0].description == ""
    assert tasks[0].capability is None


def test_parse_plan_response_accepts_explicit_capability() -> None:
    tasks = parse_plan_response('[{"title": "Design", "capability": "design"}]')

    assert tasks[0].capability == "design"


def test_parse_plan_response_rejects_invalid_json() -> None:
    with pytest.raises(AnalysisResponseError):
        parse_plan_response("not json")


def test_parse_plan_response_rejects_non_list_json() -> None:
    with pytest.raises(AnalysisResponseError):
        parse_plan_response('{"title": "Design"}')


def test_parse_plan_response_rejects_non_object_item() -> None:
    with pytest.raises(AnalysisResponseError):
        parse_plan_response('["Design"]')


def test_parse_plan_response_rejects_missing_title() -> None:
    with pytest.raises(AnalysisResponseError):
        parse_plan_response('[{"description": "no title here"}]')


def test_parse_plan_response_rejects_non_string_title() -> None:
    with pytest.raises(AnalysisResponseError):
        parse_plan_response('[{"title": 42}]')


def test_parse_plan_response_rejects_non_string_description() -> None:
    with pytest.raises(AnalysisResponseError):
        parse_plan_response('[{"title": "Design", "description": 42}]')


def test_parse_plan_response_rejects_non_string_capability() -> None:
    with pytest.raises(AnalysisResponseError):
        parse_plan_response('[{"title": "Design", "capability": 42}]')


def test_parse_plan_response_rejects_non_list_depends_on() -> None:
    with pytest.raises(AnalysisResponseError):
        parse_plan_response('[{"title": "Design", "depends_on": 0}]')


def test_parse_plan_response_rejects_out_of_range_dependency_index() -> None:
    with pytest.raises(AnalysisResponseError):
        parse_plan_response('[{"title": "Design", "depends_on": [5]}]')


def test_parse_plan_response_rejects_negative_dependency_index() -> None:
    with pytest.raises(AnalysisResponseError):
        parse_plan_response('[{"title": "Design", "depends_on": [-1]}]')


def test_parse_plan_response_rejects_boolean_dependency_index() -> None:
    with pytest.raises(AnalysisResponseError):
        parse_plan_response('[{"title": "A"}, {"title": "B", "depends_on": [true]}]')


def test_parse_plan_response_accepts_empty_array() -> None:
    tasks = parse_plan_response("[]")

    assert tasks == ()
