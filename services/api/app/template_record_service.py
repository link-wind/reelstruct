from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from uuid import uuid4

from app.models import DemoRunResponse, StructureTemplateRecord, StructureTemplateSummary


def save_structure_template_record(record: StructureTemplateRecord, templates_dir: Path) -> Path:
    templates_dir.mkdir(parents=True, exist_ok=True)
    target_path = templates_dir / f"{record.template_id}.json"
    target_path.write_text(record.model_dump_json(indent=2), encoding="utf-8")
    return target_path


def create_structure_template_from_run(run: DemoRunResponse, templates_dir: Path) -> StructureTemplateRecord:
    record = StructureTemplateRecord(
        template_id=f"tpl-{uuid4().hex[:8]}",
        created_at=datetime.now(timezone.utc).isoformat(),
        source_run_id=run.run_id,
        template=run.preview.template,
    )
    save_structure_template_record(record, templates_dir)
    return record


def load_structure_template_record(template_id: str, templates_dir: Path) -> Optional[StructureTemplateRecord]:
    target_path = templates_dir / f"{template_id}.json"
    if not target_path.exists():
        return None
    return StructureTemplateRecord.model_validate_json(target_path.read_text(encoding="utf-8"))


def list_structure_template_records(templates_dir: Path, limit: int = 20) -> list[StructureTemplateSummary]:
    records: list[StructureTemplateRecord] = []
    for path in templates_dir.glob("*.json"):
        records.append(StructureTemplateRecord.model_validate_json(path.read_text(encoding="utf-8")))

    records.sort(key=lambda item: item.created_at, reverse=True)
    return [
        StructureTemplateSummary(
            template_id=item.template_id,
            created_at=item.created_at,
            source_run_id=item.source_run_id,
            title=item.template.title,
            slot_count=len(item.template.script_pattern),
            rhythm_summary=item.template.rhythm_summary,
        )
        for item in records[:limit]
    ]
