from app.domain.structure.template_builder import apply_variant_to_template, extract_template_structure
from app.models import SampleVideoInput


def test_extract_template_structure_uses_transcript_summary_and_builds_graph():
    template = extract_template_structure(
        SampleVideoInput(
            title="护肤样例",
            duration=18,
            shot_count=5,
            transcript_summary="先讲熬夜脸很垮。再展示精华上脸效果。最后引导现在下单。",
        )
    )

    evidence_lookup = {slot.id: slot.sample_evidence for slot in template.script_pattern}

    assert "先讲熬夜脸很垮" in evidence_lookup["hook"]
    assert "最后引导现在下单" in evidence_lookup["cta"]
    assert template.shot_evidence_graph is not None
    assert template.analysis_summary.graph_presentation is not None


def test_apply_variant_to_template_compresses_fast_rhythm_slots_and_adds_notes():
    base = extract_template_structure(
        SampleVideoInput(
            title="咖啡样例",
            duration=20,
            shot_count=6,
        )
    )

    variant = apply_variant_to_template(base, "fast_rhythm")
    slot_lookup = {slot.id: slot for slot in variant.script_pattern}

    assert "快切节奏" in variant.packaging_notes
    assert "高节奏快切版" in variant.rhythm_summary
    assert slot_lookup["hook"].duration < 3
    assert slot_lookup["cta"].start + slot_lookup["cta"].duration < 20
