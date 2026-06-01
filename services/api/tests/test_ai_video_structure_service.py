import os
from pathlib import Path
from unittest.mock import Mock

import httpx
import pytest
from pydantic import ValidationError

from app.video_understanding.evidence_service import build_shot_evidence
from app.video_understanding.keyframe_service import extract_keyframes
from app.video_understanding.schemas import (
    AIStructureAnalysis,
    KeyframeEvidence,
    ShotEvidence,
    ShotVisualAnalysis,
    VideoMetadata,
    VideoSignal,
    VideoShot,
)
from app.video_understanding.shot_detector import detect_video_signal


def test_shot_visual_analysis_schema_defaults_and_constraints():
    analysis = ShotVisualAnalysis(shot_index=1, visual_summary="A bright product shot.", confidence=0.8)

    assert analysis.shot_index == 1
    assert analysis.visual_summary == "A bright product shot."
    assert analysis.subject_type == ""
    assert analysis.scene_type == ""
    assert analysis.packaging_signals == []
    assert analysis.confidence == 0.8
    assert analysis.warnings == []


def test_shot_visual_analysis_schema_forbids_extra_fields():
    with pytest.raises(ValidationError, match="extra_forbidden"):
        ShotVisualAnalysis.model_validate(
            {
                "shot_index": 1,
                "visual_summary": "A bright product shot.",
                "confidence": 0.8,
                "unexpected_field": "x",
            }
        )


def test_ai_structure_analysis_schema_requires_segments():
    with pytest.raises(ValueError, match="segments"):
        AIStructureAnalysis(headline="痛点结构", segments=[])


def test_build_shot_evidence_combines_shots_keyframes_transcript_and_visuals(tmp_path):
    fixture_path = Path(__file__).resolve().parents[3] / "fixtures" / "vid_001.mp4"
    signal = detect_video_signal(fixture_path)
    keyframes = extract_keyframes(
        fixture_path,
        signal.shots[:1],
        output_dir=tmp_path / "keyframes",
        public_prefix="/keyframes/test",
    )
    visuals = [
        ShotVisualAnalysis(
            shot_index=keyframes[0].shot_index,
            visual_summary="产品特写，画面有大标题",
            packaging_signals=["大标题"],
            confidence=0.9,
        )
    ]

    evidence = build_shot_evidence(signal.shots[:1], keyframes, visuals, "开头提出痛点。")

    assert evidence[0].shot_index == 1
    assert evidence[0].keyframe_public_url.startswith("/keyframes/")
    assert evidence[0].transcript_text
    assert evidence[0].visual_summary == "产品特写，画面有大标题"
    assert "大标题" in evidence[0].packaging_signals


def test_build_shot_evidence_merges_overflow_transcript_into_last_shot():
    shots = [
        VideoShot(index=1, start=0, end=2, duration=2, keyframe_time=1),
        VideoShot(index=2, start=2, end=5, duration=3, keyframe_time=3.5),
    ]

    evidence = build_shot_evidence(
        shots,
        keyframes=[],
        visual_analyses=[],
        transcript_summary="第一句。第二句。第三句。",
    )

    assert evidence[0].transcript_text == "第一句"
    assert evidence[1].transcript_text == "第二句。第三句"


def test_analyze_keyframe_visuals_requires_openai_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    from app.video_understanding.ai_vision_service import analyze_keyframe_visuals

    with pytest.raises(RuntimeError, match="OPENAI_API_KEY is required"):
        analyze_keyframe_visuals([])


def test_analyze_keyframe_visuals_raises_when_keyframe_file_is_missing(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", "test-secret-key")

    from app.video_understanding.ai_vision_service import analyze_keyframe_visuals

    missing_keyframe = KeyframeEvidence(
        shot_index=1,
        keyframe_time=0,
        local_path=str(tmp_path / "missing.jpg"),
        public_url="/keyframes/missing.jpg",
    )

    with pytest.raises(FileNotFoundError, match="keyframe image not found.*shot_index=1"):
        analyze_keyframe_visuals([missing_keyframe])


def test_analyze_keyframe_visuals_posts_data_url_and_returns_analysis(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", "test-secret-key")
    posted = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "output_text": (
                    '{"visual_summary":"A clean product close-up.","subject_type":"product",'
                    '"scene_type":"studio","packaging_signals":["label visible"],'
                    '"confidence":0.87,"warnings":[]}'
                )
            }

    class FakeClient:
        def __init__(self, **kwargs):
            posted["client_kwargs"] = kwargs

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def post(self, url, *, headers, json):
            posted["url"] = url
            posted["headers"] = headers
            posted["json"] = json
            return FakeResponse()

    image_path = tmp_path / "shot.jpg"
    image_path.write_bytes(b"\xff\xd8fake-jpeg\xff\xd9")
    keyframe = KeyframeEvidence(
        shot_index=3,
        keyframe_time=1.2,
        local_path=str(image_path),
        public_url="/keyframes/shot.jpg",
    )

    monkeypatch.setattr("app.video_understanding.ai_vision_service.httpx.Client", FakeClient)
    from app.video_understanding.ai_vision_service import analyze_keyframe_visuals

    analyses = analyze_keyframe_visuals([keyframe])

    assert len(analyses) == 1
    assert analyses[0].shot_index == 3
    assert analyses[0].visual_summary == "A clean product close-up."
    assert analyses[0].confidence == 0.87

    content = posted["json"]["input"][0]["content"]
    image_parts = [part for part in content if part["type"] == "input_image"]
    assert image_parts[0]["image_url"].startswith("data:image/jpeg;base64,")
    assert "test-secret-key" not in str(posted["json"])
    assert posted["headers"]["Authorization"] == "Bearer test-secret-key"


def test_analyze_keyframe_visuals_uses_openai_base_url(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", "test-secret-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://relay.example.com/v1/")
    posted = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "output_text": (
                    '{"visual_summary":"A clean product close-up.","subject_type":"product",'
                    '"scene_type":"studio","packaging_signals":[],"confidence":0.87,"warnings":[]}'
                )
            }

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def post(self, url, *, headers, json):
            posted["url"] = url
            return FakeResponse()

    monkeypatch.setattr("app.video_understanding.ai_vision_service.httpx.Client", FakeClient)

    from app.video_understanding.ai_vision_service import analyze_keyframe_visuals

    analyze_keyframe_visuals([_keyframe_with_image(tmp_path)])

    assert posted["url"] == "https://relay.example.com/v1/responses"


def test_analyze_keyframe_visuals_wraps_http_status_error(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", "test-secret-key")

    class FakeResponse:
        status_code = 429
        text = '{"error":{"message":"rate limited"}}'

        def raise_for_status(self):
            request = httpx.Request("POST", "https://api.openai.com/v1/responses")
            response = httpx.Response(
                status_code=429,
                json={"error": {"message": "rate limited"}},
                request=request,
            )
            raise httpx.HTTPStatusError("rate limited", request=request, response=response)

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def post(self, url, *, headers, json):
            return FakeResponse()

    image_path = tmp_path / "shot.jpg"
    image_path.write_bytes(b"\xff\xd8fake-jpeg\xff\xd9")
    keyframe = KeyframeEvidence(
        shot_index=2,
        keyframe_time=0.5,
        local_path=str(image_path),
        public_url="/keyframes/shot.jpg",
    )

    monkeypatch.setattr("app.video_understanding.ai_vision_service.httpx.Client", FakeClient)
    from app.video_understanding.ai_vision_service import analyze_keyframe_visuals

    with pytest.raises(RuntimeError, match="shot_index=2.*status=429.*rate limited"):
        analyze_keyframe_visuals([keyframe])


def test_analyze_keyframe_visuals_raises_value_error_when_output_text_is_missing(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", "test-secret-key")
    keyframe = _keyframe_with_image(tmp_path)
    _install_fake_openai_response(monkeypatch, {})

    from app.video_understanding.ai_vision_service import analyze_keyframe_visuals

    with pytest.raises(ValueError, match="missing output_text.*shot_index=1"):
        analyze_keyframe_visuals([keyframe])


def test_analyze_keyframe_visuals_raises_value_error_when_output_text_is_not_json(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", "test-secret-key")
    keyframe = _keyframe_with_image(tmp_path)
    _install_fake_openai_response(monkeypatch, {"output_text": "not json"})

    from app.video_understanding.ai_vision_service import analyze_keyframe_visuals

    with pytest.raises(ValueError, match="not valid JSON.*shot_index=1"):
        analyze_keyframe_visuals([keyframe])


def test_understand_shots_with_ai_posts_multiple_frames_and_returns_understanding(monkeypatch, tmp_path):
    from app.video_understanding.schemas import (
        AnalysisUnit,
        FrameEvidence,
        FrameOCRText,
        ShotEvidenceGraph,
        ShotEvidenceNode,
        ShotTextAlignment,
        VideoShot,
    )
    from app.video_understanding.shot_understanding_service import understand_shots_with_ai

    monkeypatch.setenv("OPENAI_API_KEY", "test-secret-key")
    posted = {}
    frame_paths = []
    for index in range(2):
        frame_path = tmp_path / f"shot_1_{index}.jpg"
        frame_path.write_bytes(b"\xff\xd8fake-jpeg\xff\xd9")
        frame_paths.append(frame_path)

    shot_node = ShotEvidenceNode(
        shot=VideoShot(index=1, start=0, end=2, duration=2, keyframe_time=1),
        frames=[
            FrameEvidence(
                shot_index=1,
                frame_index=1,
                time=0.15,
                role="start",
                local_path=str(frame_paths[0]),
                public_url="/keyframes/shot_1_start.jpg",
            ),
            FrameEvidence(
                shot_index=1,
                frame_index=2,
                time=1,
                role="middle",
                local_path=str(frame_paths[1]),
                public_url="/keyframes/shot_1_middle.jpg",
            ),
        ],
        ocr_texts=[
            FrameOCRText(
                shot_index=1,
                frame_index=1,
                frame_time=0.15,
                text="限时优惠",
                position="top",
                confidence=0.91,
            )
        ],
        transcript_texts=[
            ShotTextAlignment(
                shot_index=1,
                text="早上来不及吃饭？",
                source_start=0.2,
                source_end=1.4,
                overlap_ratio=0.6,
            )
        ],
    )
    graph = ShotEvidenceGraph(
        shots=[
            shot_node
        ],
        analysis_units=[
            AnalysisUnit(
                unit_id="unit_1",
                shot_indices=[1],
                start=0,
                end=2,
                duration=2,
                representative_frames=shot_node.frames,
                ocr_texts=shot_node.ocr_texts,
                transcript_texts=shot_node.transcript_texts,
            )
        ]
    )

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "output_text": (
                    '{"visual_summary":"人物展示产品并口播","text_summary":"画面有卖点字幕",'
                    '"subject":"人物和产品","scene":"室内口播","action":"展示产品",'
                    '"packaging_signals":["底部字幕","产品露出"],'
                    '"creative_function_hint":"product_intro","confidence":0.84,"warnings":[]}'
                )
            }

    class FakeClient:
        def __init__(self, **kwargs):
            posted["client_kwargs"] = kwargs

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def post(self, url, *, headers, json):
            posted["url"] = url
            posted["headers"] = headers
            posted["json"] = json
            return FakeResponse()

    monkeypatch.setattr("app.video_understanding.shot_understanding_service.httpx.Client", FakeClient)

    understood = understand_shots_with_ai(graph)

    understanding = understood.shots[0].understanding
    assert understanding.visual_summary == "人物展示产品并口播"
    assert understanding.subject == "人物和产品"
    assert understanding.creative_function_hint == "product_intro"
    assert understanding.confidence == 0.84
    content = posted["json"]["input"][0]["content"]
    image_parts = [part for part in content if part["type"] == "input_image"]
    prompt_text = content[0]["text"]
    assert len(image_parts) == 2
    assert all(part["image_url"].startswith("data:image/jpeg;base64,") for part in image_parts)
    assert "限时优惠" in prompt_text
    assert "ocr_texts" in prompt_text
    assert "早上来不及吃饭？" in prompt_text
    assert "transcript_texts" in prompt_text
    assert posted["headers"]["Authorization"] == "Bearer test-secret-key"


def test_understand_shots_with_ai_filters_repeated_and_noisy_ocr_from_prompt(monkeypatch, tmp_path):
    from app.video_understanding.schemas import (
        AnalysisUnit,
        FrameEvidence,
        FrameOCRText,
        ShotEvidenceGraph,
        ShotEvidenceNode,
        VideoShot,
    )
    from app.video_understanding.shot_understanding_service import understand_shots_with_ai

    monkeypatch.setenv("OPENAI_API_KEY", "test-secret-key")
    posted = {}
    frame_path = tmp_path / "unit.jpg"
    frame_path.write_bytes(b"\xff\xd8fake-jpeg\xff\xd9")
    frame = FrameEvidence(
        shot_index=1,
        frame_index=1,
        time=0.5,
        role="middle",
        local_path=str(frame_path),
        public_url="/keyframes/unit.jpg",
    )
    ocr_texts = [
        FrameOCRText(shot_index=1, frame_index=1, frame_time=0.5, text="小红书", confidence=0.99),
        FrameOCRText(shot_index=1, frame_index=2, frame_time=0.8, text="小红书", confidence=0.98),
        FrameOCRText(shot_index=1, frame_index=1, frame_time=0.5, text="QX×x_L", confidence=0.82),
        FrameOCRText(shot_index=1, frame_index=1, frame_time=0.5, text="SALE", confidence=0.93),
        FrameOCRText(shot_index=1, frame_index=1, frame_time=0.5, text="限时优惠", confidence=0.88),
    ]
    shot_node = ShotEvidenceNode(
        shot=VideoShot(index=1, start=0, end=2, duration=2, keyframe_time=1),
        frames=[frame],
        ocr_texts=ocr_texts,
    )
    graph = ShotEvidenceGraph(
        shots=[shot_node],
        analysis_units=[
            AnalysisUnit(
                unit_id="unit_1",
                shot_indices=[1],
                start=0,
                end=2,
                duration=2,
                representative_frames=[frame],
                ocr_texts=ocr_texts,
            )
        ],
    )

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "output_text": (
                    '{"visual_summary":"有字幕包装的画面","text_summary":"限时优惠",'
                    '"subject":"产品","scene":"营销画面","action":"展示",'
                    '"packaging_signals":["字幕"],"creative_function_hint":"offer",'
                    '"confidence":0.72,"warnings":[]}'
                )
            }

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def post(self, url, *, headers, json):
            posted["prompt"] = json["input"][0]["content"][0]["text"]
            return FakeResponse()

    monkeypatch.setattr("app.video_understanding.shot_understanding_service.httpx.Client", FakeClient)

    understand_shots_with_ai(graph)

    prompt = posted["prompt"]
    assert prompt.count("小红书") == 1
    assert "限时优惠" in prompt
    assert "SALE" in prompt
    assert "QX×x_L" not in prompt


def test_understand_shots_with_ai_prefers_analysis_units_over_per_shot_calls(monkeypatch, tmp_path):
    from app.video_understanding.schemas import AnalysisUnit, FrameEvidence, ShotEvidenceGraph, ShotEvidenceNode, VideoShot
    from app.video_understanding.shot_understanding_service import understand_shots_with_ai

    monkeypatch.setenv("OPENAI_API_KEY", "test-secret-key")
    frame_path = tmp_path / "unit.jpg"
    frame_path.write_bytes(b"\xff\xd8fake-jpeg\xff\xd9")
    shots = [
        ShotEvidenceNode(
            shot=VideoShot(
                index=index,
                start=round((index - 1) * 0.5, 3),
                end=round(index * 0.5, 3),
                duration=0.5,
                keyframe_time=round((index - 0.5) * 0.5, 3),
            ),
            frames=[
                FrameEvidence(
                    shot_index=index,
                    frame_index=1,
                    time=round((index - 0.5) * 0.5, 3),
                    role="middle",
                    local_path=str(frame_path),
                    public_url=f"/keyframes/shot_{index}.jpg",
                )
            ],
        )
        for index in range(1, 21)
    ]
    units = [
        AnalysisUnit(
            unit_id="unit_1",
            shot_indices=[node.shot.index for node in shots[:8]],
            start=0,
            end=4,
            duration=4,
            representative_frames=[shots[0].frames[0], shots[3].frames[0], shots[7].frames[0]],
        ),
        AnalysisUnit(
            unit_id="unit_2",
            shot_indices=[node.shot.index for node in shots[8:16]],
            start=4,
            end=8,
            duration=4,
            representative_frames=[shots[8].frames[0], shots[12].frames[0], shots[15].frames[0]],
        ),
        AnalysisUnit(
            unit_id="unit_3",
            shot_indices=[node.shot.index for node in shots[16:]],
            start=8,
            end=10,
            duration=2,
            representative_frames=[shots[16].frames[0], shots[-1].frames[0]],
        ),
    ]
    graph = ShotEvidenceGraph(shots=shots, analysis_units=units)
    calls = {"count": 0, "prompts": []}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "output_text": (
                    '{"visual_summary":"一组连续快切展示产品","text_summary":"",'
                    '"subject":"产品","scene":"快切片段","action":"展示",'
                    '"packaging_signals":["快切"],"creative_function_hint":"product_demo",'
                    '"confidence":0.72,"warnings":[]}'
                )
            }

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def post(self, url, *, headers, json):
            calls["count"] += 1
            calls["prompts"].append(json["input"][0]["content"][0]["text"])
            return FakeResponse()

    monkeypatch.setattr("app.video_understanding.shot_understanding_service.httpx.Client", FakeClient)

    understood = understand_shots_with_ai(graph)

    assert calls["count"] == 3
    assert "unit_id=unit_1" in calls["prompts"][0]
    assert "shot_indices=[1, 2, 3, 4, 5, 6, 7, 8]" in calls["prompts"][0]
    assert [unit.understanding.visual_summary for unit in understood.analysis_units] == [
        "一组连续快切展示产品",
        "一组连续快切展示产品",
        "一组连续快切展示产品",
    ]
    assert understood.shots[0].understanding.visual_summary == "一组连续快切展示产品"
    assert understood.shots[19].understanding.creative_function_hint == "product_demo"


def test_understand_shots_with_ai_requires_openai_api_key(monkeypatch):
    from app.video_understanding.schemas import ShotEvidenceGraph, ShotEvidenceNode, VideoShot
    from app.video_understanding.shot_understanding_service import understand_shots_with_ai

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    graph = ShotEvidenceGraph(
        shots=[
            ShotEvidenceNode(
                shot=VideoShot(index=1, start=0, end=2, duration=2, keyframe_time=1),
            )
        ]
    )

    with pytest.raises(RuntimeError, match="OPENAI_API_KEY is required"):
        understand_shots_with_ai(graph)


def test_understand_shots_with_ai_retries_transient_503(monkeypatch, tmp_path):
    from app.video_understanding.schemas import FrameEvidence, ShotEvidenceGraph, ShotEvidenceNode, VideoShot
    from app.video_understanding.shot_understanding_service import understand_shots_with_ai

    monkeypatch.setenv("OPENAI_API_KEY", "test-secret-key")
    monkeypatch.setattr("app.video_understanding.shot_understanding_service.RETRY_SLEEP_SECONDS", 0)
    frame_path = tmp_path / "shot.jpg"
    frame_path.write_bytes(b"\xff\xd8fake-jpeg\xff\xd9")
    graph = ShotEvidenceGraph(
        shots=[
            ShotEvidenceNode(
                shot=VideoShot(index=1, start=0, end=2, duration=2, keyframe_time=1),
                frames=[
                    FrameEvidence(
                        shot_index=1,
                        frame_index=1,
                        time=1,
                        role="middle",
                        local_path=str(frame_path),
                        public_url="/keyframes/shot.jpg",
                    )
                ],
            )
        ]
    )
    calls = {"count": 0}

    class RetryableResponse:
        status_code = 503
        text = '{"error":{"message":"Service temporarily unavailable"}}'

        def raise_for_status(self):
            request = httpx.Request("POST", "https://relay.example.com/v1/responses")
            response = httpx.Response(
                status_code=503,
                json={"error": {"message": "Service temporarily unavailable"}},
                request=request,
            )
            raise httpx.HTTPStatusError("service unavailable", request=request, response=response)

    class SuccessResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "output_text": (
                    '{"visual_summary":"产品特写","subject":"产品","scene":"桌面",'
                    '"action":"展示","packaging_signals":[],"creative_function_hint":"product_intro",'
                    '"confidence":0.7,"warnings":[]}'
                )
            }

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def post(self, url, *, headers, json):
            calls["count"] += 1
            if calls["count"] == 1:
                return RetryableResponse()
            return SuccessResponse()

    monkeypatch.setattr("app.video_understanding.shot_understanding_service.httpx.Client", FakeClient)

    understood = understand_shots_with_ai(graph)

    assert calls["count"] == 2
    assert understood.shots[0].understanding.visual_summary == "产品特写"
    assert understood.shots[0].understanding.confidence == 0.7


def test_understand_shots_with_ai_uses_vision_model_when_shot_model_is_unset(monkeypatch, tmp_path):
    from app.video_understanding.schemas import FrameEvidence, ShotEvidenceGraph, ShotEvidenceNode, VideoShot
    from app.video_understanding.shot_understanding_service import understand_shots_with_ai

    monkeypatch.setenv("OPENAI_API_KEY", "test-secret-key")
    monkeypatch.setenv("REELSTRUCT_VISION_MODEL", "relay-vision-model")
    monkeypatch.delenv("REELSTRUCT_SHOT_UNDERSTANDING_MODEL", raising=False)
    posted = {}
    frame_path = tmp_path / "shot.jpg"
    frame_path.write_bytes(b"\xff\xd8fake-jpeg\xff\xd9")
    graph = ShotEvidenceGraph(
        shots=[
            ShotEvidenceNode(
                shot=VideoShot(index=1, start=0, end=2, duration=2, keyframe_time=1),
                frames=[
                    FrameEvidence(
                        shot_index=1,
                        frame_index=1,
                        time=1,
                        role="middle",
                        local_path=str(frame_path),
                        public_url="/keyframes/shot.jpg",
                    )
                ],
            )
        ]
    )

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "output_text": (
                    '{"visual_summary":"产品特写","subject":"产品","scene":"桌面",'
                    '"action":"展示","packaging_signals":[],"creative_function_hint":"product_intro",'
                    '"confidence":0.7,"warnings":[]}'
                )
            }

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def post(self, url, *, headers, json):
            posted["json"] = json
            return FakeResponse()

    monkeypatch.setattr("app.video_understanding.shot_understanding_service.httpx.Client", FakeClient)

    understand_shots_with_ai(graph)

    assert posted["json"]["model"] == "relay-vision-model"


def test_understand_shots_with_ai_degrades_shot_after_repeated_503(monkeypatch, tmp_path):
    from app.video_understanding.schemas import FrameEvidence, ShotEvidenceGraph, ShotEvidenceNode, VideoShot
    from app.video_understanding.shot_understanding_service import understand_shots_with_ai

    monkeypatch.setenv("OPENAI_API_KEY", "test-secret-key")
    monkeypatch.setattr("app.video_understanding.shot_understanding_service.RETRY_SLEEP_SECONDS", 0)
    frame_path = tmp_path / "shot.jpg"
    frame_path.write_bytes(b"\xff\xd8fake-jpeg\xff\xd9")
    graph = ShotEvidenceGraph(
        shots=[
            ShotEvidenceNode(
                shot=VideoShot(index=1, start=0, end=2, duration=2, keyframe_time=1),
                frames=[
                    FrameEvidence(
                        shot_index=1,
                        frame_index=1,
                        time=1,
                        role="middle",
                        local_path=str(frame_path),
                        public_url="/keyframes/shot.jpg",
                    )
                ],
            )
        ]
    )

    class RetryableResponse:
        status_code = 503
        text = '{"error":{"message":"Service temporarily unavailable"}}'

        def raise_for_status(self):
            request = httpx.Request("POST", "https://relay.example.com/v1/responses")
            response = httpx.Response(
                status_code=503,
                json={"error": {"message": "Service temporarily unavailable"}},
                request=request,
            )
            raise httpx.HTTPStatusError("service unavailable", request=request, response=response)

    class FakeClient:
        def __init__(self, **kwargs):
            self.calls = 0

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def post(self, url, *, headers, json):
            self.calls += 1
            return RetryableResponse()

    monkeypatch.setattr("app.video_understanding.shot_understanding_service.httpx.Client", FakeClient)

    understood = understand_shots_with_ai(graph)

    warning = understood.shots[0].understanding.warnings[0]
    assert understood.shots[0].understanding.confidence == 0
    assert "shot understanding failed" in warning
    assert "status=503" in warning


@pytest.mark.parametrize(
    "wrapped_json",
    [
        '```json\n{"visual_summary":"A","confidence":0.4}\n```',
        '```JSON\n{"visual_summary":"A","confidence":0.4}\n```',
        '``` json\n{"visual_summary":"A","confidence":0.4}\n```',
    ],
)
def test_parse_json_output_accepts_json_fence_variants(wrapped_json):
    from app.video_understanding.ai_vision_service import _parse_json_output

    parsed = _parse_json_output(wrapped_json, shot_index=1)

    assert parsed["visual_summary"] == "A"
    assert parsed["confidence"] == 0.4


def test_parse_graph_segments_accepts_valid_json():
    from app.video_understanding.ai_graph_service import parse_graph_segments

    result = parse_graph_segments(
        {
            "relations": [
                {
                    "from_shot": 1,
                    "to_shot": 2,
                    "relation_type": "contrast",
                    "relation_summary": "开场痛点到解决方案",
                    "rhythm_change": "快到中",
                    "semantic_shift": "痛点转解决",
                    "confidence": 0.81,
                }
            ],
            "beats": [
                {
                    "beat_id": "beat_1",
                    "label": "Hook",
                    "shot_indices": [1],
                    "start": 0.0,
                    "end": 2.0,
                    "function": "hook",
                    "reason": "用提问引入",
                    "confidence": 0.92,
                }
            ],
            "segments": [
                {
                    "segment_id": "seg_1",
                    "label": "Hook",
                    "beat_ids": ["beat_1"],
                    "shot_indices": [1],
                    "start": 0.0,
                    "end": 2.0,
                    "purpose": "吸引注意",
                    "method": "痛点提问",
                    "evidence": ["shot 1 transcript: 熬夜脸很垮？"],
                    "rhythm": "快",
                    "packaging": "大字幕",
                    "transferable_rule": "先抛问题",
                    "non_transferable": "原商品名",
                    "required_asset": "痛点场景",
                    "confidence": 0.88,
                }
            ],
            "rhythm_structure": {
                "summary": "前 3 秒快进入，中段放慢展示过程。",
                "avg_shot_duration": 1.42,
                "cut_density": "fast",
                "fast_windows": ["0.0-3.0"],
                "slow_windows": ["6.0-9.0"],
                "peak_position": "2.0-3.0",
                "slowdown_position": "6.0-9.0",
                "rhythm_curve": [
                    {"start": 0.0, "end": 3.0, "shot_count": 4, "density": "fast", "note": "hook 快切"}
                ],
                "segment_notes": [
                    {"segment_id": "seg_1", "note": "Hook 使用快切制造停留"}
                ],
            },
            "packaging_structure": {
                "caption_density": "高",
                "title_style": "开场大字幕",
                "transition_style": "硬切",
                "cover_style": "结果画面 + 强标题",
                "text_layout": "底部字幕 + 中部大标题",
                "title_cards": ["0.0-1.5 出现大标题"],
                "sticker_signals": ["价格标签"],
                "packaging_timeline": [
                    {"start": 0.0, "end": 2.0, "type": "title_card", "evidence": "shot 1 OCR 大字"}
                ],
            },
            "warnings": ["evidence should stay grounded"],
        }
    )

    assert result.relations[0].relation_type == "contrast"
    assert result.beats[0].beat_id == "beat_1"
    assert result.segments[0].evidence == ["shot 1 transcript: 熬夜脸很垮？"]
    assert result.rhythm_structure.summary == "前 3 秒快进入，中段放慢展示过程。"
    assert result.rhythm_structure.cut_density == "fast"
    assert result.rhythm_structure.rhythm_curve[0].shot_count == 4
    assert result.packaging_structure.caption_density == "高"
    assert result.packaging_structure.packaging_timeline[0].type == "title_card"
    assert result.warnings == ["evidence should stay grounded"]


def test_build_graph_prompt_requires_chinese_natural_language_values():
    from app.video_understanding.ai_graph_service import _build_graph_prompt
    from app.video_understanding.schemas import VideoShot
    from app.video_understanding.shot_evidence_graph import build_initial_shot_evidence_graph

    graph = build_initial_shot_evidence_graph(
        shots=[VideoShot(index=1, start=0, end=2, duration=2, keyframe_time=1)],
        frames=[],
    )

    prompt = _build_graph_prompt(graph)

    assert "JSON 字段名保持英文" in prompt
    assert "所有自然语言字段的值必须使用简体中文" in prompt
    assert "禁止输出英文标签" in prompt
    assert "Only 2 shots are available" in prompt
    assert "必须改写成简体中文" in prompt
    assert "不能输出 analysis_units.unit_1.understanding.visual_summary" in prompt
    assert "分析单元 1 的画面理解" in prompt


def test_graph_aggregation_detects_mixed_english_user_facing_text():
    from app.video_understanding.ai_graph_service import _needs_chinese_rewrite

    assert _needs_chinese_rewrite(
        {
            "warnings": [
                "镜头 1 contains OCR recognition errors in some English and a few Chinese fragments.",
                "Rhythm inference is limited by sparse shot count and lacks finer intra-shot motion timing evidence.",
            ]
        }
    )


def test_graph_aggregation_detects_english_packaging_structure_text():
    from app.video_understanding.ai_graph_service import _needs_chinese_rewrite

    assert _needs_chinese_rewrite(
        {
            "packaging_structure": {
                "title_style": "镜头 1 uses large bilingual title typography and keyword display",
            }
        }
    )
    assert _needs_chinese_rewrite({"packaging_structure": {"caption_density": "high in 镜头 1, medium in 镜头 2"}})
    assert _needs_chinese_rewrite(
        {
            "packaging_structure": {
                "caption_density": "high in 镜头 1, medium in 镜头 2",
                "title_style": (
                    "镜头 1 uses large bilingual title typography and keyword display; "
                    "镜头 2 uses centered account/brand text in end-card style"
                ),
                "transition_style": "硬切 from 镜头 1 to 镜头 2 evidenced by relation 'adjacent cut'",
                "cover_style": (
                    "opening has obvious poster-like cover packaging; "
                    "ending has platform account redirect end-card style"
                ),
                "text_layout": (
                    "镜头 1 features dense multi-zone text layout with large title blocks and time/location lines"
                ),
            }
        }
    )


def test_shot_understanding_prompts_require_chinese_natural_language_values():
    from app.video_understanding.schemas import AnalysisUnit, VideoShot
    from app.video_understanding.shot_evidence_graph import build_initial_shot_evidence_graph
    from app.video_understanding.shot_understanding_service import _build_prompt, _build_unit_prompt

    graph = build_initial_shot_evidence_graph(
        shots=[VideoShot(index=1, start=0, end=2, duration=2, keyframe_time=1)],
        frames=[],
    )
    unit = AnalysisUnit(unit_id="unit_1", shot_indices=[1], start=0, end=2, duration=2)

    shot_prompt = _build_prompt(graph.shots[0])
    unit_prompt = _build_unit_prompt(unit)

    assert "所有自然语言字段的值必须使用简体中文" in shot_prompt
    assert "creative_function_hint 只能保留下面列出的英文枚举值" in shot_prompt
    assert "所有自然语言字段的值必须使用简体中文" in unit_prompt


def test_apply_graph_aggregation_preserves_rhythm_and_packaging_structures():
    from app.video_understanding.schemas import (
        GraphAggregationResult,
        GraphPackagingStructure,
        GraphRhythmStructure,
        PackagingTimelineItem,
        RhythmCurvePoint,
        VideoShot,
    )
    from app.video_understanding.shot_evidence_graph import apply_graph_aggregation, build_initial_shot_evidence_graph

    graph = build_initial_shot_evidence_graph(
        shots=[VideoShot(index=1, start=0, end=2, duration=2, keyframe_time=1)],
        frames=[],
    )
    aggregation = GraphAggregationResult(
        rhythm_structure=GraphRhythmStructure(
            summary="开场快节奏",
            cut_density="fast",
            rhythm_curve=[RhythmCurvePoint(start=0, end=2, shot_count=1, density="fast", note="单镜头快进入")],
        ),
        packaging_structure=GraphPackagingStructure(
            caption_density="高",
            title_style="大标题",
            packaging_timeline=[PackagingTimelineItem(start=0, end=2, type="title_card", evidence="OCR 大字")],
        ),
    )

    merged = apply_graph_aggregation(graph, aggregation)

    assert merged.rhythm_structure.summary == "开场快节奏"
    assert merged.rhythm_structure.rhythm_curve[0].density == "fast"
    assert merged.packaging_structure.title_style == "大标题"
    assert merged.packaging_structure.packaging_timeline[0].evidence == "OCR 大字"


def test_parse_graph_segments_normalizes_common_ai_field_aliases():
    from app.video_understanding.ai_graph_service import parse_graph_segments

    result = parse_graph_segments(
        {
            "relations": [
                {
                    "from_shot": 1,
                    "to_shot": 2,
                    "type": "adjacent_cut",
                    "evidence": ["shot 1 ends at 10.083", "shot 2 starts at 10.083"],
                    "through_shots": [3],
                }
            ],
            "beats": [
                {
                    "beat_index": 1,
                    "label": "Opening beat",
                    "shot_indices": [1, 2],
                    "evidence": ["shot 1 duration is 10.083"],
                }
            ],
            "segments": [
                {
                    "segment_index": 1,
                    "label": "Opening segment",
                    "shot_indices": [1, 2],
                    "evidence": [
                        {"source": "shots[0].shot", "text": "shot 1 duration is 10.083"},
                        "timeline adjacent cut",
                    ],
                }
            ],
        }
    )

    assert result.relations[0].relation_type == "adjacent_cut"
    assert "shot 1 ends at 10.083" in result.relations[0].relation_summary
    assert result.beats[0].beat_id == "beat_1"
    assert result.beats[0].start == 0
    assert result.beats[0].end == 0
    assert result.segments[0].segment_id == "seg_1"
    assert result.segments[0].evidence[0] == "shots[0].shot: shot 1 duration is 10.083"


def test_parse_graph_segments_infers_missing_time_ranges_from_graph_shots():
    from app.video_understanding.ai_graph_service import parse_graph_segments
    from app.video_understanding.shot_evidence_graph import build_initial_shot_evidence_graph

    graph = build_initial_shot_evidence_graph(
        shots=[
            VideoShot(index=1, start=0, end=2, duration=2, keyframe_time=1),
            VideoShot(index=2, start=2, end=5, duration=3, keyframe_time=3.5),
            VideoShot(index=3, start=5, end=7, duration=2, keyframe_time=6),
        ],
        frames=[],
    )

    result = parse_graph_segments(
        {
            "beats": [{"beat_index": 1, "label": "Bridge", "shot_indices": [2, 3]}],
            "segments": [{"segment_index": 1, "label": "Demo", "shot_indices": [2, 3]}],
        },
        graph=graph,
    )

    assert result.beats[0].start == 2
    assert result.beats[0].end == 7
    assert result.segments[0].start == 2
    assert result.segments[0].end == 7


@pytest.mark.parametrize(
    "wrapped_json",
    [
        '```json\n{"relations":[],"beats":[],"segments":[],"warnings":["ok"]}\n```',
        '```JSON\n{"relations":[],"beats":[],"segments":[],"warnings":["ok"]}\n```',
        '``` json\n{"relations":[],"beats":[],"segments":[],"warnings":["ok"]}\n```',
    ],
)
def test_parse_graph_segments_accepts_json_fence_variants(wrapped_json):
    from app.video_understanding.ai_graph_service import _parse_json_output

    parsed = _parse_json_output(wrapped_json)

    assert parsed["warnings"] == ["ok"]


def test_aggregate_graph_structure_with_ai_parses_responses_output_content(monkeypatch):
    from app.video_understanding.ai_graph_service import aggregate_graph_structure_with_ai
    from app.video_understanding.shot_evidence_graph import build_initial_shot_evidence_graph

    graph = build_initial_shot_evidence_graph(
        shots=[VideoShot(index=1, start=0, end=2, duration=2, keyframe_time=1)],
        frames=[],
    )
    response_payload = {
        "output": [
            {
                "content": [
                    {
                        "type": "output_text",
                        "text": '```json\n{"warnings":["partial graph"],"segments":[]}\n```',
                    }
                ]
            }
        ]
    }

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return response_payload

    fake_client = Mock()
    fake_client.__enter__ = Mock(return_value=fake_client)
    fake_client.__exit__ = Mock(return_value=False)
    fake_client.post = Mock(return_value=FakeResponse())
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr("app.video_understanding.ai_graph_service.httpx.Client", Mock(return_value=fake_client))

    result = aggregate_graph_structure_with_ai(graph)

    assert result.warnings == ["partial graph"]
    assert result.relations == []
    assert fake_client.post.call_args.kwargs["headers"]["Authorization"] == "Bearer test-key"


def test_aggregate_graph_structure_with_ai_retries_transient_503(monkeypatch):
    from app.video_understanding.ai_graph_service import aggregate_graph_structure_with_ai
    from app.video_understanding.shot_evidence_graph import build_initial_shot_evidence_graph

    graph = build_initial_shot_evidence_graph(
        shots=[VideoShot(index=1, start=0, end=2, duration=2, keyframe_time=1)],
        frames=[],
    )
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr("app.video_understanding.ai_graph_service.RETRY_SLEEP_SECONDS", 0)
    calls = {"count": 0}

    class RetryableResponse:
        status_code = 503
        text = '{"error":{"message":"Service temporarily unavailable"}}'

        def raise_for_status(self):
            request = httpx.Request("POST", "https://relay.example.com/v1/responses")
            response = httpx.Response(
                status_code=503,
                json={"error": {"message": "Service temporarily unavailable"}},
                request=request,
            )
            raise httpx.HTTPStatusError("service unavailable", request=request, response=response)

    class SuccessResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"output_text": '{"warnings":["ok"],"segments":[]}'}

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def post(self, url, *, headers, json):
            calls["count"] += 1
            if calls["count"] == 1:
                return RetryableResponse()
            return SuccessResponse()

    monkeypatch.setattr("app.video_understanding.ai_graph_service.httpx.Client", FakeClient)

    result = aggregate_graph_structure_with_ai(graph)

    assert calls["count"] == 2
    assert result.warnings == ["ok"]


def test_aggregate_graph_structure_with_ai_rewrites_english_warnings(monkeypatch):
    from app.video_understanding.ai_graph_service import aggregate_graph_structure_with_ai
    from app.video_understanding.shot_evidence_graph import build_initial_shot_evidence_graph

    graph = build_initial_shot_evidence_graph(
        shots=[VideoShot(index=1, start=0, end=2, duration=2, keyframe_time=1)],
        frames=[],
    )
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    posted_payloads = []

    class FakeResponse:
        def __init__(self, output_text):
            self.output_text = output_text

        def raise_for_status(self):
            return None

        def json(self):
            return {"output_text": self.output_text}

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def post(self, url, *, headers, json):
            posted_payloads.append(json)
            if len(posted_payloads) == 1:
                return FakeResponse('{"warnings":["Only 2 shots are available, so beat/segment granularity is coarse."],"segments":[]}')
            return FakeResponse('{"warnings":["当前只有 2 个镜头可用，节拍和段落划分粒度会比较粗。"],"segments":[]}')

    monkeypatch.setattr("app.video_understanding.ai_graph_service.httpx.Client", FakeClient)

    result = aggregate_graph_structure_with_ai(graph)

    assert len(posted_payloads) == 2
    assert "请把以下 JSON 中面向用户展示的英文说明改写为简体中文" in posted_payloads[1]["input"][0]["content"][0]["text"]
    assert result.warnings == ["当前只有 2 个镜头可用，节拍和段落划分粒度会比较粗。"]


def test_parse_graph_segments_defaults_missing_collections_to_empty_lists():
    from app.video_understanding.ai_graph_service import parse_graph_segments

    result = parse_graph_segments({"warnings": ["partial output"]})

    assert result.relations == []
    assert result.beats == []
    assert result.segments == []
    assert result.warnings == ["partial output"]


def test_apply_graph_aggregation_replaces_graph_parts_and_appends_warnings():
    from app.video_understanding.schemas import GraphAggregationResult, ShotRelation
    from app.video_understanding.shot_evidence_graph import (
        apply_graph_aggregation,
        build_initial_shot_evidence_graph,
    )

    graph = build_initial_shot_evidence_graph(
        shots=[
            VideoShot(index=1, start=0, end=2, duration=2, keyframe_time=1),
            VideoShot(index=2, start=2, end=4, duration=2, keyframe_time=3),
        ],
        frames=[],
    ).model_copy(
        update={
            "relations": [
                ShotRelation(
                    from_shot=1,
                    to_shot=2,
                    relation_type="old",
                    relation_summary="old relation",
                )
            ],
            "warnings": ["existing warning"],
        }
    )

    aggregation = GraphAggregationResult(
        relations=[ShotRelation(from_shot=1, to_shot=2, relation_type="new")],
        beats=[],
        segments=[],
        warnings=["existing warning", "new warning"],
    )

    merged = apply_graph_aggregation(graph, aggregation)

    assert [relation.relation_type for relation in merged.relations] == ["new"]
    assert merged.warnings == ["existing warning", "existing warning", "new warning"]
    assert merged.beats == []
    assert merged.segments == []


def test_apply_graph_aggregation_preserves_existing_relations_when_ai_returns_none():
    from app.video_understanding.schemas import GraphAggregationResult, ShotEvidenceGraph, ShotRelation
    from app.video_understanding.shot_evidence_graph import apply_graph_aggregation

    graph = ShotEvidenceGraph(
        shots=[],
        relations=[
            ShotRelation(
                from_shot=1,
                to_shot=2,
                relation_type="adjacent_cut",
                relation_summary="baseline temporal continuity",
            )
        ],
    )
    aggregation = GraphAggregationResult(relations=[], warnings=["only partial evidence"])

    merged = apply_graph_aggregation(graph, aggregation)

    assert [relation.relation_type for relation in merged.relations] == ["adjacent_cut"]
    assert merged.warnings == ["only partial evidence"]


def test_decompose_video_structure_with_ai_requires_openai_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    from app.video_understanding.ai_structure_service import decompose_video_structure_with_ai

    with pytest.raises(RuntimeError, match="OPENAI_API_KEY is required"):
        decompose_video_structure_with_ai(
            title="护肤样例",
            signal=_sample_signal(),
            evidence=_sample_shot_evidence(),
            transcript_summary="开头提出痛点。中段展示效果。结尾引导下单。",
        )


def test_decompose_video_structure_with_ai_posts_prompt_and_returns_analysis(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-secret-key")
    posted = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "output_text": (
                    '{"source":"ai","headline":"痛点种草型结构","segments":[{"id":"seg_1","label":"痛点 Hook",'
                    '"type":"hook","start":0.0,"end":3.0,"shot_indices":[1],"purpose":"吸引停留",'
                    '"method":"痛点提问+大标题","evidence":"第1镜头出现痛点字幕","rhythm":"快进入",'
                    '"packaging":"大标题","required_asset":"开头近景","transferable_rule":"先抛问题",'
                    '"non_transferable":"不要照搬商品名","confidence":0.88}],"rhythm_structure":{"summary":"前段快进入"},'
                    '"packaging_structure":{"caption_density":"高","title_style":"开头大标题"},'
                    '"confidence":0.83,"warnings":[]}'
                )
            }

    class FakeClient:
        def __init__(self, **kwargs):
            posted["client_kwargs"] = kwargs

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def post(self, url, *, headers, json):
            posted["url"] = url
            posted["headers"] = headers
            posted["json"] = json
            return FakeResponse()

    monkeypatch.setattr("app.video_understanding.ai_structure_service.httpx.Client", FakeClient)

    from app.video_understanding.ai_structure_service import decompose_video_structure_with_ai

    analysis = decompose_video_structure_with_ai(
        title="护肤样例",
        signal=_sample_signal(),
        evidence=_sample_shot_evidence(),
        transcript_summary="开头提出痛点。中段展示效果。结尾引导下单。",
    )

    assert analysis.source == "ai"
    assert analysis.headline == "痛点种草型结构"
    assert analysis.segments[0].shot_indices == [1]
    assert analysis.rhythm_structure.summary == "前段快进入"
    assert analysis.packaging_structure.caption_density == "高"
    assert posted["headers"]["Authorization"] == "Bearer test-secret-key"
    assert "test-secret-key" not in str(posted["json"])
    assert "shot_evidence" in posted["json"]["input"][0]["content"][0]["text"]


def test_decompose_video_structure_with_ai_accepts_numeric_segment_ids(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-secret-key")

    _install_fake_structure_response(
        monkeypatch,
        {
            "output_text": (
                '{"source":"ai","headline":"痛点种草型结构","segments":[{"id":1,"label":"痛点开场",'
                '"type":"开场","start":0.0,"end":3.0,"shot_indices":[1],"purpose":"吸引停留",'
                '"method":"痛点提问","evidence":"第1镜头出现痛点字幕","rhythm":"快进入",'
                '"packaging":"大标题","required_asset":"开头近景","transferable_rule":"先抛问题",'
                '"non_transferable":"不要照搬商品名","confidence":0.88}],'
                '"rhythm_structure":{"summary":"前段快进入"},'
                '"packaging_structure":{"caption_density":"高"},'
                '"confidence":0.83,"warnings":[]}'
            )
        },
    )

    from app.video_understanding.ai_structure_service import decompose_video_structure_with_ai

    analysis = decompose_video_structure_with_ai(
        title="护肤样例",
        signal=_sample_signal(),
        evidence=_sample_shot_evidence(),
        transcript_summary="开头提出痛点。中段展示效果。结尾引导下单。",
    )

    assert analysis.segments[0].id == "1"


def test_decompose_video_structure_with_ai_uses_openai_base_url(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-secret-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://relay.example.com/v1")
    posted = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "output_text": (
                    '{"source":"ai","headline":"痛点种草型结构","segments":[{"id":"seg_1","label":"痛点 Hook",'
                    '"type":"hook","start":0.0,"end":3.0,"shot_indices":[1],"purpose":"吸引停留",'
                    '"method":"痛点提问+大标题","evidence":"第1镜头出现痛点字幕","rhythm":"快进入",'
                    '"packaging":"大标题","required_asset":"开头近景","transferable_rule":"先抛问题",'
                    '"non_transferable":"不要照搬商品名","confidence":0.88}],"rhythm_structure":{"summary":"前段快进入"},'
                    '"packaging_structure":{"caption_density":"高","title_style":"开头大标题"},'
                    '"confidence":0.83,"warnings":[]}'
                )
            }

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def post(self, url, *, headers, json):
            posted["url"] = url
            return FakeResponse()

    monkeypatch.setattr("app.video_understanding.ai_structure_service.httpx.Client", FakeClient)

    from app.video_understanding.ai_structure_service import decompose_video_structure_with_ai

    decompose_video_structure_with_ai(
        title="护肤样例",
        signal=_sample_signal(),
        evidence=_sample_shot_evidence(),
        transcript_summary="开头提出痛点。中段展示效果。结尾引导下单。",
    )

    assert posted["url"] == "https://relay.example.com/v1/responses"


@pytest.mark.parametrize(
    ("start", "end", "shot_indices", "match"),
    [
        (2.0, 2.0, [1], "end"),
        (3.0, 2.0, [1], "end"),
        (0.0, 2.0, [0], "shot_indices"),
        (0.0, 2.0, [-1], "shot_indices"),
    ],
)
def test_ai_structure_analysis_schema_rejects_invalid_segment_ranges_and_shot_indices(start, end, shot_indices, match):
    with pytest.raises(ValidationError, match=match):
        AIStructureAnalysis.model_validate(
            {
                "source": "ai",
                "headline": "结构",
                "segments": [
                    {
                        "id": "seg_1",
                        "label": "Hook",
                        "type": "hook",
                        "start": start,
                        "end": end,
                        "shot_indices": shot_indices,
                        "purpose": "吸引",
                        "method": "提问",
                        "evidence": "第1镜头",
                        "rhythm": "快",
                        "packaging": "大标题",
                        "transferable_rule": "先提问",
                        "non_transferable": "商品名",
                        "confidence": 0.7,
                    }
                ],
                "confidence": 0.6,
            }
        )


def test_ai_structure_analysis_schema_forbids_extra_fields():
    with pytest.raises(ValidationError, match="extra_forbidden"):
        AIStructureAnalysis.model_validate(
            {
                "source": "ai",
                "headline": "结构",
                "segments": [
                    {
                        "id": "seg_1",
                        "label": "Hook",
                        "type": "hook",
                        "start": 0,
                        "end": 2,
                        "shot_indices": [1],
                        "purpose": "吸引",
                        "method": "提问",
                        "evidence": "第1镜头",
                        "rhythm": "快",
                        "packaging": "大标题",
                        "transferable_rule": "先提问",
                        "non_transferable": "商品名",
                        "confidence": 0.7,
                        "unexpected_segment_field": "x",
                    }
                ],
                "rhythm_structure": {"summary": "前段快", "unexpected_rhythm_field": "x"},
                "packaging_structure": {"caption_density": "高", "unexpected_packaging_field": "x"},
                "confidence": 0.6,
                "unexpected_analysis_field": "x",
            }
        )


def test_decompose_video_structure_with_ai_wraps_http_status_error(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-secret-key")

    class FakeResponse:
        status_code = 429
        text = '{"error":{"message":"rate limited"}}'

        def raise_for_status(self):
            request = httpx.Request("POST", "https://api.openai.com/v1/responses")
            response = httpx.Response(
                status_code=429,
                json={"error": {"message": "rate limited"}},
                request=request,
            )
            raise httpx.HTTPStatusError("rate limited", request=request, response=response)

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def post(self, url, *, headers, json):
            return FakeResponse()

    monkeypatch.setattr("app.video_understanding.ai_structure_service.httpx.Client", FakeClient)

    from app.video_understanding.ai_structure_service import decompose_video_structure_with_ai

    with pytest.raises(RuntimeError, match="status=429.*rate limited"):
        decompose_video_structure_with_ai(
            title="护肤样例",
            signal=_sample_signal(),
            evidence=_sample_shot_evidence(),
            transcript_summary="开头提出痛点。中段展示效果。结尾引导下单。",
        )


def test_decompose_video_structure_with_ai_raises_value_error_when_output_text_is_missing(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-secret-key")
    _install_fake_structure_response(monkeypatch, {})

    from app.video_understanding.ai_structure_service import decompose_video_structure_with_ai

    with pytest.raises(ValueError, match="missing output_text"):
        decompose_video_structure_with_ai(
            title="护肤样例",
            signal=_sample_signal(),
            evidence=_sample_shot_evidence(),
            transcript_summary="开头提出痛点。中段展示效果。结尾引导下单。",
        )


def test_decompose_video_structure_with_ai_raises_value_error_when_output_text_is_not_json(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-secret-key")
    _install_fake_structure_response(monkeypatch, {"output_text": "not json"})

    from app.video_understanding.ai_structure_service import decompose_video_structure_with_ai

    with pytest.raises(ValueError, match="not valid JSON"):
        decompose_video_structure_with_ai(
            title="护肤样例",
            signal=_sample_signal(),
            evidence=_sample_shot_evidence(),
            transcript_summary="开头提出痛点。中段展示效果。结尾引导下单。",
        )


@pytest.mark.parametrize(
    "wrapped_json",
    [
        '```json\n{"source":"ai","headline":"结构","segments":[{"id":"seg_1","label":"Hook","type":"hook","start":0,"end":2,"shot_indices":[1],"purpose":"吸引","method":"提问","evidence":"第1镜头","rhythm":"快","packaging":"大标题","transferable_rule":"先提问","non_transferable":"商品名","confidence":0.7}],"confidence":0.6}\n```',
        '```JSON\n{"source":"ai","headline":"结构","segments":[{"id":"seg_1","label":"Hook","type":"hook","start":0,"end":2,"shot_indices":[1],"purpose":"吸引","method":"提问","evidence":"第1镜头","rhythm":"快","packaging":"大标题","transferable_rule":"先提问","non_transferable":"商品名","confidence":0.7}],"confidence":0.6}\n```',
        '``` json\n{"source":"ai","headline":"结构","segments":[{"id":"seg_1","label":"Hook","type":"hook","start":0,"end":2,"shot_indices":[1],"purpose":"吸引","method":"提问","evidence":"第1镜头","rhythm":"快","packaging":"大标题","transferable_rule":"先提问","non_transferable":"商品名","confidence":0.7}],"confidence":0.6}\n```',
    ],
)
def test_parse_ai_structure_json_output_accepts_json_fence_variants(wrapped_json):
    from app.video_understanding.ai_structure_service import _parse_json_output

    parsed = _parse_json_output(wrapped_json)

    assert parsed["source"] == "ai"
    assert parsed["segments"][0]["shot_indices"] == [1]


@pytest.mark.skipif(not os.getenv("OPENAI_API_KEY"), reason="requires real AI provider")
def test_decompose_video_structure_with_ai_returns_segments_with_shot_evidence():
    from app.video_understanding.ai_structure_service import decompose_video_structure_with_ai

    analysis = decompose_video_structure_with_ai(
        title="护肤样例",
        signal=_sample_signal(),
        evidence=_sample_shot_evidence(),
        transcript_summary="熬夜脸很垮？上脸清爽，第二天状态好很多。现在下单还有优惠。",
    )

    assert analysis.source == "ai"
    assert analysis.segments
    assert all(segment.shot_indices for segment in analysis.segments)
    assert analysis.rhythm_structure.summary
    assert analysis.packaging_structure.caption_density or analysis.packaging_structure.title_style


def test_analyze_keyframe_visuals_returns_real_model_descriptions(tmp_path):
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY is required for real OpenAI vision integration test")

    from app.video_understanding.ai_vision_service import analyze_keyframe_visuals

    fixture_path = Path(__file__).resolve().parents[3] / "fixtures" / "vid_001.mp4"
    signal = detect_video_signal(fixture_path)
    keyframes = extract_keyframes(
        fixture_path,
        signal.shots[:1],
        output_dir=tmp_path / "keyframes",
        public_prefix="/keyframes",
    )

    assert keyframes, "fixture video should produce at least one keyframe"

    analyses = analyze_keyframe_visuals(keyframes)

    assert len(analyses) == 1
    assert analyses[0].shot_index == keyframes[0].shot_index
    assert analyses[0].visual_summary.strip()
    assert analyses[0].confidence > 0


def _keyframe_with_image(tmp_path):
    image_path = tmp_path / "shot.jpg"
    image_path.write_bytes(b"\xff\xd8fake-jpeg\xff\xd9")
    return KeyframeEvidence(
        shot_index=1,
        keyframe_time=0.5,
        local_path=str(image_path),
        public_url="/keyframes/shot.jpg",
    )


def _install_fake_openai_response(monkeypatch, response_payload):
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return response_payload

    fake_client = Mock()
    fake_client.__enter__ = Mock(return_value=fake_client)
    fake_client.__exit__ = Mock(return_value=False)
    fake_client.post = Mock(return_value=FakeResponse())
    monkeypatch.setattr("app.video_understanding.ai_vision_service.httpx.Client", Mock(return_value=fake_client))


def _sample_signal() -> VideoSignal:
    return VideoSignal(
        metadata=VideoMetadata(duration=12, fps=30, width=1080, height=1920, format_name="mp4"),
        shot_count=3,
        shots=[
            VideoShot(index=1, start=0, end=3, duration=3, keyframe_time=1.5),
            VideoShot(index=2, start=3, end=9, duration=6, keyframe_time=6),
            VideoShot(index=3, start=9, end=12, duration=3, keyframe_time=10.5),
        ],
    )


def _sample_shot_evidence() -> list[ShotEvidence]:
    return [
        ShotEvidence(
            shot_index=1,
            start=0,
            end=3,
            duration=3,
            transcript_text="熬夜脸很垮？",
            visual_summary="人物近景，大标题字幕",
            packaging_signals=["大标题"],
        ),
        ShotEvidence(
            shot_index=2,
            start=3,
            end=9,
            duration=6,
            transcript_text="上脸清爽，第二天状态好很多。",
            visual_summary="产品特写和使用过程",
            packaging_signals=["卖点字幕"],
        ),
        ShotEvidence(
            shot_index=3,
            start=9,
            end=12,
            duration=3,
            transcript_text="现在下单还有优惠。",
            visual_summary="结尾停留，优惠信息字幕",
            packaging_signals=["CTA字幕"],
        ),
    ]


def _install_fake_structure_response(monkeypatch, response_payload):
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return response_payload

    fake_client = Mock()
    fake_client.__enter__ = Mock(return_value=fake_client)
    fake_client.__exit__ = Mock(return_value=False)
    fake_client.post = Mock(return_value=FakeResponse())
    monkeypatch.setattr("app.video_understanding.ai_structure_service.httpx.Client", Mock(return_value=fake_client))
