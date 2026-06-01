from typing import Optional

from app.domain.shared.domain_models import MaterialRequestTask, NewContentInput, TemplateStructure


def apply_delivered_material_tasks_to_content(
    template: TemplateStructure,
    content: NewContentInput,
    request_sheet: Optional[list[MaterialRequestTask]] = None,
) -> NewContentInput:
    if not request_sheet:
        return content

    delivered_slot_ids = {
        item.slot_id
        for item in request_sheet
        if item.status in {"已拍", "已交付"}
    }
    if not delivered_slot_ids:
        return content

    delivered_assets = [
        slot.required_asset
        for slot in template.script_pattern
        if slot.id in delivered_slot_ids
    ]
    return content.model_copy(
        update={
            "available_assets": _dedupe([*content.available_assets, *delivered_assets]),
        }
    )


def apply_uploaded_slot_assets_to_content(
    template: TemplateStructure,
    content: NewContentInput,
) -> NewContentInput:
    if not content.uploaded_assets:
        return content

    uploaded_slot_ids = {asset.slot_id for asset in content.uploaded_assets if asset.local_path or asset.public_url}
    if not uploaded_slot_ids:
        return content

    uploaded_required_assets = [
        slot.required_asset
        for slot in template.script_pattern
        if slot.id in uploaded_slot_ids
    ]
    return content.model_copy(
        update={
            "available_assets": _dedupe([*content.available_assets, *uploaded_required_assets]),
        }
    )


def build_material_request_sheet(
    template: TemplateStructure,
    request_sheet: Optional[list[MaterialRequestTask]] = None,
) -> list[MaterialRequestTask]:
    if not request_sheet:
        return []

    request_lookup = {item.slot_id: item for item in request_sheet}
    return [
        MaterialRequestTask(slot_id=slot.id, status=request_lookup[slot.id].status)
        for slot in template.script_pattern
        if slot.id in request_lookup
    ]


def _dedupe(items: list[str]) -> list[str]:
    deduped: list[str] = []
    for item in items:
        if item and item not in deduped:
            deduped.append(item)
    return deduped
