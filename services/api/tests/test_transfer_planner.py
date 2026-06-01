from app.domain.structure.transfer_planner import build_transfer_plan
from app.models import (
    MaterialGap,
    MaterialRequestTask,
    MaterialSupplementOption,
    NewContentInput,
    PackagingPlan,
    SlotFillDecision,
    SlotQueryProfile,
    SlotRetrievalPlan,
    StructureCoverageResult,
    StructureSlot,
    SupplementSelection,
    TemplateStructure,
)


def test_build_transfer_plan_uses_selected_supplement_and_variant_title():
    template = TemplateStructure(
        title="咖啡模板",
        script_pattern=[
            StructureSlot(
                id="selling_points",
                label="卖点展开",
                start=0,
                duration=4,
                purpose="推进卖点",
                required_asset="商品特写镜头",
                sample_evidence="样例给产品特写",
                method="利益点连续推进",
                transferable_rule="保留连续展开卖点的结构。",
                packaging_intent="用卖点卡片提高信息密度。",
            )
        ],
        rhythm_summary="中段密集",
        packaging_notes=[],
        analysis_summary={"headline": "分析"},
    )
    content = NewContentInput(
        topic="咖啡店开业",
        product_name="巷口手作咖啡",
        selling_points=["手作拉花", "开业优惠"],
    )
    gaps = [
        MaterialGap(
            slot_id="selling_points",
            missing_asset="商品特写镜头",
            impact="缺少商品特写",
            fill_strategy="默认补位策略",
            retrieval_plan=SlotRetrievalPlan(),
            slot_fill_decision=SlotFillDecision(slot_id="selling_points"),
            slot_query_profile=SlotQueryProfile(),
            coverage_result=StructureCoverageResult(),
            supplement_options=[
                MaterialSupplementOption(
                    method="包装补全",
                    title="用卡片补表达",
                    action="叠加卖点卡片和高亮词",
                    evidence=["缺少特写"],
                    priority=1,
                )
            ],
        )
    ]

    plan = build_transfer_plan(
        template,
        content,
        gaps,
        variant="high_click",
        material_request_sheet=[MaterialRequestTask(slot_id="selling_points", status="已拍")],
        supplement_selections=[SupplementSelection(slot_id="selling_points", method="包装补全")],
    )

    assert plan.title == "巷口手作咖啡 高点击版结构迁移方案"
    assert plan.material_request_sheet == [MaterialRequestTask(slot_id="selling_points", status="已拍")]
    assert plan.mappings[0].asset_strategy.startswith("采用“包装补全”")
    assert plan.mappings[0].fallback_strategy == "叠加卖点卡片和高亮词"
    assert plan.mappings[0].packaging == PackagingPlan(
        caption_density="高密度",
        title_card="",
        card_text="卖点卡片：手作拉花 / 开业优惠",
        emphasis_words=["手作拉花", "开业优惠", "巷口手作咖啡"],
        transition_hint="一镜一卖点，卡片跟随镜头切换。",
        cover_hint="封面候选：手作拉花 的可视化结果。",
    )
