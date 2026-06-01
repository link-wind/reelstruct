import ast
from pathlib import Path


MATERIAL_GRAPH_SERVICE_PATH = Path(__file__).resolve().parents[1] / "app" / "material_graph_service.py"
EXPECTED_DOMAIN_MODEL_IMPORTS = {
    "MaterialGraph",
    "MaterialGraphEdge",
    "MaterialGraphMatchedNode",
    "MaterialGraphNode",
    "MaterialGraphSearchResult",
    "SlotQueryProfile",
    "UserSlotAsset",
}
DOMAIN_MODEL_MODULE = "app.domain.shared.domain_models"


def test_material_graph_service_imports_domain_models_only():
    tree = ast.parse(MATERIAL_GRAPH_SERVICE_PATH.read_text(encoding="utf-8"), filename=str(MATERIAL_GRAPH_SERVICE_PATH))

    imported_from_domain_models = set()
    forbidden_imports = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module == DOMAIN_MODEL_MODULE:
                imported_from_domain_models.update(alias.name for alias in node.names)
            if node.module == "app.models":
                forbidden_imports.append("from app.models import ...")
            if node.module == "app":
                forbidden_imports.append("from app import ...")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "app.models":
                    forbidden_imports.append("import app.models")
                if alias.name == "app":
                    forbidden_imports.append("import app")

    assert imported_from_domain_models == EXPECTED_DOMAIN_MODEL_IMPORTS
    assert forbidden_imports == []
