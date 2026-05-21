from pathlib import Path

from app.fixture_asset_service import RenderClip
from app.render_service import build_render_plan, build_video_filter, render_demo_video


def test_build_render_plan_uses_reelstruct_output_contract(tmp_path):
    clip_path = tmp_path / "clip.mp4"
    clip_path.write_bytes(b"placeholder")
    clip = RenderClip(
        scene_id="hook",
        local_path=str(clip_path),
        public_url="/downloads/hook.mp4",
        caption="开头抓住注意力",
        start_time=0,
        duration=3,
    )

    plan = build_render_plan([clip], output_path=tmp_path / "demo.mp4")

    assert plan["segments"][0]["input"] == str(clip_path)
    assert plan["segments"][0]["caption"] == "开头抓住注意力"
    assert plan["segments"][0]["trimDuration"] == 3
    assert plan["output"]["width"] == 720
    assert plan["output"]["height"] == 1280


def test_build_video_filter_adds_drawtext_when_caption_file_is_available(tmp_path):
    caption_path = tmp_path / "caption.txt"
    caption_path.write_text("开头抓住注意力", encoding="utf-8")

    video_filter = build_video_filter(caption_path=caption_path, drawtext_available=True)

    assert "drawtext=" in video_filter
    assert f"textfile={caption_path}" in video_filter
    assert "fontsize=42" in video_filter


def test_build_video_filter_skips_drawtext_when_filter_is_unavailable(tmp_path):
    caption_path = tmp_path / "caption.txt"
    caption_path.write_text("开头抓住注意力", encoding="utf-8")

    video_filter = build_video_filter(caption_path=caption_path, drawtext_available=False)

    assert "drawtext=" not in video_filter
    assert "scale=720:1280" in video_filter


def test_render_demo_video_creates_mp4_from_fixture_clip(tmp_path):
    source = tmp_path / "source.mp4"
    output_dir = tmp_path / "output"
    create_tiny_video(source)
    clip = RenderClip(
        scene_id="hook",
        local_path=str(source),
        public_url="/downloads/source.mp4",
        caption="",
        start_time=0,
        duration=1,
    )

    result = render_demo_video([clip], output_filename="demo.mp4", output_dir=output_dir)

    output_path = output_dir / "demo.mp4"
    assert result.video_url == "/output/demo.mp4"
    assert result.local_path == str(output_path)
    assert output_path.exists()
    assert output_path.stat().st_size > 0


def create_tiny_video(path: Path) -> None:
    import subprocess

    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=blue:s=160x240:d=1",
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
