"""#2517: the *existing* verified Engine batch accepts trusted source dimensions.

CADSplit must not construct BoxBody/EndCap PartSpecs or infer FW/Fold/Corner.
The Engine's existing factory resolver and verified DXF sink remain sole owners.
"""
from pathlib import Path

import ezdxf
import pytest

from ae_engine.contracts import ManufacturingContext
from ae_engine.integration_api import (
    ManufacturingResolvedBayInput,
    ManufacturingSourceIdentity,
    export_verified_resolved_integration_bays,
)

REPO = Path(__file__).resolve().parents[1]
P1 = {"w": 800.0, "h": 1600.0, "d": 350.0, "t": 2.0}


def _bay(*, set_id="Set1", bay_id="Bay1", source_dimensions=None,
         operator_confirmation="fresh_family_confirmed", **overrides):
    return ManufacturingResolvedBayInput(
        family="受電箱",
        source=ManufacturingSourceIdentity(
            panel_key="P1", source_revision="confirmed-original-dxf",
            set_id=set_id, bay_id=bay_id,
        ),
        source_dimensions_mm=dict(P1) if source_dimensions is None else source_dimensions,
        operator_confirmation=operator_confirmation,
        **overrides,
    )


def test_original_p1_source_dimensions_enter_existing_verified_engine_export(tmp_path):
    dimensions = dict(P1)
    bay = _bay(source_dimensions=dimensions)
    checks = []
    outcome = export_verified_resolved_integration_bays(
        (bay,), tmp_path / "real",
        context=ManufacturingContext(resource_root=REPO),
        pre_commit_guard=lambda: checks.append("verified-source-stable"),
    )
    assert dimensions == P1
    assert checks == ["verified-source-stable", "verified-source-stable"]
    assert outcome.physical_dxf_roundtrip_verified
    assert not outcome.complete_assembly_certified
    assert len(outcome.output_files) == 5
    assert sum("box_body" in Path(path).stem for path in outcome.output_files.values()) == 3
    for filename in outcome.output_files.values():
        doc = ezdxf.readfile(filename)
        assert any(entity.dxf.layer == "CUTTING" for entity in doc.modelspace())


def test_source_set_bay_identity_namespaces_independent_engine_physical_dxf(tmp_path):
    outcome = export_verified_resolved_integration_bays(
        (_bay(set_id="SetA", bay_id="P1"),
         _bay(set_id="SetA", bay_id="P2", source_dimensions={
             "w": 920, "h": 1770, "d": 410, "t": 2.5,
         })),
        tmp_path / "two_bays",
        context=ManufacturingContext(resource_root=REPO),
        pre_commit_guard=lambda: None,
    )
    assert outcome.physical_dxf_roundtrip_verified
    assert len(outcome.output_files) == 10
    names = tuple(str(path) for path in outcome.output_files.values())
    assert len(set(names)) == len(names)
    assert any("SetA__P1" in path for path in names)
    assert any("SetA__P2" in path for path in names)


@pytest.mark.parametrize("options,code", [
    ({"operator_confirmation": None}, "RECEIVING_OPERATOR_CONFIRMATION_REQUIRED"),
    ({"operator_confirmation": "unconfirmed"}, "RECEIVING_OPERATOR_CONFIRMATION_REQUIRED"),
    ({"source_dimensions_mm": {"w": 800, "h": 1600, "d": 350, "t": 2, "fw": 29}},
     "RECEIVING_SOURCE_DIMENSIONS_INVALID"),
    ({"source_dimensions_mm": None}, "RECEIVING_SOURCE_DIMENSIONS_REQUIRED"),
    ({"operator_snapshot": {"model": "受電箱"}},
     "RECEIVING_OPERATOR_CONFIRMATION_AMBIGUOUS"),
])
def test_source_only_and_conflicting_state_never_write_manufacturing_dxf(tmp_path, options, code):
    values = {
        "source_dimensions_mm": dict(P1),
        "operator_confirmation": "fresh_family_confirmed",
    }
    values.update(options)
    bay = ManufacturingResolvedBayInput(
        family="受電箱",
        source=ManufacturingSourceIdentity(
            "P1", "source-revision", "Set1", "Bay1",
        ),
        **values,
    )
    root = tmp_path / "not_produced"
    with pytest.raises(ValueError, match=code):
        export_verified_resolved_integration_bays(
            (bay,), root, context=ManufacturingContext(resource_root=REPO),
            pre_commit_guard=lambda: None,
        )
    assert not root.exists() or not list(root.rglob("*.dxf"))


def test_existing_resolved_and_confirmed_part_inputs_remain_exclusive(tmp_path):
    from ae_engine.manufacturing_api import build_receiving_factory_confirmed_parts
    parts = build_receiving_factory_confirmed_parts(
        P1, confirmation="fresh_family_confirmed",
    )
    bay = _bay(confirmed_parts=parts)
    with pytest.raises(ValueError, match="RECEIVING_AMBIGUOUS_MANUFACTURING_INPUT"):
        export_verified_resolved_integration_bays(
            (bay,), tmp_path / "mixed",
            context=ManufacturingContext(resource_root=REPO),
            pre_commit_guard=lambda: None,
        )
    assert not (tmp_path / "mixed").exists()


def test_saved_operator_option_needs_saved_profile_in_engine_not_cadsplit(tmp_path):
    bay = _bay(
        operator_confirmation="saved_operator_confirmed",
        operator_snapshot={"model": "受電箱", **P1},
    )
    with pytest.raises(ValueError, match="RECEIVING_SAVED_PHYSICAL_STATE_INCOMPLETE"):
        export_verified_resolved_integration_bays(
            (bay,), tmp_path / "invalid",
            context=ManufacturingContext(resource_root=REPO),
            pre_commit_guard=lambda: None,
        )
    assert not (tmp_path / "invalid").exists()
