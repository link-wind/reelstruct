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
