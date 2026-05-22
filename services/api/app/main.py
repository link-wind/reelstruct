from pathlib import Path

from fastapi import FastAPI, HTTPException, Response, UploadFile
from fastapi.staticfiles import StaticFiles

from app.fixture_asset_service import build_render_clips_from_composition
from app.models import (
    CompositionSpec,
    DemoRunResponse,
    PrepareDemoAssetsResponse,
    RenderClipPreview,
    RenderDemoResponse,
    RunPinUpdateRequest,
    RunNoteUpdateRequest,
    RunRecordSummary,
    SampleUploadResponse,
    StructureTemplateRecord,
    StructureTemplateSummary,
    TranscriptUploadResponse,
    StructurePreviewRequest,
    StructurePreviewResponse,
)
from app.render_service import render_demo_video
from app.run_record_service import (
    delete_demo_run_record,
    list_demo_run_records,
    load_demo_run_record,
    update_demo_run_note,
    update_demo_run_pinned,
)
from app.sample_service import extract_transcript_upload, save_sample_upload
from app.structure_service import build_structure_preview
from app.template_record_service import (
    create_structure_template_from_run,
    list_structure_template_records,
    load_structure_template_record,
)
from app.workflow_service import create_demo_run


app = FastAPI(title="ReelStruct API")
STORAGE_DIR = Path(__file__).resolve().parents[1] / "storage"
DOWNLOADS_DIR = STORAGE_DIR / "downloads"
OUTPUT_DIR = STORAGE_DIR / "output"
SAMPLES_DIR = STORAGE_DIR / "samples"
RUNS_DIR = STORAGE_DIR / "runs"
TEMPLATES_DIR = STORAGE_DIR / "templates"
DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
RUNS_DIR.mkdir(parents=True, exist_ok=True)
TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)

app.mount("/downloads", StaticFiles(directory=str(DOWNLOADS_DIR)), name="downloads")
app.mount("/output", StaticFiles(directory=str(OUTPUT_DIR)), name="output")
app.mount("/samples", StaticFiles(directory=str(SAMPLES_DIR)), name="samples")


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/structure/preview", response_model=StructurePreviewResponse)
def preview_structure_transfer(request: StructurePreviewRequest) -> StructurePreviewResponse:
    template_record = _get_template_record_or_404(request.template_id) if request.template_id else None
    return build_structure_preview(
        request.sample,
        request.content,
        template_override=template_record.template if template_record else None,
        mapping_overrides=request.mapping_overrides,
        material_request_sheet=request.material_request_sheet,
    )


@app.post("/api/runs/demo", response_model=DemoRunResponse)
def run_demo_workflow(request: StructurePreviewRequest) -> DemoRunResponse:
    template_record = _get_template_record_or_404(request.template_id) if request.template_id else None
    return create_demo_run(
        request,
        runs_dir=RUNS_DIR,
        template_override=template_record.template if template_record else None,
    )


@app.get("/api/runs/{run_id}", response_model=DemoRunResponse)
def get_run_record(run_id: str) -> DemoRunResponse:
    record = load_demo_run_record(run_id, RUNS_DIR)
    if record is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return record


@app.delete("/api/runs/{run_id}", status_code=204)
def delete_run_record(run_id: str) -> Response:
    deleted = delete_demo_run_record(run_id, RUNS_DIR)
    if not deleted:
        raise HTTPException(status_code=404, detail="Run not found")
    return Response(status_code=204)


@app.patch("/api/runs/{run_id}/note", response_model=DemoRunResponse)
def patch_run_note(run_id: str, request: RunNoteUpdateRequest) -> DemoRunResponse:
    record = update_demo_run_note(run_id, request.note, RUNS_DIR)
    if record is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return record


@app.patch("/api/runs/{run_id}/pin", response_model=DemoRunResponse)
def patch_run_pin(run_id: str, request: RunPinUpdateRequest) -> DemoRunResponse:
    record = update_demo_run_pinned(run_id, request.pinned, RUNS_DIR)
    if record is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return record


@app.get("/api/runs", response_model=list[RunRecordSummary])
def list_run_records(q: str = "", status: str = "") -> list[RunRecordSummary]:
    return list_demo_run_records(RUNS_DIR, q=q, status=status)


@app.post("/api/templates/from-run/{run_id}", response_model=StructureTemplateRecord)
def save_template_from_run(run_id: str) -> StructureTemplateRecord:
    run = load_demo_run_record(run_id, RUNS_DIR)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return create_structure_template_from_run(run, TEMPLATES_DIR)


@app.get("/api/templates", response_model=list[StructureTemplateSummary])
def list_templates() -> list[StructureTemplateSummary]:
    return list_structure_template_records(TEMPLATES_DIR)


@app.get("/api/templates/{template_id}", response_model=StructureTemplateRecord)
def get_template(template_id: str) -> StructureTemplateRecord:
    return _get_template_record_or_404(template_id)


@app.post("/api/samples/upload", response_model=SampleUploadResponse)
def upload_sample_video(file: UploadFile) -> SampleUploadResponse:
    return save_sample_upload(file, sample_dir=SAMPLES_DIR)


@app.post("/api/samples/upload-transcript", response_model=TranscriptUploadResponse)
def upload_sample_transcript(file: UploadFile) -> TranscriptUploadResponse:
    return extract_transcript_upload(file)


@app.post("/api/media/prepare-demo-assets", response_model=PrepareDemoAssetsResponse)
def prepare_demo_assets(composition: CompositionSpec) -> PrepareDemoAssetsResponse:
    clips = build_render_clips_from_composition(composition)
    return PrepareDemoAssetsResponse(
        clips=[
            RenderClipPreview(
                scene_id=clip.scene_id,
                local_path=clip.local_path,
                public_url=clip.public_url,
                caption=clip.caption,
                start_time=clip.start_time,
                duration=clip.duration,
            )
            for clip in clips
        ]
    )


@app.post("/api/media/render-demo", response_model=RenderDemoResponse)
def render_demo(composition: CompositionSpec) -> RenderDemoResponse:
    clips = build_render_clips_from_composition(composition)
    result = render_demo_video(clips, output_filename="demo.mp4")
    return RenderDemoResponse(video_url=result.video_url, local_path=result.local_path)


def _get_template_record_or_404(template_id: str) -> StructureTemplateRecord:
    record = load_structure_template_record(template_id, TEMPLATES_DIR)
    if record is None:
        raise HTTPException(status_code=404, detail="Template not found")
    return record
