from typing import Optional

from app.video_understanding.schemas import (
    FrameEvidence,
    FrameOCRText,
    GraphAggregationResult,
    ShotEvidenceGraph,
    ShotEvidenceNode,
    ShotRelation,
    ShotTextAlignment,
    ShotUnderstanding,
    VideoShot,
)


def build_initial_shot_evidence_graph(
    *,
    shots: list[VideoShot],
    frames: list[FrameEvidence],
    transcript_texts: Optional[list[ShotTextAlignment]] = None,
    ocr_texts: Optional[list[FrameOCRText]] = None,
) -> ShotEvidenceGraph:
    frame_lookup: dict[int, list[FrameEvidence]] = {}
    for frame in frames:
        frame_lookup.setdefault(frame.shot_index, []).append(frame)

    transcript_lookup: dict[int, list[ShotTextAlignment]] = {}
    for transcript_text in transcript_texts or []:
        transcript_lookup.setdefault(transcript_text.shot_index, []).append(transcript_text)

    ocr_lookup: dict[int, list[FrameOCRText]] = {}
    for ocr_text in ocr_texts or []:
        ocr_lookup.setdefault(ocr_text.shot_index, []).append(ocr_text)

    return ShotEvidenceGraph(
        shots=[
            ShotEvidenceNode(
                shot=shot,
                frames=frame_lookup.get(shot.index, []),
                ocr_texts=ocr_lookup.get(shot.index, []),
                transcript_texts=transcript_lookup.get(shot.index, []),
                understanding=ShotUnderstanding(shot_index=shot.index),
            )
            for shot in shots
        ],
        relations=_build_adjacent_relations(shots),
    )


def apply_graph_aggregation(
    graph: ShotEvidenceGraph,
    aggregation: GraphAggregationResult,
) -> ShotEvidenceGraph:
    return graph.model_copy(
        update={
            "relations": aggregation.relations or graph.relations,
            "beats": aggregation.beats,
            "segments": aggregation.segments,
            "warnings": [*graph.warnings, *aggregation.warnings],
        }
    )


def _build_adjacent_relations(shots: list[VideoShot]) -> list[ShotRelation]:
    sorted_shots = sorted(shots, key=lambda shot: (shot.start, shot.index))
    relations: list[ShotRelation] = []
    for left, right in zip(sorted_shots, sorted_shots[1:]):
        relations.append(
            ShotRelation(
                from_shot=left.index,
                to_shot=right.index,
                relation_type="adjacent_cut",
                relation_summary=(
                    f"shot {left.index} ends at {left.end} and "
                    f"shot {right.index} starts at {right.start}"
                ),
                rhythm_change=_rhythm_change(left.duration, right.duration),
                semantic_shift="unknown",
                confidence=0.65,
            )
        )
    return relations


def _rhythm_change(left_duration: float, right_duration: float) -> str:
    if right_duration > left_duration * 1.2:
        return "slower"
    if right_duration < left_duration * 0.8:
        return "faster"
    return "steady"
