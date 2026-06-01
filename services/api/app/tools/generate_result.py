from app.api.api_models import PreviewRunRequest
from app.workflow_service import create_demo_run_from_preview


def handle(payload: dict) -> dict:
    request = PreviewRunRequest(**payload)
    run = create_demo_run_from_preview(request)
    return {"run": run.model_dump()}
