import pytest

from app.agent.tool_executor import execute_tool
from app.models import EvaluationSummary
from pydantic import ValidationError


def _build_structure_payload() -> dict:
    return {
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
    }


def test_execute_tool_analyze_structure_returns_structure_stage_and_preview():
    response = execute_tool("analyze_structure", _build_structure_payload())

    assert response["tool_name"] == "analyze_structure"
    assert response["stage"] == "structure"
    assert "preview" in response["data"]
    assert response["data"]["preview"]["transfer_plan"]["title"] == "清透保湿精华 结构迁移方案"


def test_execute_tool_generate_result_dispatches_to_registry_handler(monkeypatch):
    captured = {}

    def fake_handle(payload: dict) -> dict:
        captured["payload"] = payload
        return {"run": {"run_id": "demo-test", "status": "succeeded"}}

    monkeypatch.setattr("app.tools.generate_result.handle", fake_handle)

    payload = {
        "preview": {
            **execute_tool("analyze_structure", _build_structure_payload())["data"]["preview"],
            "evaluation_summary": EvaluationSummary(headline="ready").model_dump(),
        },
        "template_id": "tpl-1",
        "template_title": "模板 1",
        "template_tags": ["test"],
        "variant": "standard",
    }

    response = execute_tool("generate_result", payload)

    assert captured["payload"] == payload
    assert response["tool_name"] == "generate_result"
    assert response["stage"] == "output"
    assert response["data"]["run"]["run_id"] == "demo-test"


def test_execute_tool_run_ocr_dispatches_to_registry_handler(monkeypatch):
    captured = {}

    def fake_handle(payload: dict) -> dict:
        captured["payload"] = payload
        return {"shot_evidence_graph": {"shots": [], "warnings": []}}

    monkeypatch.setattr("app.tools.run_ocr.handle", fake_handle)
    payload = {"sample_id": "sample-1"}

    response = execute_tool("run_ocr", payload)

    assert captured["payload"] == payload
    assert response["tool_name"] == "run_ocr"
    assert response["stage"] == "structure"
    assert "shot_evidence_graph" in response["data"]


def test_execute_tool_run_asr_dispatches_to_registry_handler(monkeypatch):
    captured = {}

    def fake_handle(payload: dict) -> dict:
        captured["payload"] = payload
        return {"shot_evidence_graph": {"shots": [], "warnings": []}}

    monkeypatch.setattr("app.tools.run_asr.handle", fake_handle)
    payload = {"sample_id": "sample-1"}

    response = execute_tool("run_asr", payload)

    assert captured["payload"] == payload
    assert response["tool_name"] == "run_asr"
    assert response["stage"] == "structure"
    assert "shot_evidence_graph" in response["data"]


def test_execute_tool_complete_materials_returns_materials_stage_bundle():
    response = execute_tool("complete_materials", _build_structure_payload())

    assert response["tool_name"] == "complete_materials"
    assert response["stage"] == "materials"
    assert "preview" in response["data"]
    assert response["data"]["gaps"] == response["data"]["preview"]["transfer_plan"]["gaps"]
    assert response["data"]["material_request_sheet"] == response["data"]["preview"]["transfer_plan"]["material_request_sheet"]
    assert response["data"]["evaluation_summary"] == response["data"]["preview"]["evaluation_summary"]


@pytest.mark.parametrize("tool_name", ["analyze_structure", "complete_materials"])
def test_execute_tool_rejects_unsupported_preview_fields(tool_name):
    payload = {
        **_build_structure_payload(),
        "sample_local_path": "/tmp/sample.mp4",
        "shot_evidence_graph": {},
        "template_id": "tpl-1",
        "use_ai_structure": True,
    }

    with pytest.raises(ValidationError):
        execute_tool(tool_name, payload)


def test_execute_tool_unknown_tool_raises_value_error():
    with pytest.raises(ValueError, match="unknown tool"):
        execute_tool("unknown_tool", {})
