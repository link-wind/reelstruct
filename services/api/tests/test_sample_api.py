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


def test_upload_sample_video_detects_scene_based_shot_count():
    client = TestClient(app)

    response = client.post(
        "/api/samples/upload",
        files={"file": ("scene.mp4", create_scene_change_video_bytes(), "video/mp4")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["sample"]["duration"] >= 3
    assert body["sample"]["shot_count"] >= 3


def test_upload_transcript_file_returns_clean_summary():
    client = TestClient(app)

    response = client.post(
        "/api/samples/upload-transcript",
        files={
            "file": (
                "sample.srt",
                (
                    "1\n00:00:00,000 --> 00:00:01,000\n先讲熬夜脸很垮。\n\n"
                    "2\n00:00:01,000 --> 00:00:02,500\n再展示精华上脸效果。\n\n"
                    "3\n00:00:02,500 --> 00:00:03,000\n最后引导现在下单。"
                ).encode("utf-8"),
                "application/x-subrip",
            )
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["filename"] == "sample.srt"
    assert "00:00:00,000" not in body["transcript_summary"]
    assert "先讲熬夜脸很垮。" in body["transcript_summary"]
    assert "最后引导现在下单。" in body["transcript_summary"]


def test_generate_sample_ocr_evidence_returns_graph_with_ocr_texts(monkeypatch, tmp_path):
    from app.video_understanding.schemas import FrameOCRText

    client = TestClient(app)
    video_path = tmp_path / "sample.mp4"
    video_path.write_bytes(b"video")

    class FakeOCRResult:
        texts = [
            FrameOCRText(
                shot_index=1,
                frame_index=1,
                frame_time=0.5,
                text="限时优惠",
                position="top",
                confidence=0.91,
            )
        ]
        warnings = ["ocr warning"]

    monkeypatch.setattr(
        "app.sample_evidence_service.extract_frame_evidence",
        lambda path, shots, *, output_dir, public_prefix: [],
    )
    monkeypatch.setattr("app.sample_evidence_service.recognize_frames_with_ocr", lambda frames: FakeOCRResult())

    response = client.post(
        "/api/samples/evidence/ocr",
        json={
            "sample_id": "sample-test",
            "sample_local_path": str(video_path),
            "video_signal": {
                "metadata": {"duration": 2, "fps": 30, "width": 720, "height": 1280, "format_name": "mp4"},
                "shot_count": 1,
                "detection_method": "pyscenedetect_adaptive",
                "shots": [{"index": 1, "start": 0, "end": 2, "duration": 2, "keyframe_time": 1}],
                "rhythm_metrics": {},
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["shots"][0]["ocr_texts"][0]["text"] == "限时优惠"
    assert body["warnings"] == ["ocr warning"]


def test_generate_sample_ocr_evidence_can_limit_to_requested_shots(monkeypatch, tmp_path):
    client = TestClient(app)
    video_path = tmp_path / "sample.mp4"
    video_path.write_bytes(b"video")
    captured_shot_indices = []

    class FakeOCRResult:
        texts = []
        warnings = []

    def fake_extract_frame_evidence(path, shots, *, output_dir, public_prefix):
        captured_shot_indices.extend(shot.index for shot in shots)
        return []

    monkeypatch.setattr("app.sample_evidence_service.extract_frame_evidence", fake_extract_frame_evidence)
    monkeypatch.setattr("app.sample_evidence_service.recognize_frames_with_ocr", lambda frames: FakeOCRResult())

    response = client.post(
        "/api/samples/evidence/ocr",
        json={
            "sample_id": "sample-test",
            "sample_local_path": str(video_path),
            "shot_indices": [2],
            "video_signal": {
                "metadata": {"duration": 4, "fps": 30, "width": 720, "height": 1280, "format_name": "mp4"},
                "shot_count": 2,
                "detection_method": "pyscenedetect_adaptive",
                "shots": [
                    {"index": 1, "start": 0, "end": 2, "duration": 2, "keyframe_time": 1},
                    {"index": 2, "start": 2, "end": 4, "duration": 2, "keyframe_time": 3},
                ],
                "rhythm_metrics": {},
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert captured_shot_indices == [2]
    assert [node["shot"]["index"] for node in body["shots"]] == [2]


def test_generate_sample_asr_evidence_returns_graph_with_transcript_texts(monkeypatch, tmp_path):
    from app.video_understanding.schemas import TranscriptSegment

    client = TestClient(app)
    video_path = tmp_path / "sample.mp4"
    video_path.write_bytes(b"video")

    class FakeASRResult:
        segments = [TranscriptSegment(start=0.2, end=1.4, text="早上来不及吃饭？")]
        warnings = ["asr warning"]

    monkeypatch.setattr("app.sample_evidence_service.transcribe_video_with_asr", lambda path, *, work_dir: FakeASRResult())

    response = client.post(
        "/api/samples/evidence/asr",
        json={
            "sample_id": "sample-test",
            "sample_local_path": str(video_path),
            "video_signal": {
                "metadata": {"duration": 2, "fps": 30, "width": 720, "height": 1280, "format_name": "mp4"},
                "shot_count": 1,
                "detection_method": "pyscenedetect_adaptive",
                "shots": [{"index": 1, "start": 0, "end": 2, "duration": 2, "keyframe_time": 1}],
                "rhythm_metrics": {},
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["shots"][0]["transcript_texts"][0]["text"] == "早上来不及吃饭？"
    assert body["warnings"] == ["asr warning"]


def test_generate_sample_asr_evidence_can_limit_to_requested_shots(monkeypatch, tmp_path):
    from app.video_understanding.schemas import TranscriptSegment

    client = TestClient(app)
    video_path = tmp_path / "sample.mp4"
    video_path.write_bytes(b"video")
    captured = {}

    class FakeASRResult:
        segments = [TranscriptSegment(start=2.2, end=3.2, text="第二镜头口播")]
        warnings = []

    def fake_transcribe_video_with_asr(path, *, work_dir, clip_start=None, clip_end=None):
        captured["clip_start"] = clip_start
        captured["clip_end"] = clip_end
        return FakeASRResult()

    monkeypatch.setattr("app.sample_evidence_service.transcribe_video_with_asr", fake_transcribe_video_with_asr)

    response = client.post(
        "/api/samples/evidence/asr",
        json={
            "sample_id": "sample-test",
            "sample_local_path": str(video_path),
            "shot_indices": [2],
            "video_signal": {
                "metadata": {"duration": 4, "fps": 30, "width": 720, "height": 1280, "format_name": "mp4"},
                "shot_count": 2,
                "detection_method": "pyscenedetect_adaptive",
                "shots": [
                    {"index": 1, "start": 0, "end": 2, "duration": 2, "keyframe_time": 1},
                    {"index": 2, "start": 2, "end": 4, "duration": 2, "keyframe_time": 3},
                ],
                "rhythm_metrics": {},
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert captured == {"clip_start": 2.0, "clip_end": 4.0}
    assert [node["shot"]["index"] for node in body["shots"]] == [2]
    assert body["shots"][0]["transcript_texts"][0]["text"] == "第二镜头口播"


def test_upload_sample_video_returns_400_when_parser_raises_runtime_error(monkeypatch):
    client = TestClient(app, raise_server_exceptions=False)

    def fake_save_sample_upload(*args, **kwargs):
        raise RuntimeError("ffmpeg parser crashed")

    monkeypatch.setattr("app.main.save_sample_upload", fake_save_sample_upload)

    response = client.post(
        "/api/samples/upload",
        files={"file": ("sample.mp4", b"video bytes", "video/mp4")},
    )

    assert response.status_code == 400
    assert "视频解析失败" in response.json()["detail"]


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


def create_scene_change_video_bytes() -> bytes:
    from pathlib import Path
    import subprocess
    import tempfile

    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        colors = ["red", "blue", "green"]
        segment_paths: list[Path] = []
        for color in colors:
            segment_path = root / f"{color}.mp4"
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-f",
                    "lavfi",
                    "-i",
                    f"color=c={color}:s=160x240:d=1",
                    "-f",
                    "lavfi",
                    "-i",
                    "anullsrc=channel_layout=stereo:sample_rate=44100",
                    "-shortest",
                    "-c:v",
                    "libx264",
                    "-c:a",
                    "aac",
                    str(segment_path),
                ],
                check=True,
                capture_output=True,
            )
            segment_paths.append(segment_path)

        list_path = root / "list.txt"
        list_path.write_text(
            "".join(f"file '{path.as_posix()}'\n" for path in segment_paths),
            encoding="utf-8",
        )
        output_path = root / "scene.mp4"
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(list_path),
                "-c",
                "copy",
                str(output_path),
            ],
            check=True,
            capture_output=True,
        )
        return output_path.read_bytes()
