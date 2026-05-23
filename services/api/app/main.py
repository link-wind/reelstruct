from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, Response, UploadFile
from fastapi.staticfiles import StaticFiles

from app.fixture_asset_service import build_render_clips_from_composition
from app.models import (
    CreateTemplateFromRunRequest,
    CompositionSpec,
    DemoVariantRunsResponse,
    DemoRunResponse,
    PrepareDemoAssetsResponse,
    RenderClipPreview,
    RenderDemoResponse,
    RunBatchResponse,
    RunPinUpdateRequest,
    RunPreferredUpdateRequest,
    RunNoteUpdateRequest,
    RunRecordSummary,
    SampleUploadResponse,
    StructureTemplateRecord,
    StructureTemplateSummary,
    StructureVariantSummary,
    StructureVariantsResponse,
    TranscriptUploadResponse,
    UpdateStructureTemplateRequest,
    UserSlotAsset,
    StructurePreviewRequest,
    StructurePreviewResponse,
)
from app.material_asset_service import save_material_upload
from app.render_service import render_demo_video
from app.run_record_service import (
    delete_demo_run_record,
    list_demo_run_records,
    load_demo_run_batch,
    load_demo_run_record,
    update_demo_run_note,
    update_demo_run_pinned,
    update_demo_run_preferred,
)
from app.sample_service import extract_transcript_upload, save_sample_upload
from app.structure_service import build_structure_preview
from app.template_record_service import (
    create_structure_template_from_run,
    delete_structure_template_record,
    fork_structure_template_record,
    list_structure_template_records,
    load_structure_template_record,
    rollback_structure_template_record,
    update_structure_template_record,
)
from app.workflow_service import create_demo_run


app = FastAPI(title="ReelStruct API")
STORAGE_DIR = Path(__file__).resolve().parents[1] / "storage"
DOWNLOADS_DIR = STORAGE_DIR / "downloads"
OUTPUT_DIR = STORAGE_DIR / "output"
SAMPLES_DIR = STORAGE_DIR / "samples"
MATERIALS_DIR = STORAGE_DIR / "materials"
RUNS_DIR = STORAGE_DIR / "runs"
TEMPLATES_DIR = STORAGE_DIR / "templates"
DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
MATERIALS_DIR.mkdir(parents=True, exist_ok=True)
RUNS_DIR.mkdir(parents=True, exist_ok=True)
TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)

app.mount("/downloads", StaticFiles(directory=str(DOWNLOADS_DIR)), name="downloads")
app.mount("/output", StaticFiles(directory=str(OUTPUT_DIR)), name="output")
app.mount("/samples", StaticFiles(directory=str(SAMPLES_DIR)), name="samples")
app.mount("/materials", StaticFiles(directory=str(MATERIALS_DIR)), name="materials")


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
        variant=request.variant,
    )


@app.post("/api/structure/variants", response_model=StructureVariantsResponse)
def compare_structure_variants(request: StructurePreviewRequest) -> StructureVariantsResponse:
    template_record = _get_template_record_or_404(request.template_id) if request.template_id else None
    variants = []
    for variant in ("standard", "high_click", "high_conversion", "fast_rhythm"):
        preview = build_structure_preview(
            request.sample,
            request.content,
            template_override=template_record.template if template_record else None,
            mapping_overrides=request.mapping_overrides,
            material_request_sheet=request.material_request_sheet,
            variant=variant,
        )
        mapping_lookup = {item.slot_id: item for item in preview.transfer_plan.mappings}
        variants.append(
            StructureVariantSummary(
                variant=variant,
                title=preview.transfer_plan.title,
                duration=preview.composition.duration,
                hook=mapping_lookup.get("hook").target_message if mapping_lookup.get("hook") else "",
                cta=mapping_lookup.get("cta").target_message if mapping_lookup.get("cta") else "",
                gap_count=len(preview.transfer_plan.gaps),
                rhythm_summary=preview.template.rhythm_summary,
            )
        )
    return StructureVariantsResponse(variants=variants)


@app.post("/api/runs/demo", response_model=DemoRunResponse)
def run_demo_workflow(request: StructurePreviewRequest) -> DemoRunResponse:
    template_record = _get_template_record_or_404(request.template_id) if request.template_id else None
    return create_demo_run(
        request,
        runs_dir=RUNS_DIR,
        template_override=template_record.template if template_record else None,
        template_id=template_record.template_id if template_record else "",
        template_title=template_record.template.title if template_record else "",
        template_tags=template_record.tags if template_record else [],
    )


@app.post("/api/runs/demo-variants", response_model=DemoVariantRunsResponse)
def run_demo_variant_workflows(request: StructurePreviewRequest) -> DemoVariantRunsResponse:
    template_record = _get_template_record_or_404(request.template_id) if request.template_id else None
    batch_id = f"batch-{uuid4().hex[:8]}"
    runs = []
    for variant in ("standard", "high_click", "high_conversion", "fast_rhythm"):
        variant_request = request.model_copy(update={"variant": variant})
        runs.append(
            create_demo_run(
                variant_request,
                runs_dir=RUNS_DIR,
                batch_id=batch_id,
                template_override=template_record.template if template_record else None,
                template_id=template_record.template_id if template_record else "",
                template_title=template_record.template.title if template_record else "",
                template_tags=template_record.tags if template_record else [],
            )
        )
    return DemoVariantRunsResponse(runs=runs)


@app.get("/api/runs/{run_id}", response_model=DemoRunResponse)
def get_run_record(run_id: str) -> DemoRunResponse:
    record = load_demo_run_record(run_id, RUNS_DIR)
    if record is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return record


@app.get("/api/runs/batches/{batch_id}", response_model=RunBatchResponse)
def get_run_batch(batch_id: str) -> RunBatchResponse:
    batch = load_demo_run_batch(batch_id, RUNS_DIR)
    if batch is None:
        raise HTTPException(status_code=404, detail="Batch not found")
    return batch


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


@app.patch("/api/runs/{run_id}/preferred", response_model=DemoRunResponse)
def patch_run_preferred(run_id: str, request: RunPreferredUpdateRequest) -> DemoRunResponse:
    record = update_demo_run_preferred(run_id, request.preferred, RUNS_DIR)
    if record is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return record


@app.get("/api/runs", response_model=list[RunRecordSummary])
def list_run_records(q: str = "", status: str = "", template_id: str = "", tag: str = "") -> list[RunRecordSummary]:
    return list_demo_run_records(RUNS_DIR, q=q, status=status, template_id=template_id, tag=tag)


@app.post("/api/templates/from-run/{run_id}", response_model=StructureTemplateRecord)
def save_template_from_run(run_id: str, request: CreateTemplateFromRunRequest) -> StructureTemplateRecord:
    run = load_demo_run_record(run_id, RUNS_DIR)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return create_structure_template_from_run(run, TEMPLATES_DIR, title=request.title, tags=request.tags)


@app.get("/api/templates", response_model=list[StructureTemplateSummary])
def list_templates(tag: str = "") -> list[StructureTemplateSummary]:
    return list_structure_template_records(TEMPLATES_DIR, tag=tag)


@app.get("/api/templates/{template_id}", response_model=StructureTemplateRecord)
def get_template(template_id: str) -> StructureTemplateRecord:
    return _get_template_record_or_404(template_id)


@app.patch("/api/templates/{template_id}", response_model=StructureTemplateRecord)
def update_template(template_id: str, request: UpdateStructureTemplateRequest) -> StructureTemplateRecord:
    record = update_structure_template_record(template_id, request, TEMPLATES_DIR)
    if record is None:
        raise HTTPException(status_code=404, detail="Template not found")
    return record


@app.post("/api/templates/{template_id}/rollback/{version_id}", response_model=StructureTemplateRecord)
def rollback_template(template_id: str, version_id: str) -> StructureTemplateRecord:
    record = rollback_structure_template_record(template_id, version_id, TEMPLATES_DIR)
    if record is None:
        raise HTTPException(status_code=404, detail="Template version not found")
    return record


@app.post("/api/templates/{template_id}/fork", response_model=StructureTemplateRecord)
def fork_template(template_id: str, request: CreateTemplateFromRunRequest) -> StructureTemplateRecord:
    record = fork_structure_template_record(
        template_id,
        request.title,
        TEMPLATES_DIR,
        tags=request.tags if "tags" in request.model_fields_set else None,
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Template not found")
    return record


@app.delete("/api/templates/{template_id}", status_code=204)
def delete_template(template_id: str) -> Response:
    deleted = delete_structure_template_record(template_id, TEMPLATES_DIR)
    if not deleted:
        raise HTTPException(status_code=404, detail="Template not found")
    return Response(status_code=204)


@app.post("/api/samples/upload", response_model=SampleUploadResponse)
def upload_sample_video(file: UploadFile) -> SampleUploadResponse:
    return save_sample_upload(file, sample_dir=SAMPLES_DIR)


@app.post("/api/samples/upload-transcript", response_model=TranscriptUploadResponse)
def upload_sample_transcript(file: UploadFile) -> TranscriptUploadResponse:
    return extract_transcript_upload(file)


@app.post("/api/materials/upload", response_model=UserSlotAsset)
def upload_material_asset(slot_id: str = Form(...), file: UploadFile = File(...)) -> UserSlotAsset:
    return save_material_upload(file, slot_id=slot_id, material_dir=MATERIALS_DIR)


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
