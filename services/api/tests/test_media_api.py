from fastapi.testclient import TestClient
from pathlib import Path

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
