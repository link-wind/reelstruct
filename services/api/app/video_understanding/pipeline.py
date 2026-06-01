from pathlib import Path
from typing import Optional
from uuid import uuid4

from app.domain.shared.domain_models import SampleVideoInput, TemplateStructure
from app.structure_service import extract_template_structure
from app.video_understanding.ai_graph_service import aggregate_graph_structure_with_ai
from app.video_understanding.analysis_unit_service import build_analysis_units
from app.video_understanding.asr_service import transcribe_video_with_asr
from app.video_understanding.graph_validator import validate_graph_segments
from app.video_understanding.keyframe_service import extract_frame_evidence
from app.video_understanding.ocr_service import recognize_frames_with_ocr
from app.video_understanding.schemas import FrameEvidence, FrameOCRText, ShotEvidenceGraph, ShotTextAlignment, VideoSignal
from app.video_understanding.shot_detector import detect_video_signal
from app.video_understanding.shot_evidence_graph import apply_graph_aggregation, build_initial_shot_evidence_graph
from app.video_understanding.shot_understanding_service import understand_shots_with_ai
from app.video_understanding.template_adapter import adapt_graph_segments_to_template
from app.video_understanding.transcript_alignment import align_transcript_to_shots

PROJECT_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_KEYFRAMES_DIR = PROJECT_ROOT / "services" / "api" / "storage" / "keyframes"


def build_ai_structure_template(
    *,
    sample: SampleVideoInput,
    sample_local_path: str,
    keyframes_dir: Optional[Path] = None,
    public_prefix: str = "",
    enable_text_evidence: bool = False,
    text_evidence_graph: Optional[ShotEvidenceGraph] = None,
) -> TemplateStructure:
    video_path = Path(sample_local_path)
    signal = detect_video_signal(video_path)
    sample_id = video_path.stem or f"sample-{uuid4().hex[:8]}"
    target_keyframes_dir = (keyframes_dir or DEFAULT_KEYFRAMES_DIR) / sample_id
    keyframes_public_prefix = public_prefix or f"/keyframes/{sample_id}"
    frames = extract_frame_evidence(
        video_path,
        signal.shots,
        output_dir=target_keyframes_dir,
        public_prefix=keyframes_public_prefix,
    )
    ocr_texts: list[FrameOCRText] = []
    transcript_texts: list[ShotTextAlignment] = []
    evidence_warnings: list[str] = []
    if text_evidence_graph is not None:
        ocr_texts.extend(_extract_ocr_texts_from_graph(text_evidence_graph, signal))
        transcript_texts.extend(_extract_transcript_texts_from_graph(text_evidence_graph, signal))
        evidence_warnings.extend(text_evidence_graph.warnings)
    if enable_text_evidence:
        ocr_result = recognize_frames_with_ocr(frames)
        asr_result = transcribe_video_with_asr(video_path, work_dir=target_keyframes_dir / "asr")
        ocr_texts = _merge_ocr_texts(ocr_texts, ocr_result.texts)
        transcript_texts = _merge_transcript_texts(
            transcript_texts,
            align_transcript_to_shots(signal.shots, asr_result.segments),
        )
        evidence_warnings = [*evidence_warnings, *ocr_result.warnings, *asr_result.warnings]
    graph = build_graph_with_ai(
        signal=signal,
        frames=frames,
        sample=sample,
        transcript_texts=transcript_texts,
        ocr_texts=ocr_texts,
        warnings=evidence_warnings,
    )
    if not graph.segments:
        raise RuntimeError("AI graph aggregation returned no segments")
    return adapt_graph_segments_to_template(sample.title, graph)


def build_graph_with_ai(
    *,
    signal: VideoSignal,
    frames: list[FrameEvidence],
    sample: SampleVideoInput,
    transcript_texts: Optional[list[ShotTextAlignment]] = None,
    ocr_texts: Optional[list[FrameOCRText]] = None,
    warnings: Optional[list[str]] = None,
) -> ShotEvidenceGraph:
    graph = build_initial_shot_evidence_graph(
        shots=signal.shots,
        frames=frames,
        transcript_texts=transcript_texts,
        ocr_texts=ocr_texts,
    )
    graph = graph.model_copy(update={"analysis_units": build_analysis_units(graph.shots)})
    if warnings:
        graph = graph.model_copy(update={"warnings": [*graph.warnings, *warnings]})
    graph = understand_shots_with_ai(graph)
    aggregation = aggregate_graph_structure_with_ai(graph)
    graph = apply_graph_aggregation(graph, aggregation)
    validation_warnings = validate_graph_segments(graph)
    return graph.model_copy(update={"warnings": [*graph.warnings, *validation_warnings]})


def _extract_ocr_texts_from_graph(graph: ShotEvidenceGraph, signal: VideoSignal) -> list[FrameOCRText]:
    allowed_shots = {shot.index for shot in signal.shots}
    return _merge_ocr_texts(
        [],
        [item for node in graph.shots for item in node.ocr_texts if item.shot_index in allowed_shots],
    )


def _extract_transcript_texts_from_graph(graph: ShotEvidenceGraph, signal: VideoSignal) -> list[ShotTextAlignment]:
    allowed_shots = {shot.index for shot in signal.shots}
    return _merge_transcript_texts(
        [],
        [item for node in graph.shots for item in node.transcript_texts if item.shot_index in allowed_shots],
    )


def _merge_ocr_texts(left: list[FrameOCRText], right: list[FrameOCRText]) -> list[FrameOCRText]:
    seen: set[tuple[int, int, float, str]] = set()
    merged: list[FrameOCRText] = []
    for item in [*left, *right]:
        key = (item.shot_index, item.frame_index, item.frame_time, item.text)
        if key in seen:
            continue
        seen.add(key)
        merged.append(item)
    return merged


def _merge_transcript_texts(
    left: list[ShotTextAlignment],
    right: list[ShotTextAlignment],
) -> list[ShotTextAlignment]:
    seen: set[tuple[int, float, float, str]] = set()
    merged: list[ShotTextAlignment] = []
    for item in [*left, *right]:
        key = (item.shot_index, item.source_start, item.source_end, item.text)
        if key in seen:
            continue
        seen.add(key)
        merged.append(item)
    return merged


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
    text_evidence_graph: Optional[ShotEvidenceGraph] = None,
) -> TemplateStructure:
    try:
        return build_ai_structure_template(
            sample=sample,
            sample_local_path=sample_local_path,
            keyframes_dir=keyframes_dir,
            public_prefix=public_prefix,
            text_evidence_graph=text_evidence_graph,
        )
    except Exception as exc:
        return build_fallback_structure_template(sample=sample, reason=str(exc))
