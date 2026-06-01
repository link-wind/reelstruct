import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.agent.models import ConfirmationOption, ConfirmationRequest, WorkspaceRuntimeState
from app.agent.orchestrator import plan_from_prompt
from app.agent.policy import requires_confirmation
from app.agent.tool_registry import build_default_tool_registry
from app.main import app


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


def test_plan_from_prompt_sets_start_confirmation_state():
    prompt = "先看一下结构，再决定"

    planned = plan_from_prompt(prompt, WorkspaceRuntimeState())

    assert planned.agent_status == "awaiting_start_confirm"
    assert planned.pending_confirmation is not None
    assert planned.pending_confirmation.kind == "start_run"
    assert [option.action for option in planned.pending_confirmation.options] == [
        "continue",
        "pause",
    ]
    assert planned.current_plan.prompt == prompt


def test_plan_from_prompt_honors_ocr_and_skip_asr_prompt_rules():
    prompt = "先看结构和 OCR，不要跑 ASR，再决定是否生成结果"

    planned = plan_from_prompt(prompt, WorkspaceRuntimeState())

    assert [step.tool_name for step in planned.current_plan.steps] == [
        "analyze_structure",
        "run_ocr",
        "complete_materials",
        "generate_result",
    ]


def test_plan_from_prompt_uses_default_stage_sequence_for_normal_prompt():
    prompt = "先分析一下这个视频，再给我结果"

    planned = plan_from_prompt(prompt, WorkspaceRuntimeState())
    tool_names = [step.tool_name for step in planned.current_plan.steps]

    assert "analyze_structure" in tool_names
    assert "run_asr" in tool_names
    assert "complete_materials" in tool_names
    assert "generate_result" in tool_names
    assert tool_names[0] == "analyze_structure"


def test_plan_from_prompt_returns_clean_runtime_state_without_execution_residue():
    prompt = "先看一下结构，再决定"
    dirty_state = WorkspaceRuntimeState(
        agent_status="running",
        current_step="run_ocr",
        pending_confirmation=ConfirmationRequest(
            id="confirm_old",
            kind="run_ocr",
            title="旧确认",
        ),
        tool_runs=[{"id": "tool_1", "tool_name": "run_ocr", "status": "completed"}],
        stage_results={"ocr": {"status": "completed"}},
        warnings=["old warning"],
        errors=["old error"],
        skip_reasons=["old skip"],
    )

    planned = plan_from_prompt(prompt, dirty_state)

    assert planned.agent_status == "awaiting_start_confirm"
    assert planned.current_step == ""
    assert planned.tool_runs == []
    assert planned.stage_results == {}
    assert planned.warnings == []
    assert planned.errors == []
    assert planned.skip_reasons == []
    assert planned.pending_confirmation is not None
    assert planned.pending_confirmation.kind == "start_run"


def test_create_agent_plan_endpoint_returns_workspace_runtime_state():
    client = TestClient(app)

    response = client.post(
        "/api/agent/plan",
        json={
            "prompt": "先看结构和 OCR，不要跑 ASR，再决定是否生成结果",
            "state": {},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["agent_status"] == "awaiting_start_confirm"
    assert payload["pending_confirmation"]["kind"] == "start_run"
    assert [step["tool_name"] for step in payload["current_plan"]["steps"]] == [
        "analyze_structure",
        "run_ocr",
        "complete_materials",
        "generate_result",
    ]


def test_create_agent_plan_endpoint_drops_old_runtime_residue_from_input_state():
    client = TestClient(app)

    response = client.post(
        "/api/agent/plan",
        json={
            "prompt": "先分析一下这个视频，再给我结果",
            "state": {
                "current_plan": {"prompt": "old prompt", "steps": []},
                "tool_runs": [{"id": "tool_1", "tool_name": "run_ocr"}],
                "errors": ["old error"],
                "stage_results": {"ocr": {"status": "completed"}},
            },
        },
    )

    assert response.status_code == 422


def test_create_agent_plan_endpoint_rejects_unknown_top_level_fields():
    client = TestClient(app)

    response = client.post(
        "/api/agent/plan",
        json={
            "prompt": "先分析一下这个视频，再给我结果",
            "unexpected": True,
        },
    )

    assert response.status_code == 422


def test_create_agent_plan_endpoint_rejects_unknown_nested_state_fields():
    client = TestClient(app)

    response = client.post(
        "/api/agent/plan",
        json={
            "prompt": "先分析一下这个视频，再给我结果",
            "state": {
                "current_plan": {"prompt": "old prompt", "steps": []},
                "tool_runs": [],
            },
        },
    )

    assert response.status_code == 422


def test_execute_agent_tool_endpoint_runs_analyze_structure():
    client = TestClient(app)

    response = client.post(
        "/api/agent/tools/execute",
        json={
            "tool_name": "analyze_structure",
            "payload": {
                "sample": {
                    "title": "护肤样例",
                    "duration": 18,
                    "shot_count": 5,
                    "transcript_summary": "开头展示前后对比，中段讲补水效果，结尾引导下单。",
                },
                "content": {
                    "topic": "保湿精华短视频",
                    "product_name": "清透保湿精华",
                    "selling_points": ["快速补水", "清爽不黏"],
                    "available_assets": ["开头吸引镜头", "使用过程镜头"],
                },
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["tool_name"] == "analyze_structure"
    assert payload["stage"] == "structure"
    assert payload["data"]["preview"]["transfer_plan"]["title"] == "清透保湿精华 结构迁移方案"


def test_execute_agent_tool_endpoint_rejects_unknown_tool():
    client = TestClient(app)

    response = client.post(
        "/api/agent/tools/execute",
        json={
            "tool_name": "unknown_tool",
            "payload": {},
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "unknown tool: unknown_tool"


def test_execute_agent_tool_endpoint_returns_422_for_invalid_tool_payload():
    client = TestClient(app)

    response = client.post(
        "/api/agent/tools/execute",
        json={
            "tool_name": "analyze_structure",
            "payload": {
                "sample": {
                    "title": "护肤样例",
                    "duration": 18,
                    "shot_count": 5,
                },
                "content": {
                    "topic": "保湿精华短视频",
                },
                "unexpected": True,
            },
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["unexpected"]
