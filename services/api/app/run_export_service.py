from io import BytesIO
from pathlib import Path
from typing import Optional
from zipfile import ZIP_DEFLATED, ZipFile

from app.models import DemoRunResponse, MaterialGap, MaterialRequestTask


def build_run_export_zip(run: DemoRunResponse) -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, mode="w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("run.json", run.model_dump_json(indent=2))
        archive.writestr("material-request-sheet.txt", build_material_request_sheet_text(run))
        archive.writestr("material-sources.txt", build_material_sources_text(run))

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
