from fastapi.testclient import TestClient
from pathlib import Path

from app.material_asset_service import analyze_material_fit, enrich_material_analysis_with_video_evidence
from app.material_evidence_service import build_material_evidence_chunks_from_video
from app.models import MaterialEvidenceChunk, MaterialFitAnalysis
from app.video_understanding.schemas import FrameEvidence, FrameOCRText
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


def test_upload_material_asset_returns_fit_analysis_for_recommended_slot(monkeypatch):
    monkeypatch.setenv("REELSTRUCT_OCR_ENABLED", "false")
    called = False

    def fake_video_evidence(*args, **kwargs):
        nonlocal called
        called = True
        return []

    monkeypatch.setattr("app.material_asset_service.build_material_evidence_chunks_from_video", fake_video_evidence)
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
    assert called is False
    assert any("等待生成真实素材证据" in warning for warning in analysis["warnings"])


def test_analyze_material_fit_returns_searchable_understanding_card(monkeypatch, tmp_path):
    material_path = tmp_path / "product-detail-closeup.mp4"
    material_path.write_bytes(b"fake video")
    monkeypatch.setattr("app.material_asset_service.probe_video_duration", lambda path: 6.2)
    monkeypatch.setattr("app.material_asset_service.detect_shot_count", lambda path: 3)

    analysis = analyze_material_fit(material_path)

    assert analysis.visual_summary
    assert "product" in analysis.embedding_text
    assert "detail" in analysis.embedding_text
    assert "closeup" in analysis.embedding_text
    assert analysis.tags
    assert "卖点展开" in analysis.usable_for


def test_analyze_material_fit_returns_evidence_chunks(monkeypatch, tmp_path):
    material_path = tmp_path / "product-detail-closeup.mp4"
    material_path.write_bytes(b"fake video")
    monkeypatch.setattr("app.material_asset_service.probe_video_duration", lambda path: 6.2)
    monkeypatch.setattr("app.material_asset_service.detect_shot_count", lambda path: 3)

    analysis = analyze_material_fit(material_path)

    assert analysis.evidence_chunks
    chunk = analysis.evidence_chunks[0]
    assert chunk.chunk_id == "chunk_1"
    assert chunk.start == 0
    assert chunk.end > chunk.start
    assert "product" in chunk.embedding_text
    assert "visual" in chunk.modalities
    assert "卖点展开" in chunk.slot_hints


def test_build_material_evidence_chunks_from_video_uses_frames_and_ocr(monkeypatch, tmp_path):
    material_path = tmp_path / "detail.mp4"
    material_path.write_bytes(b"fake video")
    shots = [
        VideoShot(index=1, start=0, end=2, duration=2, keyframe_time=1),
        VideoShot(index=2, start=2, end=5, duration=3, keyframe_time=3.5),
    ]
    video_signal = VideoSignal(
        metadata=VideoMetadata(duration=5, fps=30, width=1080, height=1920, format_name="mp4"),
        shot_count=2,
        shots=shots,
    )
    analysis = MaterialFitAnalysis(
        duration=5,
        shot_count=2,
        recommended_slot_id="selling_points",
        recommended_slot_label="卖点展开",
        visual_summary="产品瓶身细节特写。",
        tags=["产品", "特写"],
        usable_for=["卖点展开"],
        embedding_text="产品 瓶身 特写 快速补水 卖点展开",
    )

    monkeypatch.setattr("app.material_evidence_service.detect_video_signal", lambda path: video_signal)
    monkeypatch.setattr(
        "app.material_evidence_service.extract_frame_evidence",
        lambda video_path, received_shots, *, output_dir, public_prefix: [
            FrameEvidence(
                shot_index=1,
                frame_index=1,
                time=1,
                role="middle",
                local_path=str(tmp_path / "frame.jpg"),
                public_url="/keyframes/materials/detail/frame.jpg",
            )
        ],
    )
    monkeypatch.setattr(
        "app.material_evidence_service.recognize_frames_with_ocr",
        lambda frames: type(
            "OCRResult",
            (),
            {
                "texts": [
                    FrameOCRText(
                        shot_index=1,
                        frame_index=1,
                        frame_time=1,
                        text="快速补水",
                        confidence=0.95,
                    )
                ],
                "warnings": [],
            },
        )(),
    )

    chunks = build_material_evidence_chunks_from_video(
        material_path,
        asset_id="detail.mp4",
        analysis=analysis,
        output_dir=tmp_path / "evidence",
        public_prefix="/keyframes/materials/detail",
    )

    assert len(chunks) == 2
    assert chunks[0].frame_urls == ["/keyframes/materials/detail/frame.jpg"]
    assert chunks[0].ocr_texts == ["快速补水"]
    assert "ocr" in chunks[0].modalities
    assert "快速补水" in chunks[0].embedding_text


def test_material_evidence_endpoint_generates_real_chunks(monkeypatch, tmp_path):
    client = TestClient(app)
    material_path = tmp_path / "detail.mp4"
    material_path.write_bytes(b"fake video")
    indexed_assets = []

    monkeypatch.setattr("app.main.MATERIALS_DIR", tmp_path)
    monkeypatch.setattr("app.main.index_material_asset", lambda asset: indexed_assets.append(asset))
    monkeypatch.setattr(
        "app.main.enrich_material_analysis_with_video_evidence",
            lambda path, *, analysis, evidence_dir, evidence_public_prefix, strict=False: analysis.model_copy(
            update={
                "warnings": ["真实素材证据已生成"],
                "evidence_chunks": [
                    MaterialEvidenceChunk(
                        asset_id=path.name,
                        chunk_id="shot_1",
                        start=0,
                        end=2,
                        duration=2,
                        frame_urls=["/materials/detail-evidence/frame.jpg"],
                        ocr_texts=["快速补水"],
                        visual_summary="产品瓶身特写。",
                        slot_hints=["卖点展开"],
                        modalities=["visual", "ocr", "slot"],
                        embedding_text="产品瓶身特写 快速补水 卖点展开",
                    )
                ],
            }
        ),
    )

    response = client.post(
        "/api/materials/evidence",
        json={
            "slot_id": "material_pool",
            "filename": "detail.mp4",
            "local_path": str(material_path),
            "public_url": "/materials/detail.mp4",
            "analysis": {
                "duration": 2,
                "shot_count": 1,
                "recommended_slot_id": "selling_points",
                "recommended_slot_label": "卖点展开",
                "recommendation_reason": "产品细节素材。",
                "slot_fit_scores": {"selling_points": 90},
                "visual_summary": "产品细节素材。",
                "tags": ["产品"],
                "usable_for": ["卖点展开"],
                "embedding_text": "产品 快速补水",
            },
        },
    )

    assert response.status_code == 200
    analysis = response.json()["analysis"]
    assert analysis["evidence_chunks"][0]["frame_urls"] == ["/materials/detail-evidence/frame.jpg"]
    assert analysis["evidence_chunks"][0]["ocr_texts"] == ["快速补水"]
    assert "真实素材证据已生成" in analysis["warnings"]
    assert indexed_assets
    assert indexed_assets[0].analysis.evidence_chunks[0].chunk_id == "shot_1"


def test_enrich_material_analysis_replaces_waiting_warning_after_real_evidence(monkeypatch, tmp_path):
    material_path = tmp_path / "detail.mp4"
    material_path.write_bytes(b"fake video")
    analysis = MaterialFitAnalysis(
        duration=2,
        shot_count=1,
        warnings=["等待生成真实素材证据：当前为轻量素材理解卡。"],
    )
    monkeypatch.setattr(
        "app.material_asset_service.build_material_evidence_chunks_from_video",
        lambda *args, **kwargs: [
            MaterialEvidenceChunk(
                asset_id="detail.mp4",
                chunk_id="shot_1",
                start=0,
                end=2,
                duration=2,
                visual_summary="产品瓶身特写。",
                modalities=["visual"],
                embedding_text="产品瓶身特写",
            )
        ],
    )

    enriched = enrich_material_analysis_with_video_evidence(
        material_path,
        analysis=analysis,
        evidence_dir=tmp_path / "evidence",
        evidence_public_prefix="/materials/detail-evidence",
        strict=True,
    )

    assert enriched.evidence_chunks[0].chunk_id == "shot_1"
    assert all("等待生成真实素材证据" not in warning for warning in enriched.warnings)
    assert "真实素材证据已生成" in enriched.warnings


def test_material_evidence_endpoint_returns_400_when_generation_fails(monkeypatch, tmp_path):
    client = TestClient(app, raise_server_exceptions=False)
    material_path = tmp_path / "detail.mp4"
    material_path.write_bytes(b"fake video")

    monkeypatch.setattr("app.main.MATERIALS_DIR", tmp_path)

    def fail_generation(*args, **kwargs):
        raise RuntimeError("ffmpeg failed")

    monkeypatch.setattr("app.main.enrich_material_analysis_with_video_evidence", fail_generation)

    response = client.post(
        "/api/materials/evidence",
        json={
            "slot_id": "material_pool",
            "filename": "detail.mp4",
            "local_path": str(material_path),
            "public_url": "/materials/detail.mp4",
            "analysis": {
                "duration": 2,
                "shot_count": 1,
                "recommended_slot_id": "selling_points",
                "recommended_slot_label": "卖点展开",
                "slot_fit_scores": {"selling_points": 90},
                "evidence_chunks": [
                    {
                        "asset_id": "detail.mp4",
                        "chunk_id": "chunk_1",
                        "start": 0,
                        "end": 2,
                        "duration": 2,
                    }
                ],
            },
        },
    )

    assert response.status_code == 400
    assert "素材证据生成失败" in response.json()["detail"]


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
