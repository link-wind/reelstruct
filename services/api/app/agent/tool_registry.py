from typing import Literal

from pydantic import BaseModel, ConfigDict


class ToolDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    title: str
    stage: str
    description: str = ""
    confirmation_kind: Literal["", "run_ocr", "run_asr", "material_strategy", "generate_result"] = ""


def build_default_tool_registry() -> list[ToolDefinition]:
    return [
        ToolDefinition(name="analyze_structure", title="分析结构", stage="structure"),
        ToolDefinition(
            name="run_ocr",
            title="执行 OCR",
            stage="structure",
            confirmation_kind="run_ocr",
        ),
        ToolDefinition(
            name="run_asr",
            title="执行 ASR",
            stage="structure",
            confirmation_kind="run_asr",
        ),
        ToolDefinition(
            name="complete_materials",
            title="补全素材",
            stage="materials",
            confirmation_kind="material_strategy",
        ),
        ToolDefinition(
            name="generate_result",
            title="生成结果",
            stage="output",
            confirmation_kind="generate_result",
        ),
    ]
