import ast
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1] / "app"

ALLOWED_LEGACY_MODEL_IMPORT_FILES = {
    "api/api_models.py",
    "domain/shared/domain_models.py",
    "workflow/workflow_models.py",
}


def test_phase2_remaining_legacy_model_import_surface_is_explicit():
    actual = {
        path.relative_to(APP_ROOT).as_posix()
        for path in APP_ROOT.rglob("*.py")
        if _imports_legacy_models(path)
    }
    assert actual == ALLOWED_LEGACY_MODEL_IMPORT_FILES


def _imports_legacy_models(path: Path) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module == "app.models":
                return True
            if node.module == "app" and any(alias.name == "models" for alias in node.names):
                return True
        if isinstance(node, ast.Import):
            if any(alias.name == "app.models" for alias in node.names):
                return True
    return False
