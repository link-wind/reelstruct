import ast
from pathlib import Path


STRUCTURE_SERVICE = Path(__file__).resolve().parents[1] / "app" / "structure_service.py"

DOMAIN_MODEL_NAMES = {
    "MaterialRequestTask",
    "NewContentInput",
    "SampleVideoInput",
    "TemplateStructure",
    "SupplementSelection",
    "TransferMappingOverride",
}


def test_structure_service_imports_models_from_phase3_facades():
    tree = ast.parse(STRUCTURE_SERVICE.read_text(encoding="utf-8"), filename=str(STRUCTURE_SERVICE))
    imported_by_module: dict[str, set[str]] = {}

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            imported_by_module.setdefault(node.module, set()).update(alias.asname or alias.name for alias in node.names)
            assert node.module != "app.models"
            assert not (node.module == "app" and any(alias.name == "models" for alias in node.names))
        if isinstance(node, ast.Import):
            assert all(alias.name != "app.models" for alias in node.names)

    assert imported_by_module.get("app.domain.shared.domain_models", set()) == DOMAIN_MODEL_NAMES
    assert imported_by_module.get("app.api.api_models", set()) == {"StructurePreviewResponse"}
