from fastapi import FastAPI

from app.models import StructurePreviewRequest, StructurePreviewResponse
from app.structure_service import build_structure_preview


app = FastAPI(title="ReelStruct API")


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/structure/preview", response_model=StructurePreviewResponse)
def preview_structure_transfer(request: StructurePreviewRequest) -> StructurePreviewResponse:
    return build_structure_preview(request.sample, request.content)
