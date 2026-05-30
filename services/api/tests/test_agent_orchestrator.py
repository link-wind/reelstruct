import pytest
from pydantic import ValidationError

from app.agent.models import ConfirmationOption, ConfirmationRequest, WorkspaceRuntimeState
from app.agent.policy import requires_confirmation
from app.agent.tool_registry import build_default_tool_registry


def test_workspace_runtime_state_defaults():
    state = WorkspaceRuntimeState()

    assert state.agent_status == "idle"
    assert state.current_plan.steps == []
    assert state.pending_confirmation is None
    assert state.tool_runs == []


def test_confirmation_request_keeps_menu_options():
    confirmation = ConfirmationRequest(
        id="confirm_ocr",
        kind="run_ocr",
        title="继续执行 OCR？",
        message="OCR 能补强标题和包装证据。",
        options=[
            {"id": "continue", "label": "继续执行", "description": "补强证据后继续", "action": "continue"},
            {"id": "skip", "label": "跳过 OCR", "description": "直接进入下一步", "action": "skip"},
        ],
    )

    assert confirmation.kind == "run_ocr"
    assert confirmation.options[0].action == "continue"


def test_confirmation_request_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        ConfirmationRequest(
            id="confirm_ocr",
            kind="run_ocr",
            title="继续执行 OCR？",
            unknown_field="unexpected",
        )


def test_confirmation_option_rejects_invalid_action():
    with pytest.raises(ValidationError):
        ConfirmationOption(
            id="continue",
            label="继续执行",
            action="approve",
        )


def test_workspace_runtime_state_default_factories_are_isolated():
    first = WorkspaceRuntimeState()
    second = WorkspaceRuntimeState()

    first.current_plan.steps.append(
        {
            "id": "step_1",
            "tool_name": "run_ocr",
            "title": "执行 OCR",
        }
    )
    first.tool_runs.append(
        {
            "id": "tool_1",
            "tool_name": "run_ocr",
        }
    )
    first.warnings.append("need review")
    first.stage_results["ocr"] = {"status": "completed"}

    assert second.current_plan.steps == []
    assert second.tool_runs == []
    assert second.warnings == []
    assert second.stage_results == {}


def test_registry_build_default_tool_registry_returns_ordered_stage_tools():
    registry = build_default_tool_registry()
    registry_by_name = {tool.name: tool for tool in registry}

    assert [tool.name for tool in registry] == [
        "analyze_structure",
        "run_ocr",
        "run_asr",
        "complete_materials",
        "generate_result",
    ]
    assert [tool.stage for tool in registry] == [
        "structure",
        "structure",
        "structure",
        "materials",
        "output",
    ]
    assert all(tool.description == "" for tool in registry)
    assert registry_by_name["analyze_structure"].confirmation_kind == ""
    assert registry_by_name["run_ocr"].confirmation_kind == "run_ocr"
    assert registry_by_name["run_asr"].confirmation_kind == "run_asr"
    assert registry_by_name["complete_materials"].confirmation_kind == "material_strategy"
    assert registry_by_name["generate_result"].confirmation_kind == "generate_result"


def test_registry_confirmation_kinds_match_confirmation_request_contract():
    registry = build_default_tool_registry()

    for tool in registry:
        if tool.confirmation_kind:
            confirmation = ConfirmationRequest(
                id=f"confirm_{tool.name}",
                kind=tool.confirmation_kind,
                title=f"确认 {tool.title}",
            )
            assert confirmation.kind == tool.confirmation_kind


@pytest.mark.parametrize(
    ("tool_name", "expected"),
    [
        ("run_ocr", True),
        ("run_asr", True),
        ("complete_materials", True),
        ("generate_result", True),
        ("analyze_structure", False),
    ],
)
def test_registry_requires_confirmation_matches_tool_policy(tool_name: str, expected: bool):
    assert requires_confirmation(tool_name) is expected


def test_registry_requires_confirmation_rejects_unknown_tool():
    with pytest.raises(ValueError, match="unknown tool: unknown_tool"):
        requires_confirmation("unknown_tool")
