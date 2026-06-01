from pathlib import Path

from app.api.api_models import MaterialEvidenceChunk, MaterialFitAnalysis
from app.video_understanding.keyframe_service import extract_frame_evidence
from app.video_understanding.ocr_service import recognize_frames_with_ocr
from app.video_understanding.schemas import FrameEvidence, FrameOCRText, VideoShot
from app.video_understanding.shot_detector import detect_video_signal


def build_material_evidence_chunks_from_video(
    video_path: Path,
    *,
    asset_id: str,
    analysis: MaterialFitAnalysis,
    output_dir: Path,
    public_prefix: str,
) -> list[MaterialEvidenceChunk]:
    video_signal = detect_video_signal(video_path)
    frames = extract_frame_evidence(
        video_path,
        video_signal.shots,
        output_dir=output_dir,
        public_prefix=public_prefix,
    )
    ocr_result = recognize_frames_with_ocr(frames)
    return [
        build_material_chunk_from_shot(
            asset_id=asset_id,
            shot=shot,
            frames=[frame for frame in frames if frame.shot_index == shot.index],
            ocr_texts=[text for text in ocr_result.texts if text.shot_index == shot.index],
            analysis=analysis,
        )
        for shot in video_signal.shots
    ]


def build_material_chunk_from_shot(
    *,
    asset_id: str,
    shot: VideoShot,
    frames: list[FrameEvidence],
    ocr_texts: list[FrameOCRText],
    analysis: MaterialFitAnalysis,
) -> MaterialEvidenceChunk:
    ocr_values = [text.text for text in ocr_texts if text.text]
    frame_urls = [frame.public_url for frame in frames if frame.public_url]
    subject_tags = _subject_tags(analysis.tags, analysis.embedding_text)
    action_tags = _action_tags(analysis.tags, analysis.embedding_text)
    packaging_signals = _packaging_signals(analysis.tags, ocr_values)
    modalities = ["visual"]
    if ocr_values:
        modalities.append("ocr")
    if packaging_signals:
        modalities.append("packaging")
    if analysis.usable_for:
        modalities.append("slot")

    embedding_text = " ".join(
        [
            analysis.embedding_text,
            analysis.visual_summary,
            *ocr_values,
            *packaging_signals,
            *subject_tags,
            *action_tags,
            *analysis.usable_for,
        ]
    )
    return MaterialEvidenceChunk(
        asset_id=asset_id,
        chunk_id=f"shot_{shot.index}",
        start=shot.start,
        end=shot.end,
        duration=shot.duration,
        frame_urls=frame_urls,
        ocr_texts=ocr_values,
        visual_summary=analysis.visual_summary,
        packaging_signals=packaging_signals,
        subject_tags=subject_tags,
        action_tags=action_tags,
        slot_hints=analysis.usable_for,
        modalities=_dedupe(modalities),
        embedding_text=embedding_text,
    )


def _subject_tags(tags: list[str], text: str) -> list[str]:
    subjects = []
    searchable = f"{' '.join(tags)} {text}".lower()
    if any(term in searchable for term in ["产品", "product", "瓶身", "质地", "细节", "detail"]):
        subjects.extend(["产品", "细节"])
    if any(term in searchable for term in ["人物", "person", "手部", "hand"]):
        subjects.append("人物/手部")
    return _dedupe(subjects or tags[:2])


def _action_tags(tags: list[str], text: str) -> list[str]:
    actions = []
    searchable = f"{' '.join(tags)} {text}".lower()
    if any(term in searchable for term in ["特写", "closeup"]):
        actions.append("特写")
    if any(term in searchable for term in ["使用", "过程", "use", "process"]):
        actions.append("使用过程")
    return _dedupe(actions)


def _packaging_signals(tags: list[str], ocr_texts: list[str]) -> list[str]:
    signals = []
    if ocr_texts:
        signals.append("画面文字")
    if any(tag in {"信息卡", "行动号召"} for tag in tags):
        signals.append("信息卡/行动号召")
    return _dedupe(signals)


def _dedupe(values: list[str]) -> list[str]:
    result = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result
