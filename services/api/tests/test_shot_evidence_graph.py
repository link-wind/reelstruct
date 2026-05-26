from app.video_understanding.graph_validator import validate_graph_segments
from app.video_understanding.schemas import (
    CreativeBeat,
    EvidenceBackedSegment,
    FrameEvidence,
    FrameOCRText,
    ShotTextAlignment,
    ShotEvidenceGraph,
    ShotEvidenceNode,
    ShotUnderstanding,
    VideoShot,
)
from app.video_understanding.shot_evidence_graph import build_initial_shot_evidence_graph


def test_build_initial_shot_evidence_graph_groups_frames_by_shot():
    shots = [
        VideoShot(index=1, start=0, end=2, duration=2, keyframe_time=1),
        VideoShot(index=2, start=2, end=5, duration=3, keyframe_time=3.5),
    ]
    frames = [
        FrameEvidence(
            shot_index=1,
            frame_index=1,
            time=1,
            role="middle",
            local_path="/tmp/1.jpg",
            public_url="/k/1.jpg",
        ),
        FrameEvidence(
            shot_index=2,
            frame_index=1,
            time=2.2,
            role="start",
            local_path="/tmp/2.jpg",
            public_url="/k/2.jpg",
        ),
    ]

    graph = build_initial_shot_evidence_graph(shots=shots, frames=frames)

    assert [node.shot.index for node in graph.shots] == [1, 2]
    assert graph.shots[0].frames[0].public_url == "/k/1.jpg"
    assert graph.shots[0].understanding == ShotUnderstanding(shot_index=1)
    assert graph.shots[1].understanding == ShotUnderstanding(shot_index=2)
    assert graph.shots[1].frames[0].role == "start"


def test_build_initial_shot_evidence_graph_adds_adjacent_relations():
    shots = [
        VideoShot(index=1, start=0, end=2, duration=2, keyframe_time=1),
        VideoShot(index=2, start=2, end=5, duration=3, keyframe_time=3.5),
        VideoShot(index=3, start=5, end=6, duration=1, keyframe_time=5.5),
    ]

    graph = build_initial_shot_evidence_graph(shots=shots, frames=[])

    assert [(relation.from_shot, relation.to_shot) for relation in graph.relations] == [(1, 2), (2, 3)]
    assert graph.relations[0].relation_type == "adjacent_cut"
    assert graph.relations[0].rhythm_change == "slower"
    assert graph.relations[0].semantic_shift == "unknown"
    assert graph.relations[0].confidence == 0.65


def test_build_initial_shot_evidence_graph_groups_transcript_texts_by_shot():
    shots = [
        VideoShot(index=1, start=0, end=2, duration=2, keyframe_time=1),
        VideoShot(index=2, start=2, end=5, duration=3, keyframe_time=3.5),
    ]
    frames = []
    transcript_texts = [
        ShotTextAlignment(
            shot_index=1,
            text="早上来不及吃饭？",
            source_start=0.0,
            source_end=1.0,
            overlap_ratio=0.5,
        ),
        ShotTextAlignment(
            shot_index=2,
            text="三分钟搞定早餐",
            source_start=2.2,
            source_end=3.0,
            overlap_ratio=0.267,
        ),
    ]

    graph = build_initial_shot_evidence_graph(shots=shots, frames=frames, transcript_texts=transcript_texts)

    assert graph.shots[0].transcript_texts[0].text == "早上来不及吃饭？"
    assert graph.shots[1].transcript_texts[0].text == "三分钟搞定早餐"


def test_build_initial_shot_evidence_graph_groups_ocr_texts_by_shot():
    shots = [
        VideoShot(index=1, start=0, end=2, duration=2, keyframe_time=1),
        VideoShot(index=2, start=2, end=5, duration=3, keyframe_time=3.5),
    ]
    ocr_texts = [
        FrameOCRText(
            shot_index=1,
            frame_index=1,
            frame_time=1.0,
            text="限时优惠",
            position="top",
            confidence=0.91,
        ),
        FrameOCRText(
            shot_index=2,
            frame_index=1,
            frame_time=3.5,
            text="立即下单",
            position="bottom",
            confidence=0.88,
        ),
    ]

    graph = build_initial_shot_evidence_graph(shots=shots, frames=[], ocr_texts=ocr_texts)

    assert graph.shots[0].ocr_texts[0].text == "限时优惠"
    assert graph.shots[1].ocr_texts[0].text == "立即下单"


def test_build_initial_shot_evidence_graph_can_include_analysis_units():
    from app.video_understanding.analysis_unit_service import build_analysis_units

    shots = [
        VideoShot(index=1, start=0, end=0.5, duration=0.5, keyframe_time=0.25),
        VideoShot(index=2, start=0.5, end=1, duration=0.5, keyframe_time=0.75),
    ]
    graph = build_initial_shot_evidence_graph(shots=shots, frames=[])
    graph = graph.model_copy(update={"analysis_units": build_analysis_units(graph.shots)})

    assert len(graph.analysis_units) == 1
    assert graph.analysis_units[0].shot_indices == [1, 2]


def test_shot_evidence_node_fills_understanding_from_shot_index_when_missing():
    node = ShotEvidenceNode(
        shot=VideoShot(index=2, start=2, end=5, duration=3, keyframe_time=3.5),
    )

    assert node.understanding == ShotUnderstanding(shot_index=2)


def test_shot_evidence_node_rejects_mismatched_understanding_index():
    try:
        ShotEvidenceNode(
            shot=VideoShot(index=2, start=2, end=5, duration=3, keyframe_time=3.5),
            understanding=ShotUnderstanding(shot_index=1),
        )
    except ValueError as exc:
        assert "understanding.shot_index must match shot.index" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_validate_graph_segments_reports_missing_shot_reference():
    graph = ShotEvidenceGraph(
        shots=[
            ShotEvidenceNode(
                shot=VideoShot(index=1, start=0, end=2, duration=2, keyframe_time=1),
                frames=[],
                understanding=ShotUnderstanding(shot_index=1, visual_summary="产品出现"),
            )
        ],
        relations=[],
        beats=[
            CreativeBeat(
                beat_id="beat_1",
                label="Hook",
                shot_indices=[1],
                start=0,
                end=2,
                function="hook",
                reason="开场",
            )
        ],
        segments=[
            EvidenceBackedSegment(
                segment_id="seg_1",
                label="Hook",
                beat_ids=["beat_1"],
                shot_indices=[1, 2],
                start=0,
                end=3,
                purpose="吸引注意",
                method="痛点开场",
                evidence=["Shot 1 产品出现"],
                rhythm="快",
                packaging="大字幕",
                transferable_rule="先抛痛点",
                non_transferable="原商品",
                required_asset="痛点场景",
                confidence=0.7,
            )
        ],
    )

    warnings = validate_graph_segments(graph)

    assert warnings == ["segment seg_1 references missing shot 2"]


def test_validate_graph_segments_reports_missing_beats_invalid_time_and_overlap():
    graph = ShotEvidenceGraph(
        shots=[
            ShotEvidenceNode(
                shot=VideoShot(index=1, start=0, end=2, duration=2, keyframe_time=1),
                understanding=ShotUnderstanding(shot_index=1),
            ),
            ShotEvidenceNode(
                shot=VideoShot(index=2, start=2, end=4, duration=2, keyframe_time=3),
                understanding=ShotUnderstanding(shot_index=2),
            ),
        ],
        segments=[
            EvidenceBackedSegment(
                segment_id="seg_1",
                label="Hook",
                beat_ids=["missing_beat"],
                shot_indices=[1],
                start=0,
                end=2,
                purpose="吸引注意",
                method="提问",
                evidence=["Shot 1"],
                rhythm="快",
                packaging="大字幕",
                transferable_rule="先提问",
                non_transferable="原台词",
                required_asset="人物开场",
                confidence=0.7,
            ),
            EvidenceBackedSegment(
                segment_id="seg_2",
                label="Body",
                beat_ids=[],
                shot_indices=[2],
                start=1.5,
                end=1.4,
                purpose="说明卖点",
                method="展示产品",
                evidence=["Shot 2"],
                rhythm="中",
                packaging="贴纸",
                transferable_rule="展示卖点",
                non_transferable="原产品",
                required_asset="产品特写",
                confidence=0.8,
            ),
        ],
    )

    warnings = validate_graph_segments(graph)

    assert warnings == [
        "segment seg_1 references missing beat missing_beat",
        "segment seg_2 has invalid time range",
    ]
