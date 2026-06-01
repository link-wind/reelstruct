from typing import Optional

from app.domain.structure.input_normalizer import build_material_request_sheet
from app.domain.shared.domain_models import (
    MaterialGap,
    MaterialRequestTask,
    MaterialSupplementOption,
    NewContentInput,
    PackagingPlan,
    StructureSlot,
    SupplementSelection,
    TemplateStructure,
    TransferMapping,
    TransferMappingOverride,
    TransferPlan,
)
from app.video_understanding.transfer_explainer_service import build_fallback_transfer_explanation


def build_transfer_plan(
    template: TemplateStructure,
    content: NewContentInput,
    gaps: list[MaterialGap],
    variant: str = "standard",
    mapping_overrides: Optional[list[TransferMappingOverride]] = None,
    material_request_sheet: Optional[list[MaterialRequestTask]] = None,
    supplement_selections: Optional[list[SupplementSelection]] = None,
) -> TransferPlan:
    gap_lookup = {gap.slot_id: gap for gap in gaps}
    override_lookup = {item.slot_id: item for item in (mapping_overrides or [])}
    supplement_lookup = {item.slot_id: item.method for item in (supplement_selections or [])}
    mappings = []

    for slot in template.script_pattern:
        override = override_lookup.get(slot.id)
        gap = gap_lookup.get(slot.id)
        decision_action = gap.slot_fill_decision.actions[0] if gap and gap.slot_fill_decision.actions else ""
        target_message = (
            override.target_message.strip()
            if override and override.target_message.strip()
            else _target_message_for_slot(slot.id, content, variant)
        )
        selected_supplement = _selected_supplement_option(gap, supplement_lookup.get(slot.id))
        asset_strategy = build_asset_strategy(slot, gap, override, selected_supplement)
        packaging = _packaging_plan_for_slot(slot, content, target_message, variant)
        mapping = TransferMapping(
            slot_id=slot.id,
            source_label=slot.label,
            target_message=target_message,
            asset_strategy=asset_strategy,
            source_method=slot.method,
            target_adaptation=_target_adaptation_for_slot(slot, content, target_message),
            reasoning=_transfer_reasoning_for_slot(slot),
            asset_requirement=slot.required_asset,
            packaging_plan=_packaging_plan_summary(packaging, slot.packaging_intent),
            packaging=packaging,
            fallback_strategy=selected_supplement.action if selected_supplement else gap.fill_strategy if gap else asset_strategy,
        )
        mappings.append(
            mapping.model_copy(
                update={
                    "explanation": build_fallback_transfer_explanation(
                        mapping=mapping,
                        source_observation=slot.method or slot.sample_evidence,
                        transferable_principle=slot.transferable_rule,
                        gap_handling=selected_supplement.action if selected_supplement else decision_action or gap.fill_strategy if gap else "",
                    )
                }
            )
        )

    title = content.product_name or content.topic
    variant_label = _variant_label(variant)
    return TransferPlan(
        title=f"{title} {variant_label}结构迁移方案",
        target_topic=content.topic,
        variant=variant,
        mappings=mappings,
        gaps=gaps,
        material_request_sheet=build_material_request_sheet(template, material_request_sheet),
    )


def build_asset_strategy(
    slot: StructureSlot,
    gap: Optional[MaterialGap],
    override: Optional[TransferMappingOverride],
    selected_supplement: Optional[MaterialSupplementOption] = None,
) -> str:
    if override and override.asset_strategy.strip():
        return override.asset_strategy.strip()
    if selected_supplement:
        return f"采用“{selected_supplement.method}”：{selected_supplement.action}"
    if gap:
        return gap.fill_strategy
    return f"使用已有素材：{slot.required_asset}"


def _selected_supplement_option(
    gap: Optional[MaterialGap],
    method: Optional[str],
) -> Optional[MaterialSupplementOption]:
    if not gap or not method:
        return None
    return next((option for option in gap.supplement_options if option.method == method), None)


def _target_message_for_slot(slot_id: str, content: NewContentInput, variant: str = "standard") -> str:
    product = content.product_name or content.topic
    first_point = content.selling_points[0] if content.selling_points else "核心卖点"
    second_point = content.selling_points[1] if len(content.selling_points) > 1 else first_point

    if variant == "high_click":
        if slot_id == "hook":
            return f"前 2 秒抛出反差问题：为什么 {product} 会让人停下来"
        if slot_id == "selling_points":
            return f"先给最强利益点 {first_point}，再用 {second_point} 放大好奇心"
        if slot_id == "usage":
            return f"用一个真实瞬间证明 {product} 不是普通选择"
        return f"用一句强 CTA 收束：现在就记住 {product}"
    if variant == "high_conversion":
        if slot_id == "hook":
            return f"先明确 {product} 解决的具体需求"
        if slot_id == "selling_points":
            return f"把 {first_point} 和 {second_point} 转成可感知的购买理由"
        if slot_id == "usage":
            return f"展示 {product} 的使用场景，并补足信任细节"
        return f"给出行动理由，引导用户立即完成咨询、到店或下单"
    if variant == "fast_rhythm":
        if slot_id == "hook":
            return f"快速点题：{product} 的最大亮点"
        if slot_id == "selling_points":
            return f"{first_point} / {second_point} 连续快切"
        if slot_id == "usage":
            return f"用短镜头展示 {product} 的关键使用过程"
        return f"用短 CTA 记住 {product}"
    if slot_id == "hook":
        return f"用 3 秒说明：为什么现在需要 {product}"
    if slot_id == "selling_points":
        return f"突出 {first_point}，再补充 {second_point}"
    if slot_id == "usage":
        return f"展示 {product} 在真实场景里的使用过程"
    return f"引导用户记住 {product} 并完成下一步行动"


def _target_adaptation_for_slot(slot: StructureSlot, content: NewContentInput, target_message: str) -> str:
    product = content.product_name or content.topic
    return f"把样例的“{slot.method}”迁移到 {product}：{target_message}"


def _transfer_reasoning_for_slot(slot: StructureSlot) -> str:
    return f"{slot.label} 只迁移方法：{slot.transferable_rule}{slot.non_transferable}"


def _packaging_plan_for_slot(
    slot: StructureSlot,
    content: NewContentInput,
    target_message: str,
    variant: str,
) -> PackagingPlan:
    product = content.product_name or content.topic
    first_point = content.selling_points[0] if content.selling_points else "核心卖点"
    second_point = content.selling_points[1] if len(content.selling_points) > 1 else first_point
    density = {
        "high_click": "高密度",
        "high_conversion": "标准偏强",
        "fast_rhythm": "短字幕高频",
    }.get(variant, "标准")

    if slot.id == "hook":
        title_card = f"标题卡片：{product} 为什么值得停下来"
        return PackagingPlan(
            caption_density=density,
            title_card=title_card,
            card_text=title_card,
            emphasis_words=_dedupe([product, "停下来", "前 2 秒" if variant == "high_click" else "现在需要"]),
            transition_hint="用反差开场或结果镜头直接切入主信息。",
            cover_hint=f"封面候选：{product} + 最大利益点，保留强标题。",
        )
    if slot.id == "selling_points":
        card_text = f"卖点卡片：{first_point} / {second_point}"
        return PackagingPlan(
            caption_density=density,
            title_card="",
            card_text=card_text,
            emphasis_words=_dedupe([first_point, second_point, product]),
            transition_hint="一镜一卖点，卡片跟随镜头切换。",
            cover_hint=f"封面候选：{first_point} 的可视化结果。",
        )
    if slot.id == "usage":
        card_text = f"过程标签：{product} 真实使用"
        return PackagingPlan(
            caption_density="说明字幕" if variant != "fast_rhythm" else "短字幕高频",
            title_card="",
            card_text=card_text,
            emphasis_words=_dedupe([product, "真实场景"]),
            transition_hint="从卖点卡片转入动作过程，字幕解释画面含义。",
            cover_hint=f"封面候选：{product} 的使用前后或关键动作。",
        )
    card_text = f"行动号召：记住 {product}"
    return PackagingPlan(
        caption_density="低密度停留" if variant != "fast_rhythm" else "短 CTA",
        title_card=f"结尾标题卡片：{product}",
        card_text=card_text,
        emphasis_words=_dedupe([product, "立即行动" if variant == "high_conversion" else "下一步"]),
        transition_hint="最后一镜停留，行动信息和字幕同时出现。",
        cover_hint=f"封面候选：{product} + 行动理由。",
    )


def _packaging_plan_summary(packaging: PackagingPlan, fallback: str) -> str:
    parts = [
        packaging.title_card,
        packaging.card_text,
        f"字幕密度：{packaging.caption_density}" if packaging.caption_density else "",
    ]
    summary = "；".join(item for item in parts if item)
    return summary or fallback


def _variant_label(variant: str) -> str:
    labels = {
        "standard": "",
        "high_click": "高点击版",
        "high_conversion": "高转化版",
        "fast_rhythm": "高节奏版",
    }
    return labels.get(variant, "")


def _dedupe(items: list[str]) -> list[str]:
    deduped: list[str] = []
    for item in items:
        if item and item not in deduped:
            deduped.append(item)
    return deduped
