from fastapi.testclient import TestClient

from app.main import app


def test_upload_sample_video_returns_metadata():
    client = TestClient(app)

    response = client.post(
        "/api/samples/upload",
        files={"file": ("sample.mp4", create_tiny_video_bytes(), "video/mp4")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["sample_id"].startswith("sample-")
    assert body["filename"].endswith(".mp4")
    assert body["public_url"].startswith("/samples/")
    assert body["sample"]["title"] == "sample.mp4"
    assert body["sample"]["duration"] >= 1
    assert body["sample"]["shot_count"] >= 1


def create_tiny_video_bytes() -> bytes:
    from pathlib import Path
    import subprocess
    import tempfile

    with tempfile.TemporaryDirectory() as temp_dir:
        path = Path(temp_dir) / "sample.mp4"
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-f",
                "lavfi",
                "-i",
                "color=c=green:s=160x240:d=1",
                "-f",
                "lavfi",
                "-i",
                "anullsrc=channel_layout=stereo:sample_rate=44100",
                "-shortest",
                "-c:v",
                "libx264",
                "-c:a",
                "aac",
                str(path),
            ],
            check=True,
            capture_output=True,
        )
        return path.read_bytes()
