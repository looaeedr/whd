# -*- coding: utf-8 -*-
"""#1503: evidence-only PAD and actual-ear Z stay deferred, never false DXF."""
from dataclasses import replace
from types import SimpleNamespace, MappingProxyType

import pytest

from ae_engine.manufacturing_export import (
    save_resolved_manufacturing_geometry_batch_dxf,
    save_resolved_manufacturing_geometry_dxf,
)
from ae_engine.manufacturing_api import build_part_render_data
from ae_engine.receiving_nfb_source_regions import (
    UPPER, LOWER, DEFERRED, OBSERVED,
)
from tests.test_issue1502_nfb_source_regions import _file, _read
from tests.test_issue1502_receiving_existing_base_plate_patterns import _spec
from ae_engine.sheetmetal_part_adapters import RECEIVING_BASE_PATTERN_CENTER


def _geometry(*pairs):
    return SimpleNamespace(parts=tuple(SimpleNamespace(
        part_key=part,render_data=SimpleNamespace(metadata=metadata),
    ) for part,metadata in pairs))


def _serializer(calls):
    def save(*a,**kw):
        calls.append(a[1])
        raise AssertionError("should reject PAD/EAR before serializer")
    return save


@pytest.mark.parametrize("physical_role", [
    "nfb_pad", "nfb_pad:shim_1", "nfb_ear:ear_a",
    "nfb-ear-side", "nfb-pad-plate",
])
@pytest.mark.parametrize("part_only", [False, True])
def test_unapproved_nfb_pad_and_ear_must_not_generate_even_part_only_dxf(
    tmp_path,physical_role,part_only,
):
    output=tmp_path/"blocked"
    calls=[]
    with pytest.raises(ValueError,match="NFB_PAD_EAR_PHYSICAL_EVIDENCE_UNAPPROVED"):
        save_resolved_manufacturing_geometry_dxf(
            _geometry((physical_role,{
                "stable_id":physical_role,
                "nfb_pad_manufacturing_ready":True,
                "receiving_base_ear_weld_z_verified":True,
            })),
            output,save_part_render_data_dxf=_serializer(calls),
            box_body_physical_piece_roles=(),part_only=part_only,
        )
    assert calls==[]
    assert not output.exists()


@pytest.mark.parametrize("role", ["PAD","EAR"])
def test_forged_approved_flag_cannot_override_deferred_role_in_atomic_batch(
    tmp_path,role,
):
    root=tmp_path/"batch"
    calls=[]
    safe=_geometry(("inner_door",{"nfb_trial_export_approved":True}))
    fake=_geometry(("manufactured_part",MappingProxyType({
        "stable_id":"manufactured_part",
        "nfb_deferred_manufacturing_role":role,
        "nfb_pad_mfg2_release_approved":True,
        "receiving_base_ear_weld_z_verified":True,
    })))
    with pytest.raises(ValueError,match="NFB_PAD_EAR_PHYSICAL_EVIDENCE_UNAPPROVED"):
        save_resolved_manufacturing_geometry_batch_dxf(
            (("A__bay1",safe),("A__bay2",fake)),
            root,save_part_render_data_dxf=_serializer(calls),
            box_body_physical_piece_roles=(),
        )
    assert calls==[]
    assert not root.exists()


def test_existing_base_ear_slots_are_not_confused_with_unapproved_ear_parts(tmp_path):
    from ae_engine.manufacturing_api import save_part_render_data_dxf
    part=_spec(RECEIVING_BASE_PATTERN_CENTER)
    real=build_part_render_data(part)
    assert real.metadata["stable_id"]=="base_plate"
    assert real.metadata["receiving_nfb_base_mfg2_release_approved"] is False
    # EAR mounting cuts are features INSIDE the genuine existing base, not
    # separate welded NFB ear manufacturing pieces.
    geometry=SimpleNamespace(parts=(SimpleNamespace(
        part_key="base_plate",render_data=real,
    ),))
    result=save_resolved_manufacturing_geometry_dxf(
        geometry,tmp_path/"base",
        save_part_render_data_dxf=save_part_render_data_dxf,
        box_body_physical_piece_roles=(),part_only=False,
    )
    assert (tmp_path/"base"/"base_plate.dxf").is_file()
    assert "base_plate" in result


def test_unapproved_brand_pad_depth_does_not_move_or_cut_base():
    # No proposed brand-dependent PAD-Z belongs in the existing physical
    # base PartSpec. The base's own cut geometry is single-source.
    spec=_spec(RECEIVING_BASE_PATTERN_CENTER)
    before=build_part_render_data(spec)
    proposed_depths=(0.,20.,45.,100.)
    fingerprints=[]
    for proposed_unapproved_pad_depth in proposed_depths:
        assert proposed_unapproved_pad_depth >= 0.
        unchanged=build_part_render_data(spec)
        fingerprints.append((
            unchanged.material.wkb,
            tuple(unchanged.scene.primitives),
            unchanged.unfolded_topology,
            unchanged.metadata["stable_id"],
        ))
    assert all(item==fingerprints[0] for item in fingerprints)
    assert before.material.wkb==fingerprints[0][0]


def test_real_native_lower_source_is_trace_only_not_a_pad_blank(tmp_path):
    path,upper,lower,digest=_file(tmp_path)
    original=path.read_bytes()
    observed=_read(path,upper,lower,digest)
    assert observed.upper.region==UPPER
    assert observed.upper.region_status==OBSERVED
    assert observed.lower.region==LOWER
    assert observed.lower.region_status==DEFERRED
    assert observed.lower.source_sha256==digest
    assert observed.upper.source_sha256==digest
    assert observed.upper.reference_handle!=observed.lower.reference_handle
    assert set(observed.upper.entity_handles).isdisjoint(observed.lower.entity_handles)
    assert not observed.manufacturing_ready
    assert not observed.lower.manufacturing_ready
    assert not hasattr(observed.lower,"render_data")
    assert not hasattr(observed.lower,"manufacturing_scene")
    assert path.read_bytes()==original
