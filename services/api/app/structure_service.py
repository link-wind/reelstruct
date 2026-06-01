from typing import Optional

from app.domain.structure.composition_builder import build_composition_spec
from app.domain.structure.input_normalizer import (
    apply_delivered_material_tasks_to_content,
    apply_uploaded_slot_assets_to_content,
)
from app.domain.structure.material_gap_builder import detect_material_gaps
from app.domain.structure.template_builder import (
    apply_slot_level_overrides,
    apply_variant_to_template,
    extract_template_structure,
)
from app.domain.structure.transfer_planner import build_transfer_plan
from app.domain.shared.domain_models import (
    MaterialRequestTask,
    NewContentInput,
    SampleVideoInput,
    TemplateStructure,
    SupplementSelection,
    TransferMappingOverride,
)
from app.api.api_models import StructurePreviewResponse
from app.evaluation_service import build_preview_evaluation_summary
from app.video_understanding.transfer_explainer_service import (
    explain_transfer_with_ai,
)


def build_structure_preview(
    sample: SampleVideoInput,
    content: NewContentInput,
    template_override: Optional[TemplateStructure] = None,
    ai_template: Optional[TemplateStructure] = None,
    mapping_overrides: Optional[list[TransferMappingOverride]] = None,
    material_request_sheet: Optional[list[MaterialRequestTask]] = None,
    supplement_selections: Optional[list[SupplementSelection]] = None,
    variant: str = "standard",
    use_ai_transfer_explanation: bool = False,
) -> StructurePreviewResponse:
    selected_template = template_override or ai_template
    template = selected_template.model_copy(deep=True) if selected_template is not None else extract_template_structure(sample)
    template = apply_variant_to_template(template, variant)
    template = apply_slot_level_overrides(template, mapping_overrides)
    effective_content = apply_delivered_material_tasks_to_content(template, content, material_request_sheet)
    effective_content = apply_uploaded_slot_assets_to_content(template, effective_content)
    gaps = detect_material_gaps(template, effective_content)
    transfer_plan = build_transfer_plan(
        template,
        effective_content,
        gaps,
        variant=variant,
        mapping_overrides=mapping_overrides,
        material_request_sheet=material_request_sheet,
        supplement_selections=supplement_selections,
    )
    if use_ai_transfer_explanation:
        transfer_plan = explain_transfer_with_ai(
            template=template,
            content=effective_content,
            transfer_plan=transfer_plan,
            graph=getattr(template, "shot_evidence_graph", None),
            variant=variant,
        )
    composition = build_composition_spec(template, transfer_plan, effective_content)
    evaluation_summary = build_preview_evaluation_summary(
        gap_count=len(gaps),
        graph_available=bool(template.shot_evidence_graph and template.shot_evidence_graph.segments),
        can_reuse_count=sum(1 for gap in gaps if gap.retrieval_status in {"可复用", "可包装后使用"}),
    )
    return StructurePreviewResponse(
        template=template,
        transfer_plan=transfer_plan,
        composition=composition,
        shot_evidence_graph=template.shot_evidence_graph,
        evaluation_summary=evaluation_summary,
    )
