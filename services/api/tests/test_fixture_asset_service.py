import json
from pathlib import Path

from app.fixture_asset_service import (
    build_render_clips_from_composition,
    copy_fixture_asset,
    search_fixture_assets,
)
from app.models import CompositionSpec, CompositionTrack


def write_fixture_library(root: Path) -> None:
    fixtures_dir = root / "fixtures"
    fixtures_dir.mkdir()
    (fixtures_dir / "coffee.mp4").write_bytes(b"coffee")
    (fixtures_dir / "city.mp4").write_bytes(b"city")
    (fixtures_dir / "videos.json").write_text(
        json.dumps(
            [
                {
                    "id": "coffee",
                    "title": "咖啡拉花特写",
                    "description": "手工咖啡拉花过程特写",
                    "duration": 20,
                    "tags": ["咖啡", "特写", "商品特写镜头"],
                    "videoUrl": "/fixtures/coffee.mp4",
                },
                {
                    "id": "city",
                    "title": "城市黄昏车流",
                    "description": "傍晚城市街道",
                    "duration": 45,
                    "tags": ["城市", "开头吸引镜头"],
                    "videoUrl": "/fixtures/city.mp4",
                },
            ]
        ),
        encoding="utf-8",
    )


def test_search_fixture_assets_scores_keywords(tmp_path):
    write_fixture_library(tmp_path)

    results = search_fixture_assets(["咖啡", "商品特写镜头"], fixture_root=tmp_path)

    assert [candidate.id for candidate in results] == ["coffee"]
    assert results[0].local_path == str(tmp_path / "fixtures" / "coffee.mp4")
    assert results[0].public_url == "/fixtures/coffee.mp4"


def test_copy_fixture_asset_copies_into_download_dir(tmp_path):
    write_fixture_library(tmp_path)
    candidate = search_fixture_assets(["城市"], fixture_root=tmp_path)[0]

    copied = copy_fixture_asset(candidate, output_dir=tmp_path / "downloads", output_name="scene-1.mp4")

    assert Path(copied.local_path).read_bytes() == b"city"
    assert copied.public_url == "/downloads/scene-1.mp4"


def test_build_render_clips_from_composition_uses_video_tracks(tmp_path):
    write_fixture_library(tmp_path)
    composition = CompositionSpec(
        duration=6,
        tracks=[
            CompositionTrack(type="video", start=0, duration=3, source="咖啡 商品特写镜头", slot_id="selling_points"),
            CompositionTrack(type="caption", start=0.5, duration=2, text="突出手作咖啡", slot_id="selling_points"),
        ],
    )

    clips = build_render_clips_from_composition(
        composition,
        fixture_root=tmp_path,
        output_dir=tmp_path / "downloads",
    )

    assert len(clips) == 1
    assert clips[0].scene_id == "selling_points"
    assert clips[0].caption == "突出手作咖啡"
    assert clips[0].source_type == "fixture"
    assert clips[0].source_label == "fixture 匹配：咖啡拉花特写"
    assert Path(clips[0].local_path).exists()


def test_build_render_clips_from_composition_merges_caption_and_card_text(tmp_path):
    write_fixture_library(tmp_path)
    composition = CompositionSpec(
        duration=6,
        tracks=[
            CompositionTrack(type="video", start=0, duration=3, source="咖啡 商品特写镜头", slot_id="selling_points"),
            CompositionTrack(type="caption", start=0.5, duration=2, text="突出手作咖啡", slot_id="selling_points"),
            CompositionTrack(type="card", start=0.8, duration=2, text="卖点卡片：手作拉花", slot_id="selling_points"),
        ],
    )

    clips = build_render_clips_from_composition(
        composition,
        fixture_root=tmp_path,
        output_dir=tmp_path / "downloads",
    )

    assert clips[0].caption == "卖点卡片：手作拉花\n突出手作咖啡"


def test_build_render_clips_from_composition_prefers_uploaded_slot_asset(tmp_path):
    write_fixture_library(tmp_path)
    uploaded_path = tmp_path / "uploads" / "selling-points.mp4"
    uploaded_path.parent.mkdir()
    uploaded_path.write_bytes(b"uploaded material")
    composition = CompositionSpec(
        duration=6,
        tracks=[
            CompositionTrack(
                type="video",
                start=0,
                duration=3,
                source="咖啡 商品特写镜头",
                slot_id="selling_points",
                asset_local_path=str(uploaded_path),
                asset_public_url="/materials/selling-points.mp4",
            ),
            CompositionTrack(type="caption", start=0.5, duration=2, text="突出手作咖啡", slot_id="selling_points"),
        ],
    )

    clips = build_render_clips_from_composition(
        composition,
        fixture_root=tmp_path,
        output_dir=tmp_path / "downloads",
    )

    assert len(clips) == 1
    assert clips[0].scene_id == "selling_points"
    assert clips[0].local_path == str(uploaded_path)
    assert clips[0].public_url == "/materials/selling-points.mp4"
    assert clips[0].caption == "突出手作咖啡"
    assert clips[0].source_type == "uploaded"
    assert clips[0].source_label == "用户上传素材"
