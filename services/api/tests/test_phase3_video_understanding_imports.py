import ast
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1] / "app"
DOMAIN_MODELS_MODULE = "app.domain.shared.domain_models"
LEGACY_MODELS_MODULE = "app.models"


def test_pipeline_imports_domain_models_only():
    imports = _imported_names_from(APP_ROOT / "video_understanding" / "pipeline.py", DOMAIN_MODELS_MODULE)
    assert imports == {"SampleVideoInput", "TemplateStructure"}
    assert not _imports_module(APP_ROOT / "video_understanding" / "pipeline.py", LEGACY_MODELS_MODULE)


def test_template_adapter_imports_domain_models_only():
    imports = _imported_names_from(APP_ROOT / "video_understanding" / "template_adapter.py", DOMAIN_MODELS_MODULE)
    assert imports == {
        "GraphPresentationEdge",
        "GraphPresentationNode",
        "GraphPresentationSummary",
        "SampleAnalysisBeat",
        "SampleAnalysisMetric",
        "SampleAnalysisSummary",
        "StructureSlot",
        "TemplateStructure",
    }
    assert not _imports_module(APP_ROOT / "video_understanding" / "template_adapter.py", LEGACY_MODELS_MODULE)


def _imported_names_from(path: Path, module: str) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == module:
            imported.update(alias.name for alias in node.names)
    return imported


def _imports_module(path: Path, module: str) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module == module:
                return True
            if node.module == "app" and any(alias.name == "models" for alias in node.names):
                return True
        if isinstance(node, ast.Import):
            if any(alias.name == module for alias in node.names):
                return True
            if any(alias.name == "app" for alias in node.names):
                return True
    return False
