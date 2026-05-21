from fastapi import FastAPI

from app.fixture_asset_service import build_render_clips_from_composition
from app.models import (
    CompositionSpec,
    PrepareDemoAssetsResponse,
    RenderClipPreview,
    RenderDemoResponse,
    StructurePreviewRequest,
    StructurePreviewResponse,
)
from app.render_service import render_demo_video
from app.structure_service import build_structure_preview


app = FastAPI(title="ReelStruct API")


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/structure/preview", response_model=StructurePreviewResponse)
def preview_structure_transfer(request: StructurePreviewRequest) -> StructurePreviewResponse:
    return build_structure_preview(request.sample, request.content)


@app.post("/api/media/prepare-demo-assets", response_model=PrepareDemoAssetsResponse)
def prepare_demo_assets(composition: CompositionSpec) -> PrepareDemoAssetsResponse:
    clips = build_render_clips_from_composition(composition)
    return PrepareDemoAssetsResponse(
        clips=[
            RenderClipPreview(
                scene_id=clip.scene_id,
                local_path=clip.local_path,
                public_url=clip.public_url,
                caption=clip.caption,
                start_time=clip.start_time,
                duration=clip.duration,
            )
            for clip in clips
        ]
    )


@app.post("/api/media/render-demo", response_model=RenderDemoResponse)
def render_demo(composition: CompositionSpec) -> RenderDemoResponse:
    clips = build_render_clips_from_composition(composition)
    result = render_demo_video(clips, output_filename="demo.mp4")
    return RenderDemoResponse(video_url=result.video_url, local_path=result.local_path)
