import ast
from pathlib import Path


SLOT_PROFILE_SERVICE_PATH = Path(__file__).resolve().parents[1] / "app" / "slot_profile_service.py"
EXPECTED_DOMAIN_MODEL_IMPORTS = {
    "NewContentInput",
    "SlotQueryProfile",
    "StructureSlot",
}
DOMAIN_MODEL_MODULE = "app.domain.shared.domain_models"


def test_slot_profile_service_imports_domain_models_only():
    tree = ast.parse(SLOT_PROFILE_SERVICE_PATH.read_text(encoding="utf-8"), filename=str(SLOT_PROFILE_SERVICE_PATH))

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
