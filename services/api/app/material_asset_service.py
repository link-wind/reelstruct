from pathlib import Path
from typing import Optional
from uuid import uuid4

from fastapi import UploadFile

from app.models import MaterialFitAnalysis, UserSlotAsset
from app.sample_service import detect_shot_count, estimate_shot_count, probe_video_duration


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_MATERIAL_DIR = PROJECT_ROOT / "services" / "api" / "storage" / "materials"


def save_material_upload(
    file: UploadFile,
    *,
    slot_id: str,
    material_dir: Optional[Path] = None,
) -> UserSlotAsset:
    target_dir = material_dir or DEFAULT_MATERIAL_DIR
    target_dir.mkdir(parents=True, exist_ok=True)

    suffix = Path(file.filename or "material.mp4").suffix or ".mp4"
    filename = f"material-{uuid4().hex[:8]}{suffix.lower()}"
    target_path = target_dir / filename
    with target_path.open("wb") as handle:
        handle.write(file.file.read())

    return UserSlotAsset(
        slot_id=slot_id,
        filename=filename,
        local_path=str(target_path),
        public_url=f"/materials/{filename}",
        analysis=analyze_material_fit(target_path),
    )


def analyze_material_fit(path: Path) -> MaterialFitAnalysis:
    duration = probe_video_duration(path) or 0
    shot_count = detect_shot_count(path) or estimate_shot_count(duration or 3)
    recommended_slot_id = recommend_slot_id(duration, shot_count)
    return MaterialFitAnalysis(
        duration=round(duration, 1),
        shot_count=shot_count,
        recommended_slot_id=recommended_slot_id,
        recommended_slot_label=slot_label(recommended_slot_id),
        recommendation_reason=recommendation_reason(recommended_slot_id, duration, shot_count),
        slot_fit_scores=slot_fit_scores(duration, shot_count),
    )


def recommend_slot_id(duration: float, shot_count: int) -> str:
    if duration <= 4:
        return "hook"
    if duration <= 8 or shot_count >= 3:
        return "selling_points"
    if duration <= 16:
        return "usage"
    return "cta"


def slot_label(slot_id: str) -> str:
    return {
        "hook": "Hook",
        "selling_points": "卖点展开",
        "usage": "使用过程",
        "cta": "CTA",
    }.get(slot_id, slot_id)


def recommendation_reason(slot_id: str, duration: float, shot_count: int) -> str:
    if slot_id == "hook":
        return f"短镜头更适合做开头吸引，当前素材约 {round(duration, 1)} 秒、{shot_count} 个镜头。"
    if slot_id == "selling_points":
        return f"镜头信息量适合承载卖点展开，当前素材约 {round(duration, 1)} 秒、{shot_count} 个镜头。"
    if slot_id == "usage":
        return f"时长适合展示连续使用过程，当前素材约 {round(duration, 1)} 秒、{shot_count} 个镜头。"
    return f"素材时长较长，更适合截取结尾行动信息或作为 CTA 背景，当前约 {round(duration, 1)} 秒。"


def slot_fit_scores(duration: float, shot_count: int) -> dict[str, int]:
    hook = 90 if duration <= 4 else max(35, 75 - int(duration * 3))
    selling = 55 if duration <= 4 else min(90, 60 + shot_count * 8)
    usage = 45 if duration <= 4 else min(88, 45 + int(duration * 3))
    cta = 30 if duration <= 8 else min(82, 40 + int(duration * 2))
    return {
        "hook": hook,
        "selling_points": selling,
        "usage": usage,
        "cta": cta,
    }
