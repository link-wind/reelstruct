from typing import Optional

from app.domain.shared.domain_models import (
    CompositionSpec,
    CompositionTrack,
    NewContentInput,
    TemplateStructure,
    TimelinePatch,
    TransferPlan,
    UserSlotAsset,
)


def build_composition_spec(
    template: TemplateStructure,
    transfer_plan: TransferPlan,
    content: Optional[NewContentInput] = None,
) -> CompositionSpec:
    mapping_lookup = {mapping.slot_id: mapping for mapping in transfer_plan.mappings}
    gap_lookup = {gap.slot_id: gap for gap in transfer_plan.gaps}
    uploaded_asset_lookup: dict[str, UserSlotAsset] = {}
    if content is not None:
        uploaded_asset_lookup = {
            asset.slot_id: asset
            for asset in content.uploaded_assets
            if asset.local_path or asset.public_url
        }
    tracks: list[CompositionTrack] = []

    for slot in template.script_pattern:
        mapping = mapping_lookup[slot.id]
        uploaded_asset = uploaded_asset_lookup.get(slot.id)
        patches = gap_lookup.get(slot.id).timeline_patches if gap_lookup.get(slot.id) else []
        source_patch = next(
            (patch for patch in patches if patch.operation == "replace_slot_media" and patch.source_asset_id),
            None,
        )
        patch_asset = _uploaded_asset_for_patch(content, source_patch) if source_patch else None
        track_asset = patch_asset or uploaded_asset
        track_payload = {
            "type": "video",
            "start": slot.start,
            "duration": slot.duration,
            "source": " ".join(
                [
                    slot.label,
                    slot.required_asset,
                    slot.purpose,
                    mapping.target_message,
                    transfer_plan.target_topic,
                ]
            ),
            "slot_id": slot.id,
            "asset_local_path": track_asset.local_path if track_asset else "",
            "asset_public_url": track_asset.public_url if track_asset else "",
        }
        if track_asset:
            track_payload["material_analysis"] = track_asset.analysis
        tracks.append(CompositionTrack(**track_payload))
        tracks.append(
            CompositionTrack(
                type="caption",
                start=slot.start + min(0.5, slot.duration / 3),
                duration=max(slot.duration - 0.5, 1),
                text=mapping.target_message,
                slot_id=slot.id,
            )
        )
        card_texts = _dedupe(
            [
                mapping.packaging.card_text,
                mapping.asset_strategy if "卡片" in mapping.asset_strategy else "",
            ]
        )
        for card_text in card_texts:
            tracks.append(
                CompositionTrack(
                    type="card",
                    start=slot.start + 0.8,
                    duration=max(slot.duration - 1, 1),
                    text=card_text,
                    slot_id=slot.id,
                )
            )
        for patch in patches:
            for update in patch.track_updates:
                if update.type != "card" or update.action != "insert":
                    continue
                tracks.append(
                    CompositionTrack(
                        type="card",
                        start=patch.target_start or slot.start,
                        duration=update.duration or max(patch.target_end - patch.target_start, 1) or slot.duration,
                        text=update.text,
                        slot_id=slot.id,
                    )
                )

    total_duration = max(slot.start + slot.duration for slot in template.script_pattern)
    return CompositionSpec(duration=round(total_duration, 1), tracks=tracks)


def _uploaded_asset_for_patch(content: Optional[NewContentInput], patch: Optional[TimelinePatch]) -> Optional[UserSlotAsset]:
    if content is None or patch is None or not patch.source_asset_id:
        return None
    for asset in content.uploaded_assets:
        asset_ids = {
            value
            for value in [
                asset.filename,
                asset.public_url,
                asset.local_path,
                _basename(asset.filename),
                _basename(asset.public_url),
                _basename(asset.local_path),
            ]
            if value
        }
        if patch.source_asset_id in asset_ids:
            return asset
        chunk_ids = {
            value
            for chunk in asset.analysis.evidence_chunks
            for value in [chunk.asset_id, _basename(chunk.asset_id)]
            if value
        }
        if patch.source_asset_id in chunk_ids:
            return asset
    return None


def _basename(value: str) -> str:
    return value.rsplit("/", 1)[-1] if value else ""


def _dedupe(items: list[str]) -> list[str]:
    deduped: list[str] = []
    for item in items:
        if item and item not in deduped:
            deduped.append(item)
    return deduped
