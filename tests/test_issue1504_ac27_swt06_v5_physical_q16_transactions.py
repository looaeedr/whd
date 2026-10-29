# -*- coding: utf-8 -*-
"""#1504 NFB-AC-27 / SWT-AC-06: Q16 current CSV V5 physical rollback proof.

Not a legacy source-DXF/SHADOW preflight. The *original operator's* existing
door+base DXF action is exercised on one real W800 Receiving Bay. A rejected
source or collision may not replace, move, or partially publish its earlier
actual CUTTING files. A valid Q16 preserves independently known X locations
and the nominal 360-mm two-switch pitch while re-evaluating *both* physical
sheets. UI-1A retains Undo/Cancel until explicit main confirmation.
"""
from copy import deepcopy
from pathlib import Path

import ezdxf
import pytest

from ae_engine.receiving_nfb_model_identity import numeric_model_ref
from ae_engine.receiving_nfb_ui1a import new_nfb_ui1a_draft, nfb_ui1a_preview
from ae_engine.receiving_nfb_ui1a_edits import (
    NfbUi1aEditSession, UNVERIFIED, editable_nfb_draft,
    replace_nfb_slot_model, set_nfb_manual_x,
)
from tests.test_issue1502_current_csv_original_pair_dxf import _scene, _export
from tests.test_issue1502_csv_v5_part_only_manufacturing import _current

A = numeric_model_ref("士林", "2P400")
B = numeric_model_ref("士林", "3P125SN")
C = numeric_model_ref("士林", "3P400SN")


def _physical(model_second):
    snap = _current(model_second=model_second)
    rows = snap["nfb_config"]["holes"]
    assert len(rows) == 2
    assert snap["w"] == 800
    for row, x in zip(rows, (-180., 180.)):
        row["manual_x_mm"] = x
        row["manual_x_state"] = "CONFIRMED"
    snap["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"] = deepcopy(
        snap["nfb_config"]
    )
    return snap


def _draft():
    draft = editable_nfb_draft(new_nfb_ui1a_draft(
        set_brand="士林", layer_count=1, model_layers=([A, B], []),
    ))
    draft = set_nfb_manual_x(draft, 0, 0, -180., datum={"w": 800, "source": A})
    return set_nfb_manual_x(
        draft, 0, 1, 180., datum={"w": 800, "source": B},
    )


def _files(receipt):
    paths = (Path(receipt.inner_door_path), Path(receipt.base_plate_path))
    assert all(p.is_file() and p.suffix == ".dxf" for p in paths)
    assert all(ezdxf.readfile(p).modelspace() is not None for p in paths)
    return paths



def _save(snapshot, parts, output_dir):
    # The original operator chooses an existing folder. Missing directories
    # are an I/O precondition error, not evidence of geometric rejection.
    output_dir.mkdir(parents=True, exist_ok=True)
    return _export(snapshot, parts, output_dir)


def _shapes(path):
    msp = ezdxf.readfile(path).modelspace()
    circles = tuple(sorted(
        (round(float(item.dxf.center.x), 5),
         round(float(item.dxf.center.y), 5),
         round(float(item.dxf.radius), 5))
        for item in msp
        if item.dxftype() == "CIRCLE" and item.dxf.layer == "CUTTING"
    ))
    closed = tuple(sorted(
        tuple(sorted((round(float(x), 5), round(float(y), 5))
                     for x, y in item.get_points("xy")))
        for item in msp
        if item.dxftype() == "LWPOLYLINE"
        and item.closed and item.dxf.layer == "CUTTING"
    ))
    return circles, closed


def test_ac27_swt06_valid_q16_preserves_two_unit_identity_pitch_and_revalidates_real_v5_dxfs(
    tmp_path,
):
    original = _draft()
    session = NfbUi1aEditSession(original)
    before = deepcopy(session.current)
    nominal_before = nfb_ui1a_preview(
        before, bay_width_mm=800, upper_cell_height_mm=1100,
    )
    assert nominal_before["layers"][0]["adjacent_x_mm"] == (360.0,)
    old = _physical("3P125SN")
    saved_before = _save(old, _scene(old), tmp_path / "before")
    original_paths = _files(saved_before)
    original_geometries = tuple(_shapes(path) for path in original_paths)
    # Before Q16, shallow 3P125SN is raised: its four screws are on PAD.
    assert len(original_geometries[1][0]) == 4
    assert saved_before.source_hole_ids == ("nfb:0", "nfb:1")

    receipt = session.apply("Q16_MODEL_CHANGE", replace_nfb_slot_model,
                            0, 1, C, catalog={"士林": (A, B, C)})
    assert receipt is not None
    changed = session.current["layers"][0]["slots"][1]
    assert changed["filename"] == C
    assert changed["unit_id"] == before["layers"][0]["slots"][1]["unit_id"]
    assert changed["manual_x_mm"] == 180.
    assert changed["manual_x_state"] == UNVERIFIED
    assert changed["datum_snapshot"] is None
    assert session.current["layers"][0]["slots"][0] == before["layers"][0]["slots"][0]
    nominal_after = nfb_ui1a_preview(
        session.current, bay_width_mm=800, upper_cell_height_mm=1100,
    )
    assert nominal_after["layers"][0]["adjacent_x_mm"] == (360.0,)
    assert nominal_after["can_manufacture"] is False

    # After CURRENT source/world-X verification, the real physical path
    # must re-evaluate both sheets, not blindly re-use old FinalScene/DXF.
    new = _physical("3P400SN")
    assert tuple(p["manual_x_mm"] for p in new["nfb_config"]["holes"]) == (-180., 180.)
    original_new_snapshot = deepcopy(new)
    new_scene = _scene(new)
    saved_after = _save(new, new_scene, tmp_path / "after")
    paths_after = _files(saved_after)
    geometry_after = tuple(_shapes(path) for path in paths_after)
    assert saved_after.source_hole_ids == ("nfb:0", "nfb:1")
    assert len(geometry_after[1][0]) == 8
    assert geometry_after != original_geometries
    assert new == original_new_snapshot
    assert tuple(_shapes(path) for path in original_paths) == original_geometries
    assert session.current != before
    assert old["nfb_config"]["holes"][1]["model_filename"] == B


def test_ac27_swt06_invalid_q16_actual_v5_cutting_collision_rolls_back_all_existing_dxfs(
    tmp_path,
):
    before = _physical("3P125SN")
    frozen = deepcopy(before)
    real_scene = _scene(before)
    saved = _save(before, real_scene, tmp_path / "baseline")
    paths = _files(saved)
    old_bytes = tuple(p.read_bytes() for p in paths)
    old_shapes = tuple(_shapes(p) for p in paths)

    # Keep the same physical source owners but intentionally create
    # overlapping main CUTTING holes: no partial scene or hidden DXF write.
    candidate = _physical("3P400SN")
    candidate["nfb_config"]["holes"][1]["manual_x_mm"] = -180.
    candidate["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"] = deepcopy(
        candidate["nfb_config"]
    )
    with pytest.raises(ValueError, match="碰撞|相交|overlap|NFB|FINALSCENE"):
        _scene(candidate)
    rejected_dir = tmp_path / "rejected"
    rejected_dir.mkdir()
    with pytest.raises(ValueError, match="FINALSCENE|DIFFERS|CSV|NFB"):
        _export(candidate, real_scene, rejected_dir)
    assert not list((tmp_path / "rejected").glob("*.dxf"))
    assert not list((tmp_path / "rejected").glob("*.tmp"))
    assert tuple(p.read_bytes() for p in paths) == old_bytes
    assert tuple(_shapes(p) for p in paths) == old_shapes
    assert before == frozen

    # An unresolved replacement model is likewise fail-closed; it cannot
    # inherit the prior model's authority just because X stayed unchanged.
    invalid_source = deepcopy(before)
    invalid_source["nfb_config"]["holes"][1]["model_filename"] = (
        "nfbv5:士林:UNLISTED_PHYSICAL_MODEL"
    )
    invalid_source["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"] = deepcopy(
        invalid_source["nfb_config"]
    )
    with pytest.raises(ValueError):
        _scene(invalid_source)
    assert tuple(p.read_bytes() for p in paths) == old_bytes


def test_ac27_swt06_failed_q16_session_undo_and_cancel_keep_existing_v5_manufacturing(
    tmp_path,
):
    baseline = _physical("3P125SN")
    receipt = _save(baseline, _scene(baseline), tmp_path / "existing")
    paths = _files(receipt)
    before_bytes = tuple(p.read_bytes() for p in paths)
    session = NfbUi1aEditSession(_draft())
    original = deepcopy(session.current)
    session.apply("Q16", replace_nfb_slot_model,
                  0, 1, C, catalog={"士林": (A, B, C)})
    valid_edit = deepcopy(session.current)
    with pytest.raises(ValueError):
        session.apply("INVALID_Q16", replace_nfb_slot_model,
                      0, 1, numeric_model_ref("東元", "2P400"),
                      catalog={"士林": (A, B, C)})
    assert session.current == valid_edit
    assert session.undo().action == "Q16"
    assert session.current == original
    assert not session.dirty
    session.apply("Q16", replace_nfb_slot_model,
                  0, 1, C, catalog={"士林": (A, B, C)})
    assert session.cancel() == original
    assert not session.dirty
    with pytest.raises(ValueError, match="no undo"):
        session.undo()
    assert tuple(p.read_bytes() for p in paths) == before_bytes
    assert baseline["nfb_config"]["holes"][1]["model_filename"] == B
