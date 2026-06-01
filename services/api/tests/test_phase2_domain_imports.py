import app.domain.structure.composition_builder as composition_builder
import app.domain.structure.input_normalizer as input_normalizer
import app.domain.structure.material_gap_builder as material_gap_builder
import app.domain.structure.template_builder as template_builder
import app.domain.structure.transfer_planner as transfer_planner
from app import models as legacy_models
from app.domain.shared.domain_models import (
    CompositionTrack,
    CompositionSpec,
    MaterialGap,
    StructureSlot,
    TemplateStructure,
    TransferPlan,
)


def test_phase2_domain_imports_share_legacy_model_symbols():
    assert StructureSlot is legacy_models.StructureSlot
    assert TemplateStructure is legacy_models.TemplateStructure
    assert MaterialGap is legacy_models.MaterialGap
    assert CompositionSpec is legacy_models.CompositionSpec
    assert CompositionTrack is legacy_models.CompositionTrack
    assert TransferPlan is legacy_models.TransferPlan


def test_phase2_domain_builders_depend_on_domain_model_facade():
    assert "from app.domain.shared.domain_models import" in open(input_normalizer.__file__).read()
    assert "from app.domain.shared.domain_models import" in open(template_builder.__file__).read()
    assert "from app.domain.shared.domain_models import" in open(transfer_planner.__file__).read()
    assert "from app.domain.shared.domain_models import" in open(material_gap_builder.__file__).read()
    assert "from app.domain.shared.domain_models import" in open(composition_builder.__file__).read()
