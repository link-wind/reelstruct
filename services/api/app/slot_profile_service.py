from __future__ import annotations

from app.domain.shared.domain_models import NewContentInput, SlotQueryProfile, StructureSlot


def build_slot_query_profile(slot: StructureSlot, content: NewContentInput) -> SlotQueryProfile:
    defaults = _slot_defaults(slot.id)
    semantic_terms = _dedupe(
        [
            slot.id,
            slot.label,
            slot.required_asset,
            slot.purpose,
            slot.method,
            slot.role,
            slot.intent,
            content.topic,
            content.product_name,
            *content.selling_points,
            *defaults["semantic"],
        ]
    )
    visual_terms = _dedupe([*defaults["visual"], *_terms_from_required_asset(slot.required_asset)])
    action_terms = _dedupe(defaults["action"])
    text_terms = _dedupe([content.product_name, *content.selling_points, *defaults["text"]])
    packaging_terms = _dedupe([*defaults["packaging"], *_split_packaging_terms(slot.packaging_intent)])

    return SlotQueryProfile(
        slot_id=slot.id,
        slot_label=slot.label,
        required_asset=slot.required_asset,
        required_expression="；".join(_dedupe([slot.purpose, slot.intent, slot.method, slot.transferable_rule])[:4]),
        semantic_terms=semantic_terms,
        visual_terms=visual_terms,
        action_terms=action_terms,
        text_terms=text_terms,
        packaging_terms=packaging_terms,
        target_duration=slot.duration,
        min_usable_duration=max(0.8, min(slot.duration * 0.35, 2.5)),
        replacement_modes=defaults["replacement_modes"],
    )


def _slot_defaults(slot_id: str) -> dict[str, list[str]]:
    defaults = {
        "hook": {
            "semantic": ["开头", "注意力", "停留", "结果", "反差"],
            "visual": ["人物", "产品", "结果画面", "封面"],
            "action": ["展示", "对比", "吸引"],
            "text": ["标题", "利益点", "为什么"],
            "packaging": ["大标题", "封面标题", "关键词高亮"],
            "replacement_modes": ["reuse_direct", "reuse_with_packaging", "caption_only", "shoot_or_aigc"],
        },
        "selling_points": {
            "semantic": ["卖点", "利益点", "产品价值"],
            "visual": ["产品", "瓶身", "特写", "细节"],
            "action": ["展示", "对比", "局部放大"],
            "text": ["卖点", "功效", "利益"],
            "packaging": ["卖点卡片", "关键词高亮", "局部放大框"],
            "replacement_modes": [
                "reuse_direct",
                "reuse_with_packaging",
                "caption_only",
                "structure_reorder",
                "shoot_or_aigc",
            ],
        },
        "usage": {
            "semantic": ["使用", "过程", "场景", "证明"],
            "visual": ["手部", "人物", "场景", "过程"],
            "action": ["使用", "演示", "操作", "对比"],
            "text": ["步骤", "过程", "说明"],
            "packaging": ["步骤编号", "说明字幕", "过程标签"],
            "replacement_modes": [
                "reuse_direct",
                "reuse_with_packaging",
                "caption_only",
                "structure_reorder",
                "shoot_or_aigc",
            ],
        },
        "cta": {
            "semantic": ["结尾", "行动", "转化", "记忆点"],
            "visual": ["门店", "入口", "二维码", "账号", "结尾卡"],
            "action": ["行动", "引导", "停留"],
            "text": ["入口", "优惠", "地址", "关注", "到店"],
            "packaging": ["结尾标题卡片", "行动按钮", "账号导流卡"],
            "replacement_modes": [
                "reuse_direct",
                "reuse_with_packaging",
                "caption_only",
                "structure_reorder",
                "shoot_or_aigc",
            ],
        },
    }
    return defaults.get(
        slot_id,
        {
            "semantic": ["素材", "表达", "补位"],
            "visual": ["主体", "画面"],
            "action": ["展示"],
            "text": ["字幕"],
            "packaging": ["标题卡片"],
            "replacement_modes": ["reuse_with_packaging", "caption_only", "shoot_or_aigc"],
        },
    )


def _terms_from_required_asset(value: str) -> list[str]:
    if "特写" in value:
        return ["产品", "特写", "细节"]
    if "使用" in value or "过程" in value:
        return ["手部", "过程", "场景"]
    if "CTA" in value or "结尾" in value:
        return ["结尾卡", "入口", "门店"]
    if "开头" in value:
        return ["封面", "人物", "产品"]
    return [value]


def _split_packaging_terms(value: str) -> list[str]:
    terms = []
    for token in ["卖点卡片", "关键词高亮", "短字幕", "标题卡片", "行动按钮", "停留画面", "说明字幕", "过程标签"]:
        if token in value:
            terms.append(token)
    return terms


def _dedupe(items: list[str]) -> list[str]:
    result: list[str] = []
    for item in items:
        cleaned = item.strip() if isinstance(item, str) else ""
        if cleaned and cleaned not in result:
            result.append(cleaned)
    return result
