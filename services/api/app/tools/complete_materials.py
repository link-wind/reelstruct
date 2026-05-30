from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models import (
    MaterialRequestTask,
    NewContentInput,
    SampleVideoInput,
    SupplementSelection,
    TransferMappingOverride,
)
from app.structure_service import build_structure_preview


class CompleteMaterialsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sample: SampleVideoInput
    content: NewContentInput
    mapping_overrides: list[TransferMappingOverride] = Field(default_factory=list)
    material_request_sheet: list[MaterialRequestTask] = Field(default_factory=list)
    supplement_selections: list[SupplementSelection] = Field(default_factory=list)
    variant: Literal["standard", "high_click", "high_conversion", "fast_rhythm"] = "standard"
    use_ai_transfer_explanation: bool = False


def handle(payload: dict) -> dict:
    request = CompleteMaterialsRequest(**payload)
    preview = build_structure_preview(
        sample=request.sample,
        content=request.content,
        mapping_overrides=request.mapping_overrides,
        material_request_sheet=request.material_request_sheet,
        supplement_selections=request.supplement_selections,
        variant=request.variant,
        use_ai_transfer_explanation=request.use_ai_transfer_explanation,
    )
    return {
        "preview": preview.model_dump(),
        "gaps": [gap.model_dump() for gap in preview.transfer_plan.gaps],
        "material_request_sheet": [task.model_dump() for task in preview.transfer_plan.material_request_sheet],
        "evaluation_summary": preview.evaluation_summary.model_dump(),
    }
