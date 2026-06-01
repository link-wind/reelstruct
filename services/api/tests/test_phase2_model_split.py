from app import models as legacy_models
from app.api import DemoRunResponse as DemoRunResponsePkg
from app.api import PreviewRunRequest as PreviewRunRequestPkg
from app.api import SampleUploadResponse as SampleUploadResponsePkg
from app.api import StructurePreviewRequest as StructurePreviewRequestPkg
from app.api import StructurePreviewResponse as StructurePreviewResponsePkg
from app.domain.shared.domain_models import CompositionSpec, MaterialGap, StructureSlot, TemplateStructure, TransferPlan
from app.domain.shared import CompositionSpec as CompositionSpecPkg
from app.domain.shared import MaterialGap as MaterialGapPkg
from app.domain.shared import StructureSlot as StructureSlotPkg
from app.domain.shared import TemplateStructure as TemplateStructurePkg
from app.domain.shared import TransferPlan as TransferPlanPkg
from app.api.api_models import DemoRunResponse, PreviewRunRequest, SampleUploadResponse, StructurePreviewRequest, StructurePreviewResponse
from app.workflow import EvaluationSummary as EvaluationSummaryPkg
from app.workflow import RunTraceEvent as RunTraceEventPkg
from app.workflow.workflow_models import EvaluationSummary, RunTraceEvent


def test_phase2_model_split_imports_are_available():
    assert StructureSlot is legacy_models.StructureSlot
    assert StructureSlotPkg is legacy_models.StructureSlot
    assert TemplateStructure is legacy_models.TemplateStructure
    assert TemplateStructurePkg is legacy_models.TemplateStructure
    assert CompositionSpec is legacy_models.CompositionSpec
    assert CompositionSpecPkg is legacy_models.CompositionSpec
    assert MaterialGap is legacy_models.MaterialGap
    assert MaterialGapPkg is legacy_models.MaterialGap
    assert TransferPlan is legacy_models.TransferPlan
    assert TransferPlanPkg is legacy_models.TransferPlan
    assert StructurePreviewRequest is legacy_models.StructurePreviewRequest
    assert StructurePreviewRequestPkg is legacy_models.StructurePreviewRequest
    assert StructurePreviewResponse is legacy_models.StructurePreviewResponse
    assert StructurePreviewResponsePkg is legacy_models.StructurePreviewResponse
    assert PreviewRunRequest is legacy_models.PreviewRunRequest
    assert PreviewRunRequestPkg is legacy_models.PreviewRunRequest
    assert DemoRunResponse is legacy_models.DemoRunResponse
    assert DemoRunResponsePkg is legacy_models.DemoRunResponse
    assert SampleUploadResponse is legacy_models.SampleUploadResponse
    assert SampleUploadResponsePkg is legacy_models.SampleUploadResponse
    assert EvaluationSummary is legacy_models.EvaluationSummary
    assert EvaluationSummaryPkg is legacy_models.EvaluationSummary
    assert RunTraceEvent is legacy_models.RunTraceEvent
    assert RunTraceEventPkg is legacy_models.RunTraceEvent
