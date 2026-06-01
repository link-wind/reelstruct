from app.domain.shared.domain_models import SlotFillDecision, StructureSlot, TimelinePatch, TimelineTrackUpdate


def build_timeline_patch(slot: StructureSlot, decision: SlotFillDecision) -> TimelinePatch:
    patch_id = decision.timeline_patch_id or _patch_id_for_decision(slot, decision)
    text = decision.actions[0] if decision.actions else decision.timeline_hint
    target_start = max(slot.start, 0)
    target_duration = _positive_duration(slot.duration)
    target_end = target_start + target_duration

    if decision.selected_asset_id:
        source_start = max(decision.start, 0)
        source_end = decision.end if decision.end > source_start else source_start + target_duration
        source_duration = _positive_duration(source_end - source_start, target_duration)
        updates = [
            TimelineTrackUpdate(
                type="video",
                action="replace",
                text=text,
                duration=source_duration,
                style_hint="图谱素材复用",
            )
        ]
        if decision.decision_type == "reuse_with_packaging":
            updates.append(
                TimelineTrackUpdate(
                    type="card",
                    action="insert",
                    text=text,
                    duration=target_duration,
                    style_hint="包装补全",
                )
            )
        return TimelinePatch(
            patch_id=patch_id,
            slot_id=slot.id,
            operation="replace_slot_media",
            target_start=target_start,
            target_end=target_end,
            execution_summary=(
                f"将素材 {decision.selected_asset_id} 的 {round(source_start, 2)}s-{round(source_end, 2)}s "
                f"替换到“{slot.label}”段，并按需要保留包装补强。"
            ),
            source_asset_id=decision.selected_asset_id,
            source_chunk_id=decision.selected_chunk_id,
            source_start=source_start,
            source_end=source_end,
            track_updates=updates,
        )

    if decision.decision_type == "shoot_or_aigc":
        return TimelinePatch(
            patch_id=patch_id,
            slot_id=slot.id,
            operation="request_asset",
            target_start=target_start,
            target_end=target_end,
            execution_summary=f"“{slot.label}”段当前缺少可复用素材，需补拍或 AIGC 生成对应画面。",
            track_updates=[
                TimelineTrackUpdate(
                    type="video",
                    action="request",
                    text=text,
                    duration=target_duration,
                    style_hint="补拍/AIGC",
                )
            ],
        )

    return TimelinePatch(
        patch_id=patch_id,
        slot_id=slot.id,
        operation="insert_caption_card",
        target_start=target_start,
        target_end=target_end,
        execution_summary=f"“{slot.label}”段当前无直接素材，用字幕卡或标题卡补足“{slot.required_asset}”表达。",
        track_updates=[
            TimelineTrackUpdate(
                type="card",
                action="insert",
                text=text or f"用字幕补足“{slot.required_asset}”。",
                duration=target_duration,
                style_hint="兜底字幕卡",
            )
        ],
    )


def _patch_id_for_decision(slot: StructureSlot, decision: SlotFillDecision) -> str:
    if decision.selected_asset_id:
        return f"patch_{slot.id}_1"
    return f"patch_{slot.id}_fallback"


def _positive_duration(value: float, fallback: float = 1) -> float:
    if value > 0:
        return value
    if fallback > 0:
        return fallback
    return 1
