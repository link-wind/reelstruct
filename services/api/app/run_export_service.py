from io import BytesIO
from pathlib import Path
from typing import Optional
from zipfile import ZIP_DEFLATED, ZipFile

from app.api.api_models import DemoRunResponse
from app.domain.shared.domain_models import MaterialGap, MaterialRequestTask


def build_run_export_zip(run: DemoRunResponse) -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, mode="w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("run.json", run.model_dump_json(indent=2))
        archive.writestr("material-request-sheet.txt", build_material_request_sheet_text(run))
        archive.writestr("material-sources.txt", build_material_sources_text(run))
        archive.writestr("material-analysis.txt", build_material_analysis_text(run))
        archive.writestr("packaging-plan.txt", build_packaging_plan_text(run))
        archive.writestr("ai-structure-analysis.txt", build_ai_structure_analysis_text(run))

        video_path = Path(run.rendered_video.local_path)
        if video_path.is_file():
            archive.write(video_path, "final-demo.mp4")

    return buffer.getvalue()


def build_material_request_sheet_text(run: DemoRunResponse) -> str:
    tasks = run.preview.transfer_plan.material_request_sheet
    if not tasks:
        return "素材需求单\n当前 run 没有素材需求单。"

    gap_lookup = {gap.slot_id: gap for gap in run.preview.transfer_plan.gaps}
    lines = ["素材需求单", "待执行素材任务", ""]
    for index, task in enumerate(tasks, start=1):
        gap = gap_lookup.get(task.slot_id)
        lines.extend(
            [
                f"{index}. {task.slot_id}",
                _material_task_text(task, gap),
                "",
            ]
        )
    return "\n".join(lines).strip()


def build_material_sources_text(run: DemoRunResponse) -> str:
    lines = ["素材来源说明", ""]
    if not run.prepared_assets:
        lines.append("当前 run 没有可渲染素材。")
        return "\n".join(lines).strip()

    for index, asset in enumerate(run.prepared_assets, start=1):
        lines.extend(
            [
                f"{index}. {asset.scene_id}",
                f"来源类型：{asset.source_type or 'unknown'}",
                f"来源说明：{asset.source_label or asset.public_url}",
                f"文件：{asset.public_url}",
                "",
            ]
        )
    return "\n".join(lines).strip()


def build_packaging_plan_text(run: DemoRunResponse) -> str:
    lines = ["画面包装方案", ""]
    mappings = run.preview.transfer_plan.mappings
    if not mappings:
        lines.append("当前 run 没有包装方案。")
        return "\n".join(lines).strip()

    for index, mapping in enumerate(mappings, start=1):
        packaging = mapping.packaging
        lines.extend(
            [
                f"{index}. {mapping.source_label}（{mapping.slot_id}）",
                f"标题卡片：{packaging.title_card or '不单独使用标题卡片'}",
                f"包装卡片：{packaging.card_text or '不单独使用包装卡片'}",
                f"字幕密度：{packaging.caption_density}",
                f"强调词：{' / '.join(packaging.emphasis_words) if packaging.emphasis_words else '无'}",
                f"转场提示：{packaging.transition_hint or '跟随原结构节奏'}",
                f"封面提示：{packaging.cover_hint or '从主视觉中选择'}",
                "",
            ]
        )
    return "\n".join(lines).strip()


def build_material_analysis_text(run: DemoRunResponse) -> str:
    lines = ["真实素材适配说明", ""]
    uploaded_assets = [
        asset for asset in run.prepared_assets
        if asset.source_type == "uploaded" and asset.material_analysis.recommended_slot_id
    ]
    if not uploaded_assets:
        lines.append("当前 run 没有带分析结果的真实上传素材。")
        return "\n".join(lines).strip()

    for index, asset in enumerate(uploaded_assets, start=1):
        analysis = asset.material_analysis
        lines.extend(
            [
                f"{index}. {asset.scene_id}",
                f"文件：{asset.public_url}",
                f"时长：{analysis.duration}s",
                f"镜头数：{analysis.shot_count}",
                f"推荐槽位：{analysis.recommended_slot_label}",
                f"推荐理由：{analysis.recommendation_reason}",
                "适配分："
                f"Hook {analysis.slot_fit_scores.get('hook', 0)} / "
                f"卖点 {analysis.slot_fit_scores.get('selling_points', 0)} / "
                f"使用过程 {analysis.slot_fit_scores.get('usage', 0)} / "
                f"CTA {analysis.slot_fit_scores.get('cta', 0)}",
                "",
            ]
        )
    return "\n".join(lines).strip()


def build_ai_structure_analysis_text(run: DemoRunResponse) -> str:
    template = run.preview.template
    summary = template.analysis_summary
    lines = [
        "视频结构拆解证据",
        "",
        f"结构来源：{_analysis_source_text(summary.source)}",
        f"整体置信度：{summary.confidence:.2f}",
        f"拆解标题：{summary.headline}",
        f"节奏摘要：{template.rhythm_summary}",
    ]
    if summary.warnings:
        lines.extend(["", "Warnings:", *[f"- {warning}" for warning in summary.warnings]])

    lines.extend(["", "结构槽位：", ""])
    for index, slot in enumerate(template.script_pattern, start=1):
        lines.extend(
            [
                f"{index}. {slot.label}（{slot.id}）",
                f"时间范围：{slot.start}-{round(slot.start + slot.duration, 1)}s",
                f"证据镜头：{_shot_indices_text(slot.evidence_shot_indices)}",
                f"槽位置信度：{slot.confidence:.2f}",
                f"结构目的：{slot.purpose}",
                f"拆解方法：{slot.method or '未提供'}",
                f"样例证据：{slot.sample_evidence}",
                f"节奏：{slot.rhythm or '未提供'}",
                f"包装：{slot.packaging_intent or '未提供'}",
                f"可迁移规则：{slot.transferable_rule or '保留结构目的，替换具体内容。'}",
                f"不可复制：{slot.non_transferable or '不复制样例具体表达。'}",
                "",
            ]
        )

    return "\n".join(lines).strip()


def _material_task_text(task: MaterialRequestTask, gap: Optional[MaterialGap]) -> str:
    if gap is None:
        return "\n".join(
            [
                f"当前状态：{task.status}",
                "已补齐素材：该槽位已进入可用素材池。",
            ]
        )
    return "\n".join(
        [
            f"当前状态：{task.status}",
            f"缺口素材：{gap.missing_asset}",
            f"补位方式：{gap.fill_strategy}",
            f"建议镜头：{'；'.join(gap.suggested_shots)}",
            f"检查清单：{'；'.join(gap.pickup_checklist)}",
        ]
    )


def _analysis_source_text(source: str) -> str:
    if source == "ai":
        return "AI 视频结构拆解"
    if source == "fallback":
        return "基础兜底拆解"
    return "基础规则拆解"


def _shot_indices_text(indices: list[int]) -> str:
    if not indices:
        return "未绑定具体镜头"
    return " / ".join(str(item) for item in indices)
