import ast
from pathlib import Path

from app import models as legacy_models
from app.api import api_models


ROOT = Path(__file__).resolve().parents[1] / "app"

TARGET_FILES = [
    "main.py",
    "sample_service.py",
    "sample_evidence_service.py",
    "material_asset_service.py",
    "material_evidence_service.py",
    "run_record_service.py",
    "run_export_service.py",
    "template_record_service.py",
]

API_MODEL_NAMES = {
    "CompositionSpec",
    "CreateTemplateFromRunRequest",
    "DemoRunResponse",
    "DemoVariantRunsResponse",
    "MaterialEvidenceChunk",
    "MaterialFitAnalysis",
    "PrepareDemoAssetsResponse",
    "PreviewRunRequest",
    "RenderClipPreview",
    "RenderDemoResponse",
    "RunBatchResponse",
    "RunNoteUpdateRequest",
    "RunPinUpdateRequest",
    "RunPreferredUpdateRequest",
    "RunRecordSummary",
    "SampleEvidenceRequest",
    "SampleUploadResponse",
    "SampleVideoInput",
    "StructurePreviewRequest",
    "StructurePreviewResponse",
    "StructureTemplateRecord",
    "StructureTemplateSummary",
    "StructureTemplateVersion",
    "StructureVariantSummary",
    "StructureVariantsResponse",
    "TranscriptUploadResponse",
    "UpdateStructureTemplateRequest",
    "UpdateStructureTemplateSlotRequest",
    "UserSlotAsset",
}


EXPECTED_MODEL_IMPORTS = {
    "main.py": {
        "app.api.api_models": {
            "CompositionSpec",
            "CreateTemplateFromRunRequest",
            "DemoRunResponse",
            "DemoVariantRunsResponse",
            "PrepareDemoAssetsResponse",
            "PreviewRunRequest",
            "RenderClipPreview",
            "RenderDemoResponse",
            "RunBatchResponse",
            "RunNoteUpdateRequest",
            "RunPinUpdateRequest",
            "RunPreferredUpdateRequest",
            "RunRecordSummary",
            "SampleEvidenceRequest",
            "SampleUploadResponse",
            "StructurePreviewRequest",
            "StructurePreviewResponse",
            "StructureTemplateRecord",
            "StructureTemplateSummary",
            "StructureVariantSummary",
            "StructureVariantsResponse",
            "TranscriptUploadResponse",
            "UpdateStructureTemplateRequest",
            "UserSlotAsset",
        },
        "app.domain.shared.domain_models": {
            "TemplateStructure",
        },
    },
    "sample_service.py": {
        "app.api.api_models": {
            "SampleUploadResponse",
            "SampleVideoInput",
            "TranscriptUploadResponse",
        }
    },
    "sample_evidence_service.py": {
        "app.api.api_models": {
            "SampleEvidenceRequest",
        }
    },
    "material_asset_service.py": {
        "app.api.api_models": {
            "MaterialEvidenceChunk",
            "MaterialFitAnalysis",
            "UserSlotAsset",
        }
    },
    "material_evidence_service.py": {
        "app.api.api_models": {
            "MaterialEvidenceChunk",
            "MaterialFitAnalysis",
        }
    },
    "run_record_service.py": {
        "app.api.api_models": {
            "DemoRunResponse",
            "RunBatchResponse",
            "RunRecordSummary",
        }
    },
    "run_export_service.py": {
        "app.api.api_models": {
            "DemoRunResponse",
        },
        "app.domain.shared.domain_models": {
            "MaterialGap",
            "MaterialRequestTask",
        },
    },
    "template_record_service.py": {
        "app.api.api_models": {
            "DemoRunResponse",
            "StructureTemplateRecord",
            "StructureTemplateSummary",
            "StructureTemplateVersion",
            "UpdateStructureTemplateRequest",
        }
    },
}


def test_phase2_api_facade_shares_legacy_model_symbols():
    for name in API_MODEL_NAMES:
        assert hasattr(api_models, name), f"app.api.api_models must re-export {name}"
        assert getattr(api_models, name) is getattr(legacy_models, name)


def test_template_structure_stays_out_of_api_facade():
    assert not hasattr(api_models, "TemplateStructure")
    imported_by_module = _imported_names_by_module("main.py")
    assert "TemplateStructure" in imported_by_module.get("app.domain.shared.domain_models", set())
    assert "TemplateStructure" not in imported_by_module.get("app.api.api_models", set())


def test_phase2_api_route_and_service_imports_use_layered_facades():
    for filename, expected_by_module in EXPECTED_MODEL_IMPORTS.items():
        imported_by_module = _imported_names_by_module(filename)
        for module, names in expected_by_module.items():
            imported_names = imported_by_module.get(module, set())
            missing = names - imported_names
            assert not missing, f"{filename} must import {sorted(missing)} from {module}"
            unexpected = (imported_names & _all_expected_model_names(filename)) - names
            assert not unexpected, f"{filename} imports {sorted(unexpected)} from unexpected module {module}"
        for module, imported_names in imported_by_module.items():
            if module in expected_by_module:
                continue
            unexpected = imported_names & _all_expected_model_names(filename)
            assert not unexpected, f"{filename} imports {sorted(unexpected)} from unexpected module {module}"


def test_phase2_api_targets_do_not_import_legacy_model_module():
    for filename in TARGET_FILES:
        tree = _parse(filename)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert node.module != "app.models", f"{filename} must not import from app.models"
                assert not (
                    node.module == "app" and any(alias.name == "models" for alias in node.names)
                ), f"{filename} must not import app.models through app"
            if isinstance(node, ast.Import):
                assert all(alias.name != "app.models" for alias in node.names), (
                    f"{filename} must not import app.models"
                )


def test_phase2_models_file_is_explicit_compatibility_layer():
    source = (ROOT / "models.py").read_text(encoding="utf-8")
    assert source.startswith("# Phase 2 compatibility layer. Do not add new model definitions here.\n")


def _all_expected_model_names(filename: str) -> set[str]:
    names: set[str] = set()
    for module_names in EXPECTED_MODEL_IMPORTS[filename].values():
        names |= module_names
    return names


def _imported_names_by_module(filename: str) -> dict[str, set[str]]:
    imports: dict[str, set[str]] = {}
    for node in ast.walk(_parse(filename)):
        if not isinstance(node, ast.ImportFrom) or node.module is None:
            continue
        names = {alias.asname or alias.name for alias in node.names}
        imports.setdefault(node.module, set()).update(names)
    return imports


def _parse(filename: str) -> ast.AST:
    return ast.parse((ROOT / filename).read_text(encoding="utf-8"), filename=filename)
