from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from uuid import uuid4

from app.api.api_models import (
    DemoRunResponse,
    StructureTemplateRecord,
    StructureTemplateSummary,
    StructureTemplateVersion,
    UpdateStructureTemplateRequest,
)


def save_structure_template_record(record: StructureTemplateRecord, templates_dir: Path) -> Path:
    templates_dir.mkdir(parents=True, exist_ok=True)
    target_path = templates_dir / f"{record.template_id}.json"
    target_path.write_text(record.model_dump_json(indent=2), encoding="utf-8")
    return target_path


def create_structure_template_from_run(
    run: DemoRunResponse,
    templates_dir: Path,
    title: str = "",
    tags: Optional[list[str]] = None,
) -> StructureTemplateRecord:
    template = run.preview.template.model_copy(
        update={
            "title": title.strip() or run.preview.template.title,
        }
    )
    record = StructureTemplateRecord(
        template_id=f"tpl-{uuid4().hex[:8]}",
        created_at=datetime.now(timezone.utc).isoformat(),
        source_run_id=run.run_id,
        tags=_normalize_tags(tags or []),
        template=template,
        versions=[],
    )
    save_structure_template_record(record, templates_dir)
    return record


def load_structure_template_record(template_id: str, templates_dir: Path) -> Optional[StructureTemplateRecord]:
    target_path = templates_dir / f"{template_id}.json"
    if not target_path.exists():
        return None
    return StructureTemplateRecord.model_validate_json(target_path.read_text(encoding="utf-8"))


def delete_structure_template_record(template_id: str, templates_dir: Path) -> bool:
    target_path = templates_dir / f"{template_id}.json"
    if not target_path.exists():
        return False
    target_path.unlink()
    return True


def update_structure_template_record(
    template_id: str,
    request: UpdateStructureTemplateRequest,
    templates_dir: Path,
) -> Optional[StructureTemplateRecord]:
    record = load_structure_template_record(template_id, templates_dir)
    if record is None:
        return None

    versions = [_snapshot_template(record.template), *record.versions]

    slot_updates = {item.slot_id: item for item in request.slots}
    next_start = 0.0
    next_slots = []
    for slot in record.template.script_pattern:
        update = slot_updates.get(slot.id)
        next_duration = update.duration if update else slot.duration
        next_required_asset = update.required_asset.strip() if update and update.required_asset.strip() else slot.required_asset
        next_slots.append(
            slot.model_copy(
                update={
                    "start": round(next_start, 1),
                    "duration": round(next_duration, 1),
                    "required_asset": next_required_asset,
                }
            )
        )
        next_start += next_duration

    next_template = record.template.model_copy(
        update={
            "title": request.title.strip() or record.template.title,
            "rhythm_summary": request.rhythm_summary.strip() or record.template.rhythm_summary,
            "script_pattern": next_slots,
        }
    )
    updated = record.model_copy(
        update={
            "tags": _normalize_tags(request.tags) if "tags" in request.model_fields_set else record.tags,
            "template": next_template,
            "versions": versions,
        }
    )
    save_structure_template_record(updated, templates_dir)
    return updated


def rollback_structure_template_record(
    template_id: str,
    version_id: str,
    templates_dir: Path,
) -> Optional[StructureTemplateRecord]:
    record = load_structure_template_record(template_id, templates_dir)
    if record is None:
        return None

    selected_version = next((item for item in record.versions if item.version_id == version_id), None)
    if selected_version is None:
        return None

    updated = record.model_copy(
        update={
            "template": selected_version.template.model_copy(deep=True),
            "versions": [_snapshot_template(record.template), *record.versions],
        }
    )
    save_structure_template_record(updated, templates_dir)
    return updated


def fork_structure_template_record(
    template_id: str,
    title: str,
    templates_dir: Path,
    tags: Optional[list[str]] = None,
) -> Optional[StructureTemplateRecord]:
    record = load_structure_template_record(template_id, templates_dir)
    if record is None:
        return None

    forked = StructureTemplateRecord(
        template_id=f"tpl-{uuid4().hex[:8]}",
        created_at=datetime.now(timezone.utc).isoformat(),
        source_run_id=record.source_run_id,
        tags=_normalize_tags(tags) if tags is not None else [*record.tags],
        template=record.template.model_copy(
            deep=True,
            update={"title": title.strip() or f"{record.template.title} 副本"},
        ),
        versions=[],
    )
    save_structure_template_record(forked, templates_dir)
    return forked


def list_structure_template_records(
    templates_dir: Path,
    limit: int = 20,
    tag: str = "",
) -> list[StructureTemplateSummary]:
    records: list[StructureTemplateRecord] = []
    for path in templates_dir.glob("*.json"):
        records.append(StructureTemplateRecord.model_validate_json(path.read_text(encoding="utf-8")))

    if tag.strip():
        records = [record for record in records if tag.strip() in record.tags]

    records.sort(key=lambda item: item.created_at, reverse=True)
    return [
        StructureTemplateSummary(
            template_id=item.template_id,
            created_at=item.created_at,
            source_run_id=item.source_run_id,
            title=item.template.title,
            tags=item.tags,
            slot_count=len(item.template.script_pattern),
            rhythm_summary=item.template.rhythm_summary,
        )
        for item in records[:limit]
    ]


def _snapshot_template(template) -> StructureTemplateVersion:
    return StructureTemplateVersion(
        version_id=f"ver-{uuid4().hex[:8]}",
        created_at=datetime.now(timezone.utc).isoformat(),
        template=template.model_copy(deep=True),
    )


def _normalize_tags(tags: list[str]) -> list[str]:
    normalized: list[str] = []
    for tag in tags:
        clean_tag = tag.strip()
        if clean_tag and clean_tag not in normalized:
            normalized.append(clean_tag)
    return normalized
