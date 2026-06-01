from pathlib import Path

from app import models as legacy_models
from app.api.api_models import PreviewRunRequest, SampleEvidenceRequest
from app.domain.shared.domain_models import (
    MaterialRequestTask,
    NewContentInput,
    SampleVideoInput,
    SupplementSelection,
    TransferMappingOverride,
)
from app.workflow.workflow_models import EvaluationSummary, RunTraceEvent


ROOT = Path(__file__).resolve().parents[1] / "app"


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_phase2_workflow_facades_share_legacy_symbols():
    assert PreviewRunRequest is legacy_models.PreviewRunRequest
    assert SampleEvidenceRequest is legacy_models.SampleEvidenceRequest
    assert MaterialRequestTask is legacy_models.MaterialRequestTask
    assert NewContentInput is legacy_models.NewContentInput
    assert SampleVideoInput is legacy_models.SampleVideoInput
    assert SupplementSelection is legacy_models.SupplementSelection
    assert TransferMappingOverride is legacy_models.TransferMappingOverride
    assert EvaluationSummary is legacy_models.EvaluationSummary
    assert RunTraceEvent is legacy_models.RunTraceEvent


def test_phase2_workflow_files_import_from_split_facades():
    workflow_service_source = _read("workflow_service.py")
    analyze_structure_source = _read("tools/analyze_structure.py")
    complete_materials_source = _read("tools/complete_materials.py")
    generate_result_source = _read("tools/generate_result.py")
    run_ocr_source = _read("tools/run_ocr.py")
    run_asr_source = _read("tools/run_asr.py")
    evaluation_service_source = _read("evaluation_service.py")

    assert "from app.api.api_models import (" in workflow_service_source
    assert "PreviewRunRequest" in workflow_service_source
    assert "StructurePreviewRequest" in workflow_service_source
    assert "StructurePreviewResponse" in workflow_service_source
    assert "DemoRunResponse" in workflow_service_source
    assert "RenderClipPreview" in workflow_service_source
    assert "RenderDemoResponse" in workflow_service_source
    assert "from app.domain.shared.domain_models import (" in workflow_service_source
    assert "CompositionTrack" in workflow_service_source
    assert "TemplateStructure" in workflow_service_source
    assert "TransferMapping" in workflow_service_source
    assert "TransferMappingOverride" in workflow_service_source
    assert "from app.workflow.workflow_models import EvaluationSummary, RunTraceEvent" in workflow_service_source

    assert "from app.domain.shared.domain_models import (" in analyze_structure_source
    assert "MaterialRequestTask" in analyze_structure_source
    assert "NewContentInput" in analyze_structure_source
    assert "SampleVideoInput" in analyze_structure_source
    assert "SupplementSelection" in analyze_structure_source
    assert "TransferMappingOverride" in analyze_structure_source

    assert "from app.domain.shared.domain_models import (" in complete_materials_source
    assert "MaterialRequestTask" in complete_materials_source
    assert "NewContentInput" in complete_materials_source
    assert "SampleVideoInput" in complete_materials_source
    assert "SupplementSelection" in complete_materials_source
    assert "TransferMappingOverride" in complete_materials_source

    assert "from app.api.api_models import PreviewRunRequest" in generate_result_source
    assert "from app.api.api_models import SampleEvidenceRequest" in run_ocr_source
    assert "from app.api.api_models import SampleEvidenceRequest" in run_asr_source
    assert "from app.workflow.workflow_models import EvaluationSummary" in evaluation_service_source

    migrated_sources = [
        workflow_service_source,
        analyze_structure_source,
        complete_materials_source,
        generate_result_source,
        run_ocr_source,
        run_asr_source,
        evaluation_service_source,
    ]
    for source in migrated_sources:
        assert "from app.models import" not in source
        assert "from app import models" not in source
