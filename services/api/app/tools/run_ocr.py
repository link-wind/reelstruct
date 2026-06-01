from app.api.api_models import SampleEvidenceRequest
from app.sample_evidence_service import generate_sample_ocr_evidence


def handle(payload: dict) -> dict:
    request = SampleEvidenceRequest(**payload)
    graph = generate_sample_ocr_evidence(request)
    return {"shot_evidence_graph": graph.model_dump()}
