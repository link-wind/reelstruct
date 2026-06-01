from pathlib import Path

from app.api.api_models import SampleEvidenceRequest
from app.video_understanding.analysis_unit_service import build_analysis_units
from app.video_understanding.asr_service import transcribe_video_with_asr
from app.video_understanding.keyframe_service import extract_frame_evidence
from app.video_understanding.ocr_service import recognize_frames_with_ocr
from app.video_understanding.schemas import ShotEvidenceGraph
from app.video_understanding.shot_evidence_graph import build_initial_shot_evidence_graph
from app.video_understanding.transcript_alignment import align_transcript_to_shots

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_KEYFRAMES_DIR = PROJECT_ROOT / "services" / "api" / "storage" / "keyframes"


def generate_sample_ocr_evidence(
    request: SampleEvidenceRequest,
    *,
    keyframes_dir: Path = DEFAULT_KEYFRAMES_DIR,
) -> ShotEvidenceGraph:
    video_path = _validate_sample_video_path(request.sample_local_path)
    shots = _select_requested_shots(request)
    frames_dir = keyframes_dir / request.sample_id / "evidence"
    frames = extract_frame_evidence(
        video_path,
        shots,
        output_dir=frames_dir,
        public_prefix=f"/keyframes/{request.sample_id}/evidence",
    )
    ocr_result = recognize_frames_with_ocr(frames)
    graph = build_initial_shot_evidence_graph(
        shots=shots,
        frames=frames,
        ocr_texts=ocr_result.texts,
    )
    graph = graph.model_copy(
        update={
            "analysis_units": build_analysis_units(graph.shots),
            "warnings": ocr_result.warnings,
        }
    )
    return graph


def generate_sample_asr_evidence(
    request: SampleEvidenceRequest,
    *,
    keyframes_dir: Path = DEFAULT_KEYFRAMES_DIR,
) -> ShotEvidenceGraph:
    video_path = _validate_sample_video_path(request.sample_local_path)
    shots = _select_requested_shots(request)
    clip_start, clip_end = _shot_time_range(shots) if request.shot_indices else (None, None)
    asr_kwargs = {
        "work_dir": keyframes_dir / request.sample_id / "asr",
    }
    if clip_start is not None and clip_end is not None:
        asr_kwargs["clip_start"] = clip_start
        asr_kwargs["clip_end"] = clip_end
    asr_result = transcribe_video_with_asr(video_path, **asr_kwargs)
    transcript_texts = align_transcript_to_shots(shots, asr_result.segments)
    graph = build_initial_shot_evidence_graph(
        shots=shots,
        frames=[],
        transcript_texts=transcript_texts,
    )
    graph = graph.model_copy(
        update={
            "analysis_units": build_analysis_units(graph.shots),
            "warnings": asr_result.warnings,
        }
    )
    return graph


def _validate_sample_video_path(sample_local_path: str) -> Path:
    video_path = Path(sample_local_path)
    if not video_path.is_file():
        raise ValueError(f"sample video not found: {sample_local_path}")
    return video_path


def _select_requested_shots(request: SampleEvidenceRequest):
    if not request.shot_indices:
        return request.video_signal.shots

    requested = set(request.shot_indices)
    return [shot for shot in request.video_signal.shots if shot.index in requested]


def _shot_time_range(shots):
    if not shots:
        return None, None
    return min(shot.start for shot in shots), max(shot.end for shot in shots)
