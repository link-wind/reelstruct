import os
from pathlib import Path
from unittest.mock import Mock

import httpx
import pytest

from app.video_understanding.keyframe_service import extract_keyframes
from app.video_understanding.schemas import KeyframeEvidence, ShotVisualAnalysis
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
