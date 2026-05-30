import pytest
from pydantic import ValidationError

from app.agent.models import ConfirmationOption, ConfirmationRequest, WorkspaceRuntimeState


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
