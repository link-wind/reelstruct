from fastapi.testclient import TestClient

from app.main import app


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
