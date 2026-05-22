from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from uuid import uuid4

from app.fixture_asset_service import build_render_clips_from_composition
from app.models import (
    DemoRunResponse,
    RenderClipPreview,
    RenderDemoResponse,
    RunTraceEvent,
    StructurePreviewRequest,
)
from app.run_record_service import save_demo_run_record
from app.render_service import render_demo_video
from app.structure_service import build_structure_preview


def create_demo_run(request: StructurePreviewRequest, runs_dir: Optional[Path] = None) -> DemoRunResponse:
    run_id = f"demo-{uuid4().hex[:8]}"
    created_at = datetime.now(timezone.utc).isoformat()
    trace = [
        RunTraceEvent(
            step="analyze_structure",
            title="结构拆解",
            message="已从样例中拆出脚本槽位、节奏摘要和包装要点。",
            progress=25,
        )
    ]

    preview = build_structure_preview(
        request.sample,
        request.content,
        mapping_overrides=request.mapping_overrides,
        material_request_sheet=request.material_request_sheet,
    )
    trace.append(
        RunTraceEvent(
            step="transfer_structure",
            title="结构迁移",
            message=f"已生成 {len(preview.transfer_plan.mappings)} 个结构映射。",
            progress=45,
        )
    )

    clips = build_render_clips_from_composition(preview.composition)
    trace.append(
        RunTraceEvent(
            step="prepare_assets",
            title="素材准备",
            message=f"已准备 {len(clips)} 段可渲染素材。",
            progress=68,
        )
    )

    rendered = render_demo_video(clips, output_filename=f"{run_id}.mp4")
    trace.append(
        RunTraceEvent(
            step="render_video",
            title="视频渲染",
            message="已使用 FFmpeg 合成竖屏 MP4 demo。",
            progress=90,
        )
    )
    trace.append(
        RunTraceEvent(
            step="done",
            title="生成完成",
            message="结构迁移 demo 已生成，可以在前端预览。",
            progress=100,
        )
    )

    response = DemoRunResponse(
        run_id=run_id,
        created_at=created_at,
        status="succeeded",
        preview=preview,
        prepared_assets=[
            RenderClipPreview(
                scene_id=clip.scene_id,
                local_path=clip.local_path,
                public_url=clip.public_url,
                caption=clip.caption,
                start_time=clip.start_time,
                duration=clip.duration,
            )
            for clip in clips
        ],
        rendered_video=RenderDemoResponse(
            video_url=rendered.video_url,
            local_path=rendered.local_path,
        ),
        trace=trace,
    )
    if runs_dir is not None:
        save_demo_run_record(response, runs_dir)
    return response
