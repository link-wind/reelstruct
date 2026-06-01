from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from uuid import uuid4

from app.fixture_asset_service import build_render_clips_from_composition
from app.api.api_models import (
    DemoRunResponse,
    PreviewRunRequest,
    RenderClipPreview,
    RenderDemoResponse,
    StructurePreviewRequest,
    StructurePreviewResponse,
)
from app.domain.shared.domain_models import (
    CompositionTrack,
    TemplateStructure,
    TransferMapping,
    TransferMappingOverride,
)
from app.workflow.workflow_models import EvaluationSummary, RunTraceEvent
from app.run_record_service import save_demo_run_record
from app.render_service import render_demo_video
from app.structure_service import apply_slot_level_overrides, build_structure_preview


def create_demo_run(
    request: StructurePreviewRequest,
    runs_dir: Optional[Path] = None,
    batch_id: str = "",
    template_override: Optional[TemplateStructure] = None,
    ai_template: Optional[TemplateStructure] = None,
    template_id: str = "",
    template_title: str = "",
    template_tags: Optional[list[str]] = None,
) -> DemoRunResponse:
    run_id = f"demo-{uuid4().hex[:8]}"
    created_at = datetime.now(timezone.utc).isoformat()
    analysis_source = _analysis_source(template_override, ai_template)
    trace = [
        RunTraceEvent(
            step="analyze_structure",
            title="结构拆解",
            message=_analysis_trace_message(analysis_source),
            progress=25,
        )
    ]

    preview = build_structure_preview(
        request.sample,
        request.content,
        template_override=template_override,
        ai_template=ai_template,
        mapping_overrides=request.mapping_overrides,
        material_request_sheet=request.material_request_sheet,
        supplement_selections=request.supplement_selections,
        variant=request.variant,
        use_ai_transfer_explanation=request.use_ai_transfer_explanation,
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
        batch_id=batch_id,
        created_at=created_at,
        status="succeeded",
        template_id=template_id,
        template_title=template_title,
        template_tags=template_tags or [],
        variant=request.variant,
        preview=preview,
        evaluation_summary=preview.evaluation_summary,
        prepared_assets=[
            RenderClipPreview(
                scene_id=clip.scene_id,
                local_path=clip.local_path,
                public_url=clip.public_url,
                caption=clip.caption,
                start_time=clip.start_time,
                duration=clip.duration,
                source_type=clip.source_type,
                source_label=clip.source_label,
                material_analysis=clip.material_analysis,
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


def create_demo_run_from_preview(
    request: PreviewRunRequest,
    *,
    runs_dir: Optional[Path] = None,
    batch_id: str = "",
) -> DemoRunResponse:
    preview = _apply_mapping_overrides_to_preview(request.preview, request.mapping_overrides)
    run_id = f"demo-{uuid4().hex[:8]}"
    created_at = datetime.now(timezone.utc).isoformat()

    clips = build_render_clips_from_composition(preview.composition)
    trace = [
        RunTraceEvent(
            step="prepare_assets",
            title="素材准备",
            message=f"已准备 {len(clips)} 段可渲染素材。",
            progress=55,
        )
    ]

    rendered = render_demo_video(clips, output_filename=f"{run_id}.mp4")
    trace.append(
        RunTraceEvent(
            step="render_video",
            title="视频渲染",
            message="已使用 FFmpeg 合成竖屏 MP4 demo。",
            progress=85,
        )
    )
    trace.append(
        RunTraceEvent(
            step="done",
            title="生成完成",
            message="已基于现有结构预览生成 demo，可以在前端预览。",
            progress=100,
        )
    )

    response = DemoRunResponse(
        run_id=run_id,
        batch_id=batch_id,
        created_at=created_at,
        status="succeeded",
        template_id=request.template_id,
        template_title=request.template_title,
        template_tags=request.template_tags,
        variant=request.variant,
        preview=preview,
        evaluation_summary=preview.evaluation_summary or EvaluationSummary(),
        prepared_assets=[
            RenderClipPreview(
                scene_id=clip.scene_id,
                local_path=clip.local_path,
                public_url=clip.public_url,
                caption=clip.caption,
                start_time=clip.start_time,
                duration=clip.duration,
                source_type=clip.source_type,
                source_label=clip.source_label,
                material_analysis=clip.material_analysis,
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


def _apply_mapping_overrides_to_preview(
    preview: StructurePreviewResponse,
    mapping_overrides: list[TransferMappingOverride],
) -> StructurePreviewResponse:
    if not mapping_overrides:
        return preview

    updated_template = apply_slot_level_overrides(preview.template, mapping_overrides)
    override_lookup = {item.slot_id: item for item in mapping_overrides}

    updated_mappings = [
        _apply_mapping_override(mapping, override_lookup.get(mapping.slot_id))
        for mapping in preview.transfer_plan.mappings
    ]
    updated_tracks = [
        _apply_track_override(track, override_lookup.get(track.slot_id))
        for track in preview.composition.tracks
    ]

    return preview.model_copy(
        deep=True,
        update={
            "template": updated_template,
            "transfer_plan": preview.transfer_plan.model_copy(
                update={
                    "mappings": updated_mappings,
                }
            ),
            "composition": preview.composition.model_copy(
                update={
                    "tracks": updated_tracks,
                }
            ),
            "shot_evidence_graph": updated_template.shot_evidence_graph,
        },
    )


def _apply_mapping_override(
    mapping: TransferMapping,
    override: Optional[TransferMappingOverride],
) -> TransferMapping:
    if override is None:
        return mapping

    update: dict[str, str] = {}
    if override.target_message.strip():
        update["target_message"] = override.target_message.strip()
    if override.asset_strategy.strip():
        asset_strategy = override.asset_strategy.strip()
        update["asset_strategy"] = asset_strategy
        update["fallback_strategy"] = asset_strategy
    if not update:
        return mapping
    return mapping.model_copy(update=update)


def _apply_track_override(
    track: CompositionTrack,
    override: Optional[TransferMappingOverride],
) -> CompositionTrack:
    if (
        override is None
        or track.type != "caption"
        or not override.target_message.strip()
    ):
        return track
    return track.model_copy(update={"text": override.target_message.strip()})


def _analysis_source(
    template_override: Optional[TemplateStructure],
    ai_template: Optional[TemplateStructure],
) -> str:
    template = template_override or ai_template
    if template is None:
        return "rule"
    return template.analysis_summary.source


def _analysis_trace_message(source: str) -> str:
    if source == "ai":
        return "已完成 AI 视频结构拆解，并提取脚本槽位、节奏摘要和包装要点。"
    if source == "fallback":
        return "AI 结构拆解未完成，已使用基础兜底拆解继续生成。"
    return "已从样例中拆出脚本槽位、节奏摘要和包装要点。"
