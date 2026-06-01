from pathlib import Path
import re
from typing import Optional
from uuid import uuid4

from fastapi import UploadFile

from app.api.api_models import MaterialEvidenceChunk, MaterialFitAnalysis, UserSlotAsset
from app.material_evidence_service import build_material_evidence_chunks_from_video
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


def analyze_material_fit(
    path: Path,
    *,
    evidence_dir: Optional[Path] = None,
    evidence_public_prefix: str = "",
) -> MaterialFitAnalysis:
    duration = probe_video_duration(path) or 0
    shot_count = detect_shot_count(path) or estimate_shot_count(duration or 3)
    recommended_slot_id = recommend_slot_id(duration, shot_count)
    scores = slot_fit_scores(duration, shot_count)
    label = slot_label(recommended_slot_id)
    reason = recommendation_reason(recommended_slot_id, duration, shot_count)
    filename_terms = filename_semantic_terms(path)
    tags = material_tags(recommended_slot_id, duration, shot_count, filename_terms)
    usable_for = material_usable_for(scores)
    visual_summary = material_visual_summary(label, duration, shot_count, filename_terms)
    embedding_text = material_embedding_text(
        path=path,
        visual_summary=visual_summary,
        tags=tags,
        usable_for=usable_for,
        recommendation_reason=reason,
        recommended_slot_label=label,
    )
    evidence_chunks = build_material_evidence_chunks(
        asset_id=path.name,
        duration=duration,
        shot_count=shot_count,
        visual_summary=visual_summary,
        tags=tags,
        usable_for=usable_for,
        embedding_text=embedding_text,
        filename_terms=filename_terms,
    )
    analysis = MaterialFitAnalysis(
        duration=round(duration, 1),
        shot_count=shot_count,
        recommended_slot_id=recommended_slot_id,
        recommended_slot_label=label,
        recommendation_reason=reason,
        slot_fit_scores=scores,
        visual_summary=visual_summary,
        tags=tags,
        usable_for=usable_for,
        embedding_text=embedding_text,
        evidence_chunks=evidence_chunks,
        warnings=["等待生成真实素材证据：当前为轻量素材理解卡。"],
    )
    if evidence_dir is not None and evidence_public_prefix:
        analysis = enrich_material_analysis_with_video_evidence(
            path,
            analysis=analysis,
            evidence_dir=evidence_dir,
            evidence_public_prefix=evidence_public_prefix,
        )
    return analysis


def enrich_material_analysis_with_video_evidence(
    path: Path,
    *,
    analysis: MaterialFitAnalysis,
    evidence_dir: Path,
    evidence_public_prefix: str,
    strict: bool = False,
) -> MaterialFitAnalysis:
    try:
        chunks = build_material_evidence_chunks_from_video(
            path,
            asset_id=path.name,
            analysis=analysis,
            output_dir=evidence_dir,
            public_prefix=evidence_public_prefix,
        )
    except Exception:
        if strict:
            raise
        return analysis
    if not chunks:
        return analysis
    warnings = [warning for warning in analysis.warnings if "等待生成真实素材证据" not in warning]
    warnings.append("真实素材证据已生成")
    return analysis.model_copy(update={"evidence_chunks": chunks, "warnings": dedupe_terms(warnings)})


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


def filename_semantic_terms(path: Path) -> list[str]:
    stem = path.stem.lower().replace("_", "-")
    terms = [term for term in re.split(r"[-\s]+", stem) if term and not term.isdigit()]
    return dedupe_terms(terms)


def material_tags(slot_id: str, duration: float, shot_count: int, filename_terms: list[str]) -> list[str]:
    tags = [slot_label(slot_id)]
    if duration <= 4:
        tags.append("短素材")
    elif duration >= 12:
        tags.append("长素材")
    if shot_count <= 1:
        tags.append("单镜头")
    elif shot_count >= 3:
        tags.append("多镜头")

    semantic_tag_map = {
        "product": "产品",
        "detail": "细节",
        "closeup": "特写",
        "usage": "使用过程",
        "use": "使用过程",
        "process": "过程",
        "ending": "结尾",
        "cta": "行动号召",
        "card": "信息卡",
        "hook": "开头吸引",
    }
    tags.extend(semantic_tag_map[term] for term in filename_terms if term in semantic_tag_map)
    return dedupe_terms(tags)


def material_usable_for(scores: dict[str, int]) -> list[str]:
    usable = [slot_label(slot_id) for slot_id, score in scores.items() if score >= 55]
    return dedupe_terms(usable)


def material_visual_summary(
    recommended_slot_label: str,
    duration: float,
    shot_count: int,
    filename_terms: list[str],
) -> str:
    term_text = "、".join(filename_terms[:4])
    if term_text:
        return f"素材名称包含 {term_text} 等线索，约 {round(duration, 1)} 秒、{shot_count} 个镜头，适合优先评估为{recommended_slot_label}素材。"
    return f"约 {round(duration, 1)} 秒、{shot_count} 个镜头，适合优先评估为{recommended_slot_label}素材。"


def material_embedding_text(
    *,
    path: Path,
    visual_summary: str,
    tags: list[str],
    usable_for: list[str],
    recommendation_reason: str,
    recommended_slot_label: str,
) -> str:
    parts = [
        path.name,
        visual_summary,
        recommendation_reason,
        recommended_slot_label,
        *tags,
        *usable_for,
        *filename_semantic_terms(path),
    ]
    return " ".join(part for part in parts if part)


def build_material_evidence_chunks(
    *,
    asset_id: str,
    duration: float,
    shot_count: int,
    visual_summary: str,
    tags: list[str],
    usable_for: list[str],
    embedding_text: str,
    filename_terms: list[str],
) -> list[MaterialEvidenceChunk]:
    safe_duration = round(duration or 0, 1)
    if safe_duration <= 0:
        safe_duration = 3.0
    chunk_count = max(1, min(shot_count or 1, 4))
    chunk_length = safe_duration / chunk_count
    chunks: list[MaterialEvidenceChunk] = []
    modalities = material_modalities(visual_summary=visual_summary, tags=tags, usable_for=usable_for)
    subject_tags = material_subject_tags(tags, filename_terms)
    action_tags = material_action_tags(tags, filename_terms)
    packaging_signals = material_packaging_signals(tags, filename_terms)

    for index in range(chunk_count):
        start = round(index * chunk_length, 1)
        end = round(safe_duration if index == chunk_count - 1 else (index + 1) * chunk_length, 1)
        chunk_text = " ".join(
            [
                embedding_text,
                visual_summary,
                *tags,
                *usable_for,
                *subject_tags,
                *action_tags,
                *packaging_signals,
            ]
        )
        chunks.append(
            MaterialEvidenceChunk(
                asset_id=asset_id,
                chunk_id=f"chunk_{index + 1}",
                start=start,
                end=end,
                duration=round(end - start, 1),
                visual_summary=visual_summary,
                packaging_signals=packaging_signals,
                subject_tags=subject_tags,
                action_tags=action_tags,
                slot_hints=usable_for,
                modalities=modalities,
                embedding_text=chunk_text,
            )
        )
    return chunks


def material_modalities(*, visual_summary: str, tags: list[str], usable_for: list[str]) -> list[str]:
    modalities = ["visual"] if visual_summary else []
    if any("字幕" in tag or "标题" in tag or "信息卡" in tag for tag in tags):
        modalities.append("packaging")
    if usable_for:
        modalities.append("slot")
    return dedupe_terms(modalities)


def material_subject_tags(tags: list[str], filename_terms: list[str]) -> list[str]:
    subjects = []
    if any(term in filename_terms for term in ["product", "detail", "closeup"]) or any(tag in tags for tag in ["产品", "细节", "特写"]):
        subjects.extend(["产品", "细节"])
    if any(term in filename_terms for term in ["people", "person", "hand", "hands"]):
        subjects.append("人物/手部")
    return dedupe_terms(subjects or tags[:2])


def material_action_tags(tags: list[str], filename_terms: list[str]) -> list[str]:
    actions = []
    if "closeup" in filename_terms or "特写" in tags:
        actions.append("特写")
    if any(term in filename_terms for term in ["usage", "use", "process"]):
        actions.append("使用过程")
    return dedupe_terms(actions)


def material_packaging_signals(tags: list[str], filename_terms: list[str]) -> list[str]:
    signals = []
    if any(term in filename_terms for term in ["card", "ending", "cta"]):
        signals.append("信息卡/行动号召")
    if any(tag in tags for tag in ["信息卡", "行动号召"]):
        signals.append("信息卡/行动号召")
    return dedupe_terms(signals)


def dedupe_terms(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result
