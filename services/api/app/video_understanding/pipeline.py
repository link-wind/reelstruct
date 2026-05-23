from pathlib import Path
from typing import Optional
from uuid import uuid4

from app.models import SampleVideoInput, TemplateStructure
from app.structure_service import extract_template_structure
from app.video_understanding.ai_structure_service import decompose_video_structure_with_ai
from app.video_understanding.ai_vision_service import analyze_keyframe_visuals
from app.video_understanding.evidence_service import build_shot_evidence
from app.video_understanding.keyframe_service import extract_keyframes
from app.video_understanding.shot_detector import detect_video_signal
from app.video_understanding.template_adapter import adapt_ai_structure_to_template

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_KEYFRAMES_DIR = PROJECT_ROOT / "services" / "api" / "storage" / "keyframes"


def build_ai_structure_template(
    *,
    sample: SampleVideoInput,
    sample_local_path: str,
    keyframes_dir: Optional[Path] = None,
    public_prefix: str = "",
) -> TemplateStructure:
    video_path = Path(sample_local_path)
    signal = detect_video_signal(video_path)
    sample_id = video_path.stem or f"sample-{uuid4().hex[:8]}"
    target_keyframes_dir = (keyframes_dir or DEFAULT_KEYFRAMES_DIR) / sample_id
    keyframes_public_prefix = public_prefix or f"/keyframes/{sample_id}"
    keyframes = extract_keyframes(
        video_path,
        signal.shots,
        output_dir=target_keyframes_dir,
        public_prefix=keyframes_public_prefix,
    )
    visual_analyses = analyze_keyframe_visuals(keyframes)
    evidence = build_shot_evidence(
        signal.shots,
        keyframes,
        visual_analyses,
        sample.transcript_summary,
    )
    analysis = decompose_video_structure_with_ai(
        title=sample.title,
        signal=signal,
        evidence=evidence,
        transcript_summary=sample.transcript_summary,
    )
    return adapt_ai_structure_to_template(sample.title, analysis)


def build_fallback_structure_template(*, sample: SampleVideoInput, reason: str) -> TemplateStructure:
    template = extract_template_structure(sample)
    warning = f"AI 结构拆解未完成：{reason}"
    analysis_summary = template.analysis_summary.model_copy(
        update={
            "source": "fallback",
            "warnings": [warning],
            "confidence": 0,
        }
    )
    return template.model_copy(update={"analysis_summary": analysis_summary})


def build_ai_or_fallback_structure_template(
    *,
    sample: SampleVideoInput,
    sample_local_path: str,
    keyframes_dir: Optional[Path] = None,
    public_prefix: str = "",
) -> TemplateStructure:
    try:
        return build_ai_structure_template(
            sample=sample,
            sample_local_path=sample_local_path,
            keyframes_dir=keyframes_dir,
            public_prefix=public_prefix,
        )
    except Exception as exc:
        return build_fallback_structure_template(sample=sample, reason=str(exc))
