import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.models import DemoRunResponse, RunRecordSummary


def save_demo_run_record(run: DemoRunResponse, runs_dir: Path) -> Path:
    runs_dir.mkdir(parents=True, exist_ok=True)
    target_path = runs_dir / f"{run.run_id}.json"
    target_path.write_text(run.model_dump_json(indent=2), encoding="utf-8")
    return target_path


def load_demo_run_record(run_id: str, runs_dir: Path) -> Optional[DemoRunResponse]:
    target_path = runs_dir / f"{run_id}.json"
    if not target_path.exists():
        return None
    return DemoRunResponse.model_validate_json(target_path.read_text(encoding="utf-8"))


def delete_demo_run_record(run_id: str, runs_dir: Path) -> bool:
    target_path = runs_dir / f"{run_id}.json"
    if not target_path.exists():
        return False
    target_path.unlink()
    return True


def update_demo_run_note(run_id: str, note: str, runs_dir: Path) -> Optional[DemoRunResponse]:
    record = load_demo_run_record(run_id, runs_dir)
    if record is None:
        return None
    updated = record.model_copy(update={"note": note})
    save_demo_run_record(updated, runs_dir)
    return updated


def update_demo_run_pinned(run_id: str, pinned: bool, runs_dir: Path) -> Optional[DemoRunResponse]:
    record = load_demo_run_record(run_id, runs_dir)
    if record is None:
        return None
    updated = record.model_copy(update={"pinned": pinned})
    save_demo_run_record(updated, runs_dir)
    return updated


def list_demo_run_records(
    runs_dir: Path,
    limit: int = 100,
    q: str = "",
    status: str = "",
    template_id: str = "",
    tag: str = "",
) -> list[RunRecordSummary]:
    summaries: list[tuple[tuple[str, int], RunRecordSummary]] = []

    for path in runs_dir.glob("*.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        preview = payload.get("preview", {})
        transfer_plan = preview.get("transfer_plan", {})
        mapping_lookup = {item.get("slot_id"): item for item in transfer_plan.get("mappings", [])}
        created_at = payload.get("created_at") or _mtime_to_iso(path)
        summaries.append(
            (
                (created_at, path.stat().st_mtime_ns),
                RunRecordSummary(
                    run_id=payload.get("run_id", path.stem),
                    created_at=created_at,
                    status=payload.get("status", "failed"),
                    pinned=payload.get("pinned", False),
                    template_id=payload.get("template_id", ""),
                    template_title=payload.get("template_title", ""),
                    template_tags=payload.get("template_tags", []),
                    variant=payload.get("variant", transfer_plan.get("variant", "standard")),
                    title=transfer_plan.get("title", "未命名迁移任务"),
                    target_topic=transfer_plan.get("target_topic", ""),
                    duration=preview.get("composition", {}).get("duration", 0),
                    hook=mapping_lookup.get("hook", {}).get("target_message", ""),
                    cta=mapping_lookup.get("cta", {}).get("target_message", ""),
                    gap_count=len(transfer_plan.get("gaps", [])),
                    material_request_count=len(transfer_plan.get("material_request_sheet", [])),
                    video_url=payload.get("rendered_video", {}).get("video_url", ""),
                    note=payload.get("note", ""),
                ),
            )
        )

    items = [item for _, item in sorted(summaries, key=lambda pair: pair[0], reverse=True)]
    items.sort(key=lambda item: not item.pinned)
    if status in {"succeeded", "failed"}:
        items = [item for item in items if item.status == status]
    if template_id.strip():
        items = [item for item in items if item.template_id == template_id.strip()]
    if tag.strip():
        items = [item for item in items if tag.strip() in item.template_tags]
    if q.strip():
        needle = q.strip().lower()
        items = [
            item
            for item in items
            if needle in item.run_id.lower()
            or needle in item.title.lower()
            or needle in item.target_topic.lower()
            or needle in item.note.lower()
            or needle in item.template_title.lower()
            or needle in " ".join(item.template_tags).lower()
            or needle in item.variant.lower()
        ]
    return items[:limit]


def _mtime_to_iso(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime).isoformat()
