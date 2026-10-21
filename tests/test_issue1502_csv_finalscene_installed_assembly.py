# -*- coding: utf-8 -*-
"""#1502: CSV V5 screws must reach the SAME installed FinalScene used by 2D/3D."""
from dataclasses import replace
from types import SimpleNamespace

import pytest

from ae_engine.manufacturing_api import build_part_render_data, save_part_render_data_dxf
from ae_engine.receiving_nfb_v5_configured_inner_door import (
    NfbV5ConfiguredInnerDoorHole, trial_configured_nfb_v5_inner_door_render_data,
)
from ae_engine.receiving_nfb_v5_live_base_preview import (
    project_csv_v5_onto_existing_assembly_parts,
)
from ae_engine.receiving_nfb_y_projection import project_nfb_inner_door_nominal_y
from ae_engine.sheetmetal_drawing import CirclePrimitive, PolylinePrimitive
from phase6_final_scene_contracts import AssemblyScenePart
from tests.test_issue1502_existing_base_nfb_assembly import _snapshot, _upper_base
from tests.test_issue1502_v5_csv_tier_bases import _setup


def _installed(snap, spec, tier, count):
    y = project_nfb_inner_door_nominal_y(
        snap, "upper", layer_count=count, slot_index=tier,
    ).box_world_y_mm
    return AssemblyScenePart(
        part_key=spec.physical_id,
        render_data=build_part_render_data(spec),
        x_profile=(), y_profile=(), placement="offset",
        offset=(0., float(y), -115.),
    )


def _screw_ids(part):
    return tuple(sorted(
        p.source_id for p in part.render_data.scene.primitives
        if isinstance(p, CirclePrimitive)
        and p.source_type == "NFB_V5_NUMERIC_BASE_TRIAL"
    ))


def _structure(part):
    return tuple(p for p in part.render_data.scene.primitives
                 if isinstance(p, PolylinePrimitive)
                 and p.layer == "CUTTING" and p.closed)


def test_two_real_installed_assembly_parts_receive_own_csv_screws_only(tmp_path):
    snap, door, holes, specs = _setup()
    a, b = (_installed(snap, specs[i], i, 2) for i in (0, 1))
    untouched = SimpleNamespace(part_key="box_body", render_data=object())
    results = project_csv_v5_onto_existing_assembly_parts(
        snap, "upper", door=door, configured_holes=holes,
        base_specs=specs, assembly_parts=(a, b, untouched),
    )
    assert len(results) == 3
    assert results[2] is untouched
    for index, (before, after) in enumerate(((a, results[0]), (b, results[1]))):
        assert after.part_key == before.part_key
        assert after.offset == before.offset
        assert after.x_profile == before.x_profile
        assert after.y_profile == before.y_profile
        assert after.render_data.unfolded_topology == before.render_data.unfolded_topology
        assert after.render_data.fold_guides == before.render_data.fold_guides
        assert _structure(after) == _structure(before)
        assert len(_structure(after)) == 5  # actual source outer + 4 EAR mounts
        assert len(_screw_ids(after)) == 4
        assert after.render_data.material.area < before.render_data.material.area
        assert after.render_data.metadata["nfb_v5_hole_ids"] == (holes[index].physical_hole_id,)
        assert after.render_data.metadata["nfb_trial_export_approved"] is False
        with pytest.raises(ValueError, match="未驗證試作"):
            save_part_render_data_dxf(after.render_data, tmp_path / f"{index}.dxf")
    assert set(_screw_ids(results[0])).isdisjoint(_screw_ids(results[1]))
    assert not list(tmp_path.iterdir())


def test_single_layer_root_plate_uses_existing_part_not_a_fabricated_tier():
    snap = _snapshot()
    holes = (NfbV5ConfiguredInnerDoorHole(
        "nfb:csv:single", "士林", "nfbv5:士林:2P400",
        35., layer_count=1, slot_index=0,
    ),)
    door = trial_configured_nfb_v5_inner_door_render_data(snap, "upper", holes=holes)
    root = _upper_base("LEFT_FLAT_SIDE")
    existing = _installed(snap, root, 0, 1)
    (result,) = project_csv_v5_onto_existing_assembly_parts(
        snap, "upper", door=door, configured_holes=holes,
        base_specs={0: root}, assembly_parts=(existing,),
    )
    assert result.part_key == "base_plate"
    assert len(_screw_ids(result)) == 4
    assert _structure(result) == _structure(existing)
    assert result.offset == existing.offset
    assert result.render_data.metadata["nfb_v5_tier_slot_index"] is None


def test_wrong_assembly_source_or_install_y_does_not_receive_a_fake_overlay():
    snap, door, holes, specs = _setup()
    a, b = (_installed(snap, specs[i], i, 2) for i in (0, 1))
    with pytest.raises(ValueError, match="安裝位置"):
        project_csv_v5_onto_existing_assembly_parts(
            snap, "upper", door=door, configured_holes=holes,
            base_specs=specs, assembly_parts=(a, replace(b, offset=(0., b.offset[1] + 2., -115.))),
        )
    with pytest.raises(ValueError, match="來源 PartSpec|source CUTTING slots do not mate"):
        project_csv_v5_onto_existing_assembly_parts(
            snap, "upper", door=door, configured_holes=holes,
            base_specs={0: replace(specs[0], receiving_bend_pattern="CENTER_DOUBLE_SIDE_FOLD"),
                        1: specs[1]},
            assembly_parts=(a, b),
        )
    with pytest.raises(ValueError, match="不存在本層"):
        project_csv_v5_onto_existing_assembly_parts(
            snap, "upper", door=door, configured_holes=holes,
            base_specs=specs, assembly_parts=(a,),
        )
    with pytest.raises(ValueError, match="重複"):
        project_csv_v5_onto_existing_assembly_parts(
            snap, "upper", door=door, configured_holes=holes,
            base_specs=specs, assembly_parts=(a, b, a),
        )


def test_mismatched_full_door_proof_rejected_before_replacing_existing_parts():
    snap, door, holes, specs = _setup()
    a, b = (_installed(snap, specs[i], i, 2) for i in (0, 1))
    altered = (holes[0], replace(holes[1], world_x_mm=holes[1].world_x_mm + 10.))
    with pytest.raises(ValueError, match="已驗證孔位"):
        project_csv_v5_onto_existing_assembly_parts(
            snap, "upper", door=door, configured_holes=altered,
            base_specs=specs, assembly_parts=(a, b),
        )
    assert not _screw_ids(a) and not _screw_ids(b)
