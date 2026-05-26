from fastapi.testclient import TestClient
from pathlib import Path

from app.video_understanding.schemas import VideoMetadata, VideoShot, VideoSignal
from app.main import app


def test_upload_material_asset_returns_slot_bound_asset():
    client = TestClient(app)

    response = client.post(
        "/api/materials/upload",
        data={"slot_id": "selling_points"},
        files={"file": ("selling-points.mp4", b"uploaded material", "video/mp4")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["slot_id"] == "selling_points"
    assert body["filename"].endswith(".mp4")
    assert body["public_url"].startswith("/materials/")
    assert body["local_path"].endswith(body["filename"])


def test_upload_material_asset_returns_fit_analysis_for_recommended_slot():
    client = TestClient(app)
    fixture_path = Path(__file__).resolve().parents[3] / "fixtures" / "vid_001.mp4"

    response = client.post(
        "/api/materials/upload",
        data={"slot_id": "selling_points"},
        files={"file": ("short-opening.mp4", fixture_path.read_bytes(), "video/mp4")},
    )

    assert response.status_code == 200
    body = response.json()
    analysis = body["analysis"]
    assert analysis["recommended_slot_id"] == "hook"
    assert analysis["recommended_slot_label"] == "Hook"
    assert analysis["duration"] > 0
    assert analysis["shot_count"] >= 1
    assert "短镜头" in analysis["recommendation_reason"]
    assert "hook" in analysis["slot_fit_scores"]


def test_prepare_demo_assets_endpoint_returns_render_clips():
    client = TestClient(app)

    response = client.post(
        "/api/media/prepare-demo-assets",
        json={
            "duration": 6,
            "tracks": [
                {
                    "type": "video",
                    "start": 0,
                    "duration": 3,
                    "source": "咖啡 特写",
                    "slot_id": "selling_points",
                },
                {
                    "type": "caption",
                    "start": 0.5,
                    "duration": 2,
                    "text": "突出手作咖啡",
                    "slot_id": "selling_points",
                },
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["clips"][0]["scene_id"] == "selling_points"
    assert body["clips"][0]["caption"] == "突出手作咖啡"
    assert body["clips"][0]["public_url"].startswith("/downloads/")


def test_render_demo_endpoint_returns_video_url():
    client = TestClient(app)

    response = client.post(
        "/api/media/render-demo",
        json={
            "duration": 3,
            "tracks": [
                {
                    "type": "video",
                    "start": 0,
                    "duration": 1,
                    "source": "咖啡 特写",
                    "slot_id": "selling_points",
                }
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["video_url"].startswith("/output/")
    assert body["local_path"].endswith(".mp4")


def test_output_static_mount_serves_rendered_video():
    client = TestClient(app)
    render_response = client.post(
        "/api/media/render-demo",
        json={
            "duration": 3,
            "tracks": [
                {
                    "type": "video",
                    "start": 0,
                    "duration": 1,
                    "source": "咖啡 特写",
                    "slot_id": "selling_points",
                }
            ],
        },
    )

    response = client.get(render_response.json()["video_url"])

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("video/")


def test_upload_sample_video_returns_real_video_signal_and_keyframes():
    client = TestClient(app)
    fixture_path = Path(__file__).resolve().parents[3] / "fixtures" / "vid_001.mp4"

    response = client.post(
        "/api/samples/upload",
        files={"file": ("sample-video.mp4", fixture_path.read_bytes(), "video/mp4")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["sample"]["duration"] > 0
    assert body["sample"]["shot_count"] >= 1
    assert "真实视频信号解析" in body["sample"]["transcript_summary"]

    video_signal = body["video_signal"]
    assert video_signal["metadata"]["duration"] > 0
    assert video_signal["metadata"]["width"] > 0
    assert video_signal["metadata"]["height"] > 0
    assert video_signal["metadata"]["fps"] > 0
    assert video_signal["shot_count"] == body["sample"]["shot_count"]
    assert video_signal["shot_count"] == len(video_signal["shots"])
    assert video_signal["detection_method"] in {
        "scene_detect",
        "pyscenedetect_adaptive",
        "pyscenedetect_content",
        "ffmpeg_scene_detect",
        "uniform_fallback",
    }
    assert video_signal["rhythm_metrics"]["avg_shot_duration"] > 0

    keyframes = body["keyframes"]
    assert len(keyframes) == video_signal["shot_count"]
    for keyframe in keyframes:
        assert Path(keyframe["local_path"]).is_file()
        assert keyframe["public_url"].startswith("/keyframes/")

    keyframe_response = client.get(keyframes[0]["public_url"])
    assert keyframe_response.status_code == 200
    assert keyframe_response.headers["content-type"].startswith("image/")


def test_upload_sample_video_returns_400_for_invalid_video():
    client = TestClient(app, raise_server_exceptions=False)

    response = client.post(
        "/api/samples/upload",
        files={"file": ("invalid.mp4", b"not a video", "video/mp4")},
    )

    assert response.status_code == 400
    assert "视频解析失败" in response.json()["detail"]


def test_upload_sample_video_passes_all_detected_shots_to_keyframe_extraction(monkeypatch):
    client = TestClient(app)
    captured_shot_count = 0
    shots = [
        VideoShot(index=index, start=index - 1, end=index, duration=1, keyframe_time=index - 0.5)
        for index in range(1, 9)
    ]
    video_signal = VideoSignal(
        metadata=VideoMetadata(duration=8, fps=30, width=1920, height=1080, format_name="mp4"),
        shot_count=len(shots),
        shots=shots,
    )

    def fake_extract_keyframes(video_path, received_shots, *, output_dir, public_prefix):
        nonlocal captured_shot_count
        captured_shot_count = len(received_shots)
        return []

    monkeypatch.setattr("app.sample_service.detect_video_signal", lambda path: video_signal)
    monkeypatch.setattr("app.sample_service.extract_keyframes", fake_extract_keyframes)

    response = client.post(
        "/api/samples/upload",
        files={"file": ("sample-video.mp4", b"fake video bytes", "video/mp4")},
    )

    assert response.status_code == 200
    assert response.json()["video_signal"]["shot_count"] == 8
    assert captured_shot_count == 8
