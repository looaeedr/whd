# -*- coding: utf-8 -*-
"""#1502 link Shihlin upper source base process to actual per-cell sheet identity."""
from dataclasses import replace
from types import SimpleNamespace

import pytest

from ae_engine.assembly_placement import resolve_base_plate_placement
from ae_engine.contracts import BasePlatePartSpec
from ae_engine.manufacturing_api import build_part_render_data
from ae_engine.receiving_nfb_base_plate_owner import (
    IDENTIFIED, resolve_upper_nfb_base_plate_owner,
)
from ae_engine.receiving_nfb_upper_base_source import (
    inspect_nfb_upper_base_native_process,
)
from tests.test_issue1502_nfb_middle_plate_physical_shadow import (
    _part, _verified,
)
from tests.test_issue1502_nfb_upper_base_native_process import _source


def _part_data(height):
    render=build_part_render_data(BasePlatePartSpec(
        width=800.,height=float(height),thickness=2.,
        shrink_top=55.,shrink_bottom=55.,
        shrink_left=55.,shrink_right=55.,
        bend=15.,model_name="受電箱",
    ))
    assert render.unfolded_topology is not None
    return render


def _case(tmp_path):
    source,profile,lower,*_=_source(tmp_path)
    nfb=inspect_nfb_upper_base_native_process(
        source,profile=profile,lower_reference_handle=lower,
    )
    snapshot,divider,baseline,datum=_part()
    verified=_verified(snapshot,profile)
    upper=SimpleNamespace(
        part_key="base_plate_c1_r1",render_data=_part_data(1100.)
    )
    lower_plate=SimpleNamespace(
        part_key="base_plate_c1_r2",render_data=_part_data(500.)
    )
    resolved=SimpleNamespace(parts=(upper,lower_plate))
    return snapshot,resolved,verified,nfb


def test_source_is_attached_to_actual_upper_base_plate_not_lower_or_legacy(tmp_path):
    snapshot,resolved,verified,nfb=_case(tmp_path)
    proof=resolve_upper_nfb_base_plate_owner(
        snapshot,resolved,verified_inner_door=verified,source_process=nfb,
    )
    assert proof.status==IDENTIFIED
    assert proof.manufacturing_ready is False
    assert proof.physical_part_id=="base_plate_c1_r1"
    assert proof.receiving_cell_key=="0:0"
    assert proof.assembly_anchor=="door_layout_cell:0:0:base_plate"
    assert proof.nfb_inner_door_part_id==verified.part_id
    assert proof.source_sha256==nfb.source_sha256
    assert proof.source_color150_handle==nfb.upper_color150_handle
    assert proof.unchanged_world_offset==pytest.approx(
        resolve_base_plate_placement(snapshot,"base_plate_c1_r1").world_offset
    )
    assert proof.unchanged_world_offset[1]==pytest.approx(250.)
    assert resolve_base_plate_placement(
        snapshot,"base_plate_c1_r2"
    ).world_offset[1]==pytest.approx(-550.)
    assert proof.physical_blank_width_mm==pytest.approx(720.)
    assert proof.physical_blank_height_mm==pytest.approx(1020.)


@pytest.mark.parametrize("variant",[
    "only_legacy","lower_only","duplicate_upper","invalid_base","missing_material",
    "mismatched_source","stale_handle","false_approval","wrong_upper_cell",
])
def test_ambiguous_or_stale_physical_base_does_not_become_manufacturable(tmp_path,variant):
    snapshot,resolved,verified,nfb=_case(tmp_path)
    upper,lower=resolved.parts
    if variant=="only_legacy":
        resolved=SimpleNamespace(parts=(replace_part(upper,"base_plate"),))
    elif variant=="lower_only":
        resolved=SimpleNamespace(parts=(lower,))
    elif variant=="duplicate_upper":
        resolved=SimpleNamespace(parts=(upper,upper,lower))
    elif variant=="invalid_base":
        resolved=SimpleNamespace(parts=(replace_part(upper,"base_plate_c9_r9"),lower))
    elif variant=="missing_material":
        resolved=SimpleNamespace(parts=(
            SimpleNamespace(part_key=upper.part_key,render_data=None),lower,
        ))
    elif variant=="mismatched_source":
        verified=replace(verified,source_sha256="0"*64)
    elif variant=="stale_handle":
        verified=replace(verified,render_data=SimpleNamespace(metadata={
            "nfb_trial_status":"CONFIGURED_NFB_INNER_DOOR_CUTTING_SOURCE_VERIFIED",
            "nfb_trial_export_approved":True,
            "nfb_source_handle":"wrong:585",
        }))
    elif variant=="false_approval":
        nfb=replace(nfb,manufacturing_ready=True)
    elif variant=="wrong_upper_cell":
        snapshot=dict(snapshot,inner_doors=[{
            "stable_id":"upper","cell_key":"0:1",
            "included_frame_sides":["top","left","right"],
        }])
    with pytest.raises((TypeError,ValueError)):
        resolve_upper_nfb_base_plate_owner(
            snapshot,resolved,verified_inner_door=verified,source_process=nfb,
        )


def replace_part(original,new_key):
    return SimpleNamespace(part_key=new_key,render_data=original.render_data)


def test_reordering_part_inventory_never_changes_owner(tmp_path):
    snapshot,resolved,verified,nfb=_case(tmp_path)
    first=resolve_upper_nfb_base_plate_owner(
        snapshot,resolved,verified_inner_door=verified,source_process=nfb,
    )
    second=resolve_upper_nfb_base_plate_owner(
        snapshot,SimpleNamespace(parts=tuple(reversed(resolved.parts))),
        verified_inner_door=verified,source_process=nfb,
    )
    assert first==second
