from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.domain.shared.domain_models import (
    MaterialRequestTask,
    NewContentInput,
    SampleVideoInput,
    SupplementSelection,
    TransferMappingOverride,
)
from app.template_record_service import load_structure_template_record
from app.structure_service import build_structure_preview
from app.video_understanding.pipeline import build_ai_or_fallback_structure_template
from app.video_understanding.schemas import ShotEvidenceGraph

TEMPLATES_DIR = Path(__file__).resolve().parents[2] / "storage" / "templates"


class AnalyzeStructureRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sample: SampleVideoInput
    content: NewContentInput
    sample_local_path: str = ""
    use_ai_structure: bool = False
    shot_evidence_graph: Optional[ShotEvidenceGraph] = None
    template_id: str = ""
    mapping_overrides: list[TransferMappingOverride] = Field(default_factory=list)
    material_request_sheet: list[MaterialRequestTask] = Field(default_factory=list)
    supplement_selections: list[SupplementSelection] = Field(default_factory=list)
    variant: Literal["standard", "high_click", "high_conversion", "fast_rhythm"] = "standard"
    use_ai_transfer_explanation: bool = False


def handle(payload: dict) -> dict:
    request = AnalyzeStructureRequest(**payload)
    template_record = load_structure_template_record(request.template_id, TEMPLATES_DIR) if request.template_id else None
    ai_template = None
    if request.use_ai_structure and request.sample_local_path.strip() and template_record is None:
        kwargs = {
            "sample": request.sample,
            "sample_local_path": request.sample_local_path,
        }
        if request.shot_evidence_graph is not None:
            kwargs["text_evidence_graph"] = request.shot_evidence_graph
        ai_template = build_ai_or_fallback_structure_template(**kwargs)
    preview = build_structure_preview(
        sample=request.sample,
        content=request.content,
        template_override=template_record.template if template_record else None,
        ai_template=ai_template,
        mapping_overrides=request.mapping_overrides,
        material_request_sheet=request.material_request_sheet,
        supplement_selections=request.supplement_selections,
        variant=request.variant,
        use_ai_transfer_explanation=request.use_ai_transfer_explanation,
    )
    return {"preview": preview.model_dump()}
