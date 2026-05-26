import httpx

from app.models import (
    MaterialGap,
    NewContentInput,
    SampleAnalysisSummary,
    StructureSlot,
    TemplateStructure,
    TransferMapping,
    TransferPlan,
)
from app.video_understanding.schemas import (
    ShotEvidenceGraph,
    ShotEvidenceNode,
    ShotRelation,
    ShotUnderstanding,
    VideoShot,
)


def test_explain_transfer_with_ai_returns_original_plan_without_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    from app.video_understanding.transfer_explainer_service import explain_transfer_with_ai

    plan = _transfer_plan()

    result = explain_transfer_with_ai(
        template=_template(),
        content=_content(),
        transfer_plan=plan,
        graph=_graph(),
        variant="standard",
    )

    assert result == plan


def test_explain_transfer_with_ai_posts_grounded_payload_and_updates_mapping_explanations(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-secret-key")
    posted = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "output_text": (
                    '{"explanations":[{'
                    '"slot_id":"hook",'
                    '"source_observation":"样例开场用第 1 镜的人物展示和大字幕建立停留。",'
                    '"transferable_principle":"迁移开场的停留功能，不复制原商品。",'
                    '"target_expression":"前 3 秒直接说巷口手作咖啡新店开业，手作拉花今天可见。",'
                    '"asset_plan":"使用开头吸引镜头，叠加新店开业标题卡。",'
                    '"gap_handling":"如果没有开场吸引镜头，用门店环境图加标题条补位。",'
                    '"reasoning":"样例证据显示开场负责建立停留，新内容需要替换成门店开业利益点。",'
                    '"confidence":0.86,'
                    '"warnings":["OCR 只作为辅助证据"]'
                    '}]}'
                )
            }

    class FakeClient:
        def __init__(self, **kwargs):
            posted["client_kwargs"] = kwargs

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def post(self, url, *, headers, json):
            posted["url"] = url
            posted["headers"] = headers
            posted["json"] = json
            return FakeResponse()

    monkeypatch.setattr("app.video_understanding.transfer_explainer_service.httpx.Client", FakeClient)

    from app.video_understanding.transfer_explainer_service import explain_transfer_with_ai

    result = explain_transfer_with_ai(
        template=_template(),
        content=_content(),
        transfer_plan=_transfer_plan(),
        graph=_graph(),
        variant="standard",
    )

    explanation = result.mappings[0].explanation
    prompt = posted["json"]["input"][0]["content"][0]["text"]

    assert posted["headers"]["Authorization"] == "Bearer test-secret-key"
    assert "巷口手作咖啡" in prompt
    assert "人物展示产品" in prompt
    assert "adjacent_cut" in prompt
    assert explanation.slot_id == "hook"
    assert explanation.target_expression == "前 3 秒直接说巷口手作咖啡新店开业，手作拉花今天可见。"
    assert explanation.confidence == 0.86
    assert explanation.warnings == ["OCR 只作为辅助证据"]


def test_explain_transfer_with_ai_keeps_rule_explanation_when_openai_fails(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-secret-key")

    class FailingResponse:
        status_code = 503
        text = '{"error":{"message":"Service temporarily unavailable"}}'

        def raise_for_status(self):
            request = httpx.Request("POST", "https://relay.example.com/v1/responses")
            response = httpx.Response(
                status_code=503,
                json={"error": {"message": "Service temporarily unavailable"}},
                request=request,
            )
            raise httpx.HTTPStatusError("service unavailable", request=request, response=response)

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def post(self, url, *, headers, json):
            return FailingResponse()

    monkeypatch.setattr("app.video_understanding.transfer_explainer_service.httpx.Client", FakeClient)

    from app.video_understanding.transfer_explainer_service import explain_transfer_with_ai

    result = explain_transfer_with_ai(
        template=_template(),
        content=_content(),
        transfer_plan=_transfer_plan(),
        graph=_graph(),
        variant="standard",
    )

    explanation = result.mappings[0].explanation

    assert explanation.target_expression == "用 3 秒说明：为什么现在需要 巷口手作咖啡"
    assert any("AI transfer explanation failed" in warning for warning in explanation.warnings)


def _template() -> TemplateStructure:
    return TemplateStructure(
        title="咖啡样例",
        script_pattern=[
            StructureSlot(
                id="hook",
                label="Hook",
                start=0,
                duration=3,
                purpose="开场制造注意力",
                required_asset="开头吸引镜头",
                sample_evidence="第 1 镜人物展示产品并出现标题字幕",
                method="结果先行 + 大字幕",
                transferable_rule="保留开场停留功能",
                non_transferable="不复制原商品和原文案",
                packaging_intent="用标题卡强化停留",
                evidence_shot_indices=[1],
                confidence=0.8,
            )
        ],
        rhythm_summary="前 3 秒快速进入",
        packaging_notes=["大字幕"],
        analysis_summary=SampleAnalysisSummary(headline="咖啡样例拆解", source="ai", confidence=0.8),
        shot_evidence_graph=_graph(),
    )


def _content() -> NewContentInput:
    return NewContentInput(
        topic="精品咖啡店开业短视频",
        product_name="巷口手作咖啡",
        selling_points=["手作拉花", "新店开业优惠"],
        available_assets=["开头吸引镜头"],
    )


def _transfer_plan() -> TransferPlan:
    return TransferPlan(
        title="巷口手作咖啡 结构迁移方案",
        target_topic="精品咖啡店开业短视频",
        mappings=[
            TransferMapping(
                slot_id="hook",
                source_label="Hook",
                target_message="用 3 秒说明：为什么现在需要 巷口手作咖啡",
                asset_strategy="使用已有素材：开头吸引镜头",
                source_method="结果先行 + 大字幕",
                target_adaptation="把样例的结果先行迁移到巷口手作咖啡",
                reasoning="Hook 只迁移方法，不复制样例内容",
                asset_requirement="开头吸引镜头",
                packaging_plan="标题卡强化停留",
            )
        ],
        gaps=[
            MaterialGap(
                slot_id="cta",
                missing_asset="结尾 CTA 镜头",
                impact="结尾缺少行动支撑",
                fill_strategy="用 CTA 卡片补位",
            )
        ],
    )


def _graph() -> ShotEvidenceGraph:
    return ShotEvidenceGraph(
        shots=[
            ShotEvidenceNode(
                shot=VideoShot(index=1, start=0, end=3, duration=3, keyframe_time=1.5),
                understanding=ShotUnderstanding(
                    shot_index=1,
                    visual_summary="人物展示产品",
                    text_summary="画面有大标题",
                    creative_function_hint="hook",
                    confidence=0.8,
                ),
            )
        ],
        relations=[
            ShotRelation(
                from_shot=1,
                to_shot=2,
                relation_type="adjacent_cut",
                relation_summary="shot 1 ends before shot 2",
            )
        ],
    )
