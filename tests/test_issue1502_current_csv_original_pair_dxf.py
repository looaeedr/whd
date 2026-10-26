# -*- coding: utf-8 -*-
"""#1502 original Receiving DXF control consumes one canonical NFB CSV source."""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import ezdxf
import pytest

from ae_engine.cabinet_types.policy import derive_inner_door_panels
from ae_engine.manufacturing_api import build_inner_door_panel_render_data
from ae_engine.receiving_nfb_committed_final_scene import (
    apply_committed_csv_v5_to_canonical_parts,
)
from phase6_final_scene_contracts import AssemblyScenePart
from gui_modules.application.receiving_nfb_pair_partial_export_action import (
    export_current_csv_nfb_door_base_pair,
)
from tests.test_issue1502_csv_is_only_normal_finalscene_source import _make
from tests.test_issue1502_csv_v5_part_only_manufacturing import _current
from tests.test_issue1502_source_derived_center_base import _spec


def _scene(snapshot):
    panel = next(p for p in derive_inner_door_panels(snapshot)
                 if str(p.cell_key).split(":")[-1] == "0")
    actual = AssemblyScenePart(
        part_key=panel.stable_id,
        render_data=build_inner_door_panel_render_data(panel),
        x_profile=(), y_profile=(), placement="offset",
        offset=(0., 0., 0.),
    )
    return apply_committed_csv_v5_to_canonical_parts(
        snapshot, (actual, _make(snapshot)),
    )


def _export(snap, parts, root):
    return export_current_csv_nfb_door_base_pair(
        snap, assembly_parts=parts, base_spec=(
            _spec(snap) if snap.get("nfb_config_submitted") is True else None
        ),
        output_directory=root,
    )


def test_normal_existing_pair_export_writes_two_verified_actual_csv_dxfs(tmp_path):
    snapshot = _current()
    assert "receiving_base_plate" not in snapshot
    parts = _scene(snapshot)
    actual = _export(snapshot, parts, tmp_path)
    assert actual.source_hole_ids == ("nfb:0", "nfb:1")
    assert len(actual.check_q_key) == 64
    door = Path(actual.inner_door_path)
    base = Path(actual.base_plate_path)
    assert door.is_file() and base.is_file() and door != base
    assert len(list(tmp_path.glob("*.dxf"))) == 2
    a = ezdxf.readfile(door).modelspace()
    b = ezdxf.readfile(base).modelspace()
    assert len([p for p in a if p.dxftype()=="LWPOLYLINE"
                and p.closed and p.dxf.layer=="CUTTING"]) >= 2
    assert len([p for p in b if p.dxftype()=="CIRCLE"
                and p.dxf.layer=="CUTTING"]) == 8
    # Today's committed Flat source has its original one perimeter +
    # four EAR slots, plus source-verified PAD square locator CUTTING.
    # Compare every saved polygon to the ACTUAL resolved FinalScene, rather
    # than hardcoding the pre-PAD count of five or trusting metadata alone.
    from ae_engine.sheetmetal_drawing import PolylinePrimitive
    physical_base = next(p.render_data for p in parts if p.part_key == "base_plate")
    source_cutting = [
        p for p in physical_base.scene.primitives
        if isinstance(p, PolylinePrimitive) and p.closed and p.layer == "CUTTING"
    ]
    saved_cutting = [
        p for p in b if p.dxftype() == "LWPOLYLINE"
        and p.closed and p.dxf.layer == "CUTTING"
    ]
    pad_owners = tuple(physical_base.metadata["nfb_v5_pad_square_owners"])
    assert pad_owners and sum(count for _, count in pad_owners) == 4
    assert len(source_cutting) == len(saved_cutting) == 5 + sum(
        count for _, count in pad_owners
    )
    def source_vertices(poly):
        return tuple((round(float(p.x), 5), round(float(p.y), 5)) for p in poly.points)
    def saved_vertices(poly):
        return tuple((round(float(x), 5), round(float(y), 5))
                     for x, y in poly.get_points("xy"))
    assert sorted(map(source_vertices, source_cutting)) == sorted(
        map(saved_vertices, saved_cutting)
    )
    assert any(p.dxf.layer=="BEND" for p in b)


def test_stale_scene_or_wrong_bay_cannot_export_to_existing_operator_action(tmp_path):
    snapshot = _current()
    parts = _scene(snapshot)
    wrong = replace(parts[1], render_data=replace(parts[1].render_data,
        metadata={**parts[1].render_data.metadata, "stable_id": "wrong"}))
    with pytest.raises(ValueError, match="CURRENT_FINALSCENE"):
        _export(snapshot, (parts[0], wrong), tmp_path)
    stale = deepcopy(snapshot)
    stale["nfb_config"]["holes"][1]["manual_x_mm"] += 20.
    stale["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"] = deepcopy(
        stale["nfb_config"]
    )
    with pytest.raises(ValueError, match="CURRENT_FINALSCENE"):
        _export(stale, parts, tmp_path)
    wrong_bay = deepcopy(snapshot)
    wrong_bay["_receiving_runtime_selection"]["bay_id"] = "different"
    with pytest.raises(ValueError, match="identity drift|IDENTITY_DRIFT|RECEIVING_FLAT_NFB_BAY_SCOPE_DRIFT"):
        _export(wrong_bay, parts, tmp_path)
    assert not list(tmp_path.glob("*.dxf"))


def test_pair_export_rejects_unsubmitted_and_refuses_silent_overwrite(tmp_path):
    snapshot = _current()
    parts = _scene(snapshot)
    first = _export(snapshot, parts, tmp_path)
    first_bytes = Path(first.inner_door_path).read_bytes()
    with pytest.raises(FileExistsError, match="EXISTING_DXF"):
        _export(snapshot, parts, tmp_path)
    assert Path(first.inner_door_path).read_bytes() == first_bytes
    cleared = deepcopy(snapshot)
    cleared["nfb_config_submitted"] = False
    cleared.pop("nfb_config", None)
    # The original #1502 test uses a minimal Set/Bay manufacturing fixture
    # (no ReceivingLayout schema), not a persisted normalized layout. Restore
    # its selected Bay authority directly; only a genuinely unconfigured Bay
    # may use the original legacy no-NFB path.
    bay = cleared["receiving_layout"]["sets"][0]["bays"][0]
    assert bay["nfb_config_submitted"] is True
    bay["nfb_config_submitted"] = False
    bay.pop("nfb_config", None)
    assert "nfb_config" not in bay
    with pytest.raises(ValueError, match="SOURCE_UNAVAILABLE"):
        _export(cleared, parts, tmp_path)


def test_dxf_roundtrip_failure_never_partially_publishes(monkeypatch,tmp_path):
    import gui_modules.application.receiving_nfb_pair_partial_export_action as action
    import ae_engine.manufacturing_verification as verification

    snap = _current()
    parts = _scene(snap)
    call_count = {"n": 0}
    real = verification.verify_saved_part_render_data_dxf
    def fail_second(render, path):
        call_count["n"] += 1
        if call_count["n"] == 2:
            return SimpleNamespace(ok=False)
        return real(render,path)
    monkeypatch.setattr(verification,"verify_saved_part_render_data_dxf",fail_second)
    with pytest.raises(ValueError,match="ROUNDTRIP_FAILED"):
        _export(snap, parts, tmp_path)
    assert not list(tmp_path.glob("*.dxf"))


def test_original_gui_pair_port_auto_consumes_csv_without_extra_button():
    import inspect
    from gui_modules.application import (
        fold_designer_composition_receiving, receiving_multi_settings_window,
    )
    gui=inspect.getsource(fold_designer_composition_receiving)
    modal=inspect.getsource(receiving_multi_settings_window)
    assert "current_csv_pair_source(set_index, bay_index)" in gui
    assert "export_current_csv_nfb_door_base_pair(" in gui
    assert '"pair_partial_export": export_partial_nfb_door_base_pair' in gui
    assert 'text="輸出內門＋底板 DXF（成對部分）"' in modal
    assert "輸出 CSV 底板 DXF（單片）" not in modal


def test_original_operator_left_two_source_equivalent_models_roundtrip(tmp_path):
    # The user's LEFT original has TWO 44x194 / Ø5.1 quartets on ONE
    # physical base. Different numeric catalog names with exactly the
    # same source geometry must traverse the ordinary two-sheet operator
    # export, not just the physical configuration resolver.
    snap = _current(model_second="3P400SN")
    from ae_engine.receiving_base_plate_config import (
        receiving_base_plate_values, receiving_base_plate_blank_dimensions,
    )
    assert receiving_base_plate_values(snap)["receiving_bend_pattern"] == "LEFT_FLAT_SIDE"
    assert receiving_base_plate_blank_dimensions(snap) == (710., 300.)
    parts = _scene(snap)
    receipt = _export(snap, parts, tmp_path)
    assert receipt.source_hole_ids == ("nfb:0", "nfb:1")
    assert len(receipt.check_q_key) == 64
    paths = (Path(receipt.inner_door_path), Path(receipt.base_plate_path))
    assert all(path.is_file() for path in paths)
    assert len(list(tmp_path.glob("*.dxf"))) == 2
    base = ezdxf.readfile(paths[1]).modelspace()
    screws = [item for item in base
              if item.dxftype() == "CIRCLE" and item.dxf.layer == "CUTTING"]
    slots = [item for item in base
             if item.dxftype() == "LWPOLYLINE" and item.closed
             and item.dxf.layer == "CUTTING"]
    assert len(screws) == 8
    assert all(abs(float(h.dxf.radius) - 2.55) < 1e-6 for h in screws)
    assert len(slots) == 5  # one blank + four original EAR fixing slots
    assert sum(1 for h in base if h.dxf.layer == "BEND") == 2
    door = ezdxf.readfile(paths[0]).modelspace()
    openings = [item for item in door
                if item.dxftype() == "LWPOLYLINE" and item.closed
                and item.dxf.layer == "CUTTING"]
    assert len(openings) >= 3  # actual inner-door perimeter + both NFB openings


def test_three_same_tier_400_switches_share_one_source_base_and_reopen_dxf(tmp_path):
    # One submitted vertical tier can have 3 horizontally arranged NFBs.
    # The NFBConfig owns all 3 X locations; source LEFT still owns one
    # cabinet-centred base and its original four ear-mount slots.
    snap = _current(model_second="3P400SN")
    holes = snap["nfb_config"]["holes"]
    holes[0]["manual_x_mm"] = -180.
    holes[1]["manual_x_mm"] = 0.
    third = deepcopy(holes[0])
    third.update(physical_hole_id="nfb:third", slot_index=2,
                 manual_x_mm=180., model_filename="nfbv5:士林:2P400")
    holes.append(third)
    snap["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"] = deepcopy(
        snap["nfb_config"]
    )
    parts = _scene(snap)
    receipt = _export(snap, parts, tmp_path)
    assert receipt.source_hole_ids == ("nfb:0", "nfb:1", "nfb:third")
    assert len(list(tmp_path.glob("*.dxf"))) == 2
    base = ezdxf.readfile(receipt.base_plate_path).modelspace()
    circles = [p for p in base if p.dxftype() == "CIRCLE"
               and p.dxf.layer == "CUTTING"]
    assert len(circles) == 12
    assert all(abs(float(p.dxf.radius) - 2.55) < 1e-6 for p in circles)
    assert len([p for p in base if p.dxftype() == "LWPOLYLINE"
                and p.closed and p.dxf.layer == "CUTTING"]) == 5
    assert sum(1 for p in base if p.dxf.layer == "BEND") == 2
    door = ezdxf.readfile(receipt.inner_door_path).modelspace()
    assert len([p for p in door if p.dxftype() == "LWPOLYLINE"
                and p.closed and p.dxf.layer == "CUTTING"]) >= 4


def test_normal_operator_export_single_125_current_csv_uses_real_flat_source(tmp_path):
    snap = _current()
    only = deepcopy(snap["nfb_config"]["holes"][1])
    only.update(slot_index=0, layer_index=0, manual_x_mm=0.)
    snap["nfb_config"]["holes"] = [only]
    snap["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"] = deepcopy(
        snap["nfb_config"]
    )
    parts = _scene(snap)
    receipt = _export(snap, parts, tmp_path)
    assert receipt.source_hole_ids == ("nfb:1",)
    assert len(list(tmp_path.glob("*.dxf"))) == 2
    plate = ezdxf.readfile(receipt.base_plate_path).modelspace()
    holes = [x for x in plate if x.dxftype() == "CIRCLE"
             and x.dxf.layer == "CUTTING"]
    assert len(holes) == 4
    assert all(abs(float(x.dxf.radius) - 1.6) < 1e-6 for x in holes)
    assert len([x for x in plate if x.dxftype() == "LWPOLYLINE"
                and x.closed and x.dxf.layer == "CUTTING"]) == 5
    assert sum(1 for x in plate if x.dxf.layer == "BEND") == 2


def test_original_operator_does_not_equate_two_brands_on_one_flat_base(tmp_path):
    snap = _current(model_second="3P400SN")
    row = snap["nfb_config"]["holes"][1]
    row.update(model_filename="nfbv5:伍菱:3P400SN", source_brand="伍菱")
    snap["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"] = deepcopy(
        snap["nfb_config"]
    )
    from ae_engine.receiving_base_plate_config import receiving_base_plate_values
    assert receiving_base_plate_values(snap)["receiving_bend_pattern"] == "LEFT_FLAT_SIDE"
    receipt = _export(snap, _scene(snap), tmp_path)
    assert receipt.source_hole_ids == ("nfb:0", "nfb:1")
    plate = ezdxf.readfile(receipt.base_plate_path).modelspace()
    assert sum(1 for x in plate if x.dxftype() == "CIRCLE"
               and x.dxf.layer == "CUTTING") == 8
    door = ezdxf.readfile(receipt.inner_door_path).modelspace()
    assert sum(1 for x in door if x.dxftype() == "LWPOLYLINE"
               and x.closed and x.dxf.layer == "CUTTING") >= 3


@pytest.mark.parametrize("rotation", (0, 90, 180, 270))
def test_swt29_current_csv_four_rotations_keep_one_main_cut_and_original_pair(
    rotation, tmp_path,
):
    """Current numeric V5 -> real inner-door FinalScene -> original paired DXFs.

    Reopened DXF must retain one, and only one, source-sized NFB main opening;
    a legacy Hole Editor alias must not make a second identical CUTTING loop.
    The four base screw holes belong to the same physical owner but a
    different original physical plate; this is NOT whole-cabinet approval.
    """
    from ae_engine.receiving_nfb_numeric_catalog import model_spec
    from ae_engine.receiving_nfb_committed_final_scene import _submitted_csv_holes
    from ae_engine.receiving_nfb_v5_configured_inner_door import (
        trial_configured_nfb_v5_inner_door_render_data,
    )
    from ae_engine.sheetmetal_drawing import CirclePrimitive, PolylinePrimitive

    snap = _current()
    only = deepcopy(snap["nfb_config"]["holes"][0])
    only.update(slot_index=0, layer_index=0, manual_x_mm=0.,
                rotation_deg=rotation)
    snap["nfb_config"]["holes"] = [only]
    snap["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"] = deepcopy(
        snap["nfb_config"]
    )
    source = deepcopy(snap)
    inner_door_id, holes = _submitted_csv_holes(snap)
    assert len(holes) == 1 and holes[0].physical_hole_id == only["physical_hole_id"]
    trial = trial_configured_nfb_v5_inner_door_render_data(
        snap, inner_door_id, holes=holes,
    )
    expected_opening = model_spec("士林", "2P400").opening_mm
    assert expected_opening is not None
    expected_dims = expected_opening[::-1] if rotation in (90, 270) else expected_opening
    centre = trial.patterns[0].datum.uv_centre_mm

    real_parts = _scene(snap)
    receipt = _export(snap, real_parts, tmp_path)
    assert receipt.source_hole_ids == (only["physical_hole_id"],)
    paths = (Path(receipt.inner_door_path), Path(receipt.base_plate_path))
    assert len(list(tmp_path.glob("*.dxf"))) == 2
    door = ezdxf.readfile(paths[0]).modelspace()
    contours = [p for p in door if p.dxftype() == "LWPOLYLINE"
                and p.closed and p.dxf.layer == "CUTTING"]
    def bounds(poly):
        points = tuple((float(x), float(y)) for x, y in poly.get_points("xy"))
        xs, ys = zip(*points)
        return (max(xs)-min(xs), max(ys)-min(ys),
                (max(xs)+min(xs))/2., (max(ys)+min(ys))/2.)
    openings = [p for p in contours
                if tuple(round(x, 5) for x in bounds(p)[:2]) ==
                tuple(round(x, 5) for x in expected_dims)]
    assert len(openings) == 1
    assert bounds(openings[0])[2:] == pytest.approx(centre, abs=1e-5)
    native_door = next(p.render_data for p in real_parts if p.part_key == trial.part_id)
    assert sum(isinstance(p, PolylinePrimitive) and p.closed
               and p.layer == "CUTTING"
               for p in native_door.scene.primitives) == len(contours)

    base = ezdxf.readfile(paths[1]).modelspace()
    saved_screws = sorted(
        (round(float(e.dxf.center.x), 5), round(float(e.dxf.center.y), 5),
         round(float(e.dxf.radius), 5))
        for e in base if e.dxftype() == "CIRCLE" and e.dxf.layer == "CUTTING"
    )
    native_base = next(p.render_data for p in real_parts if p.part_key == "base_plate")
    actual_screws = sorted(
        (round(float(p.center.x), 5), round(float(p.center.y), 5),
         round(float(p.radius), 5))
        for p in native_base.scene.primitives
        if isinstance(p, CirclePrimitive)
        and p.source_type == "NFB_V5_NUMERIC_BASE_TRIAL"
    )
    assert len(saved_screws) == len(actual_screws) == 4
    assert saved_screws == actual_screws
    assert snap == source


def test_ac11_ac51_swt27_swt30_current_v5_never_needs_legacy_model_dxf_input(
    tmp_path, monkeypatch,
):
    """Current brand-numeric CSV model -> submitted FinalScene -> 2 DXF reopen.

    Neither legacy color/pivot parsing nor an original NFB manufacturer model
    .dxf is a prerequisite for current V5. The *generated* manufacturing
    DXFs still require real CUTTING geometry, a verified pair and reopening.
    This is not authorization for unverified W/N/X or whole-cabinet output.
    """
    from ae_engine.receiving_nfb_model_identity import (
        parse_numeric_model_ref, selected_numeric_spec,
    )
    from ae_engine import receiving_nfb_dxf_source as legacy_dxf
    from ae_engine import receiving_nfb_manufacturing_release as legacy_release

    def forbidden_legacy(*_args, **_kwargs):
        pytest.fail("CURRENT numeric V5 illegally requires original model DXF")

    monkeypatch.setattr(
        legacy_dxf, "inspect_nfb_dxf_source", forbidden_legacy,
    )
    monkeypatch.setattr(
        legacy_release, "inspect_nfb_dxf_source", forbidden_legacy,
    )

    saved = _current()
    assert saved["nfb_config_submitted"] is True
    originals = saved["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"]
    refs = tuple(x["model_filename"] for x in saved["nfb_config"]["holes"])
    assert refs == ("nfbv5:士林:2P400", "nfbv5:士林:3P125SN")
    assert tuple(x["model_filename"] for x in originals["holes"]) == refs
    for ref in refs:
        assert parse_numeric_model_ref(ref) is not None
        spec = selected_numeric_spec("士林", ref)
        assert spec is not None and spec.dimensionally_complete
        assert spec.opening_mm is not None and spec.screw_pitch_mm is not None

    destination = tmp_path / "current_v5"
    destination.mkdir()
    actual = _export(saved, _scene(saved), destination)
    paths = (Path(actual.inner_door_path), Path(actual.base_plate_path))
    assert all(path.is_file() for path in paths)
    assert len(list((tmp_path / "current_v5").glob("*.dxf"))) == 2
    door = ezdxf.readfile(paths[0]).modelspace()
    base = ezdxf.readfile(paths[1]).modelspace()
    assert sum(
        entity.dxftype() == "LWPOLYLINE"
        and entity.closed and entity.dxf.layer == "CUTTING"
        for entity in door
    ) >= len(refs)
    assert sum(
        entity.dxftype() == "CIRCLE" and entity.dxf.layer == "CUTTING"
        for entity in base
    ) == 4 * len(refs)
    assert actual.source_hole_ids == ("nfb:0", "nfb:1")
    assert len(actual.check_q_key) == 64


def test_ac11_ac51_current_v5_missing_numeric_model_fails_without_legacy_fallback(
    tmp_path, monkeypatch,
):
    """Unknown V5 source cannot be rescued by same-named historic model DXF."""
    from ae_engine import receiving_nfb_dxf_source as legacy_dxf
    monkeypatch.setattr(
        legacy_dxf, "inspect_nfb_dxf_source",
        lambda *_a, **_kw: pytest.fail("legacy fallback is forbidden for V5"),
    )
    saved = _current()
    missing = "nfbv5:士林:THIS_MODEL_IS_NOT_IN_CURRENT_CSV"
    saved["nfb_config"]["holes"][1]["model_filename"] = missing
    bay = saved["receiving_layout"]["sets"][0]["bays"][0]
    bay["nfb_config"] = deepcopy(saved["nfb_config"])
    with pytest.raises((ValueError, KeyError)):
        _scene(saved)
    assert not list(tmp_path.rglob("*.dxf"))


@pytest.mark.parametrize("rotation", (0, 90, 180, 270))
def test_ac11_current_numeric_v5_two_models_real_pivot_and_upper_door_lower_base_dxf(
    rotation, tmp_path, monkeypatch,
):
    """Current V5 main-hole pivot is per model's CSV opening centre at actual UV.

    No original per-model DXF ARC/CIRCLE/color/handle is mandatory. Confirm
    two independently selected CSV models + live world X, four rotations,
    one main CUTTING per model in true INNER-DOOR DXF, 8 screw CUTTING
    circles on real BASE DXF, native FinalScene equality and no double cut.
    Historic model-DXF parser is forbidden for this CURRENT route.
    """
    from ae_engine import receiving_nfb_dxf_source as legacy
    from ae_engine import receiving_nfb_manufacturing_release as legacy_release
    from ae_engine.receiving_nfb_committed_final_scene import _submitted_csv_holes
    from ae_engine.receiving_nfb_model_identity import (
        parse_numeric_model_ref, selected_numeric_spec,
    )
    from ae_engine.receiving_nfb_v5_configured_inner_door import (
        trial_configured_nfb_v5_inner_door_render_data,
    )
    from ae_engine.sheetmetal_drawing import PolylinePrimitive, CirclePrimitive

    def unexpected_legacy(*args, **kwargs):
        pytest.fail("V5 main-pivot/physical export called old NFB model DXF")

    monkeypatch.setattr(legacy, "inspect_nfb_dxf_source", unexpected_legacy)
    monkeypatch.setattr(legacy_release, "inspect_nfb_dxf_source", unexpected_legacy)

    snap = _current()
    selected = snap["nfb_config"]["holes"]
    assert len(selected) == 2
    # Distinct declared world X; if the old source drawing/global origin
    # were used as a pivot, these saved positions could not match output.
    assert [h["manual_x_mm"] for h in selected] == [-150.0, 150.0]
    selected[1]["rotation_deg"] = rotation
    snap["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"] = deepcopy(
        snap["nfb_config"]
    )
    inner_id, holes = _submitted_csv_holes(snap)
    assert len(holes) == 2
    trial = trial_configured_nfb_v5_inner_door_render_data(
        snap, inner_id, holes=holes,
    )
    assert trial.hole_ids == tuple(h.physical_hole_id for h in holes)
    assert len(trial.patterns) == 2
    for pattern, hole in zip(trial.patterns, holes):
        ref = parse_numeric_model_ref(hole.model_ref)
        assert ref is not None and ref[0] == pattern.brand
        spec = selected_numeric_spec(pattern.brand, hole.model_ref)
        assert spec is not None and spec.dimensionally_complete
        assert pattern.model == ref[1]
        assert pattern.opening_uv_mm is not None
        assert pattern.screw_centres_uv_mm is None
        assert pattern.status != "MANUFACTURING_READY"
        corners = pattern.opening_uv_mm
        cx = (min(p[0] for p in corners)+max(p[0] for p in corners))/2
        cy = (min(p[1] for p in corners)+max(p[1] for p in corners))/2
        assert (cx, cy) == pytest.approx(pattern.datum.uv_centre_mm)
        assert pattern.datum.uv_axis_x in ((1,0), (0,1), (-1,0), (0,-1))
        assert pattern.datum.uv_axis_y in ((0,1), (-1,0), (0,-1), (1,0))

    actual_scene = _scene(snap)
    receipt = _export(snap, actual_scene, tmp_path)
    assert receipt.source_hole_ids == tuple(h.physical_hole_id for h in holes)
    assert len(list(tmp_path.glob("*.dxf"))) == 2

    def points(poly):
        return tuple((round(float(x), 5), round(float(y), 5))
                     for x,y in poly.get_points("xy"))

    door = ezdxf.readfile(receipt.inner_door_path).modelspace()
    loops = [entity for entity in door
             if entity.dxftype() == "LWPOLYLINE" and entity.closed
             and entity.dxf.layer == "CUTTING"]
    # Use exact rotated vertices, not only bounding-box and nominal pitch.
    expected = [tuple(sorted((round(x, 5), round(y, 5))
                             for x,y in pattern.opening_uv_mm))
                for pattern in trial.patterns]
    matches = [tuple(sorted(points(poly))) for poly in loops]
    for outline in expected:
        assert matches.count(outline) == 1
    assert len(set(expected)) == 2
    native_door = next(p.render_data for p in actual_scene
                       if p.part_key == trial.part_id)
    native_loops = [p for p in native_door.scene.primitives
                    if isinstance(p, PolylinePrimitive)
                    and p.closed and p.layer == "CUTTING"]
    assert len(native_loops) == len(loops)

    base = ezdxf.readfile(receipt.base_plate_path).modelspace()
    saved_screws = sorted(
        (round(float(ent.dxf.center.x), 5),
         round(float(ent.dxf.center.y), 5),
         round(float(ent.dxf.radius), 5))
        for ent in base if ent.dxftype() == "CIRCLE"
        and ent.dxf.layer == "CUTTING"
    )
    native_base = next(p.render_data for p in actual_scene
                       if p.part_key == "base_plate")
    from_scene = sorted(
        (round(float(p.center.x), 5), round(float(p.center.y), 5),
         round(float(p.radius), 5))
        for p in native_base.scene.primitives
        if isinstance(p, CirclePrimitive)
        and p.source_type == "NFB_V5_NUMERIC_BASE_TRIAL"
    )
    assert len(saved_screws) == len(from_scene) == 8
    assert saved_screws == from_scene
    # This is physical source-scoped partial output, NOT automatic MFG2 PAD.
    assert not list(tmp_path.glob("*PAD*.dxf"))


def test_swt27_current_v5_single_x_and_three_row_x_are_true_physical_datums(
    tmp_path, monkeypatch,
):
    """W800/T2 verified example: submitted per-hole X -> exact physical CSV DXFs.

    Two committed three-hole rows differ ONLY at first-hole X (-180 -> -165).
    Check main-opening vertices and the source-verified Base screw circles.
    The other holes, physical plate owner, Set/Bay, and original selected
    model sources remain unchanged. This does not bless other widths/rows.
    """
    from ae_engine import receiving_nfb_dxf_source as legacy
    from ae_engine.receiving_nfb_committed_final_scene import _submitted_csv_holes
    from ae_engine.receiving_nfb_v5_configured_inner_door import (
        trial_configured_nfb_v5_inner_door_render_data,
    )
    from ae_engine.receiving_nfb_model_identity import selected_numeric_spec

    monkeypatch.setattr(
        legacy, "inspect_nfb_dxf_source",
        lambda *_a, **_kw: pytest.fail("Current CSV X must not read old model DXF"),
    )
    before = _current(model_second="3P400SN")
    holes = before["nfb_config"]["holes"]
    holes[0]["manual_x_mm"] = -180.
    holes[1]["manual_x_mm"] = 0.
    third = deepcopy(holes[0])
    third.update(physical_hole_id="nfb:third", slot_index=2,
                 manual_x_mm=180., model_filename="nfbv5:士林:2P400")
    holes.append(third)
    before["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"] = deepcopy(
        before["nfb_config"]
    )
    after = deepcopy(before)
    after["nfb_config"]["holes"][0]["manual_x_mm"] = -165.
    after["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"] = deepcopy(
        after["nfb_config"]
    )

    assert all(row["manual_x_state"] == "CONFIRMED"
               for row in before["nfb_config"]["holes"])
    for snap, x_positions in (
        (before, (-180., 0., 180.)),
        (after, (-165., 0., 180.)),
    ):
        assert snap["w"] == 800.
        assert [row["manual_x_mm"] for row in snap["nfb_config"]["holes"]] == list(x_positions)
        assert [row["slot_index"] for row in snap["nfb_config"]["holes"]] == [0, 1, 2]
        inner_id, resolved = _submitted_csv_holes(snap)
        assert [h.world_x_mm for h in resolved] == list(x_positions)
        assert len({h.physical_hole_id for h in resolved}) == 3
        assert all(selected_numeric_spec("士林", h.model_ref).dimensionally_complete
                   for h in resolved)
        trial = trial_configured_nfb_v5_inner_door_render_data(
            snap, inner_id, holes=resolved,
        )
        assert len(trial.patterns) == 3
        centres = [p.datum.uv_centre_mm for p in trial.patterns]
        assert [xy[0] - centres[1][0] for xy in centres] == pytest.approx(
            [x_positions[0], 0., 180.]
        )
        assert all(xy[1] == pytest.approx(centres[0][1]) for xy in centres)

    # The pre-change physical sheets cannot authorize post-change export.
    first_parts = _scene(before)
    with pytest.raises(ValueError, match="CURRENT_FINALSCENE|SOURCE"):
        _export(after, first_parts, tmp_path / "nonexistent")
    assert not list(tmp_path.rglob("*.dxf"))

    def export_and_points(snap, subdir):
        folder = tmp_path / subdir
        folder.mkdir()
        receipt = _export(snap, _scene(snap), folder)
        assert receipt.source_hole_ids == ("nfb:0", "nfb:1", "nfb:third")
        assert len(list(folder.glob("*.dxf"))) == 2
        door = ezdxf.readfile(receipt.inner_door_path).modelspace()
        base = ezdxf.readfile(receipt.base_plate_path).modelspace()
        loops = [
            tuple(sorted((round(float(x), 5), round(float(y), 5))
                         for x, y in e.get_points("xy")))
            for e in door if e.dxftype() == "LWPOLYLINE"
            and e.closed and e.dxf.layer == "CUTTING"
        ]
        circles = sorted(
            (round(float(e.dxf.center.x), 5),
             round(float(e.dxf.center.y), 5),
             round(float(e.dxf.radius), 5))
            for e in base if e.dxftype() == "CIRCLE" and e.dxf.layer == "CUTTING"
        )
        assert len(circles) == 12
        assert receipt.check_q_key
        return loops, circles

    first_loops, first_screws = export_and_points(before, "before")
    next_loops, next_screws = export_and_points(after, "after")
    def expected_contours(snap):
        inner_id, resolved = _submitted_csv_holes(snap)
        patterns = trial_configured_nfb_v5_inner_door_render_data(
            snap, inner_id, holes=resolved,
        ).patterns
        return [
            tuple(sorted((round(x, 5), round(y, 5))
                         for x, y in pattern.opening_uv_mm))
            for pattern in patterns
        ]
    originals = expected_contours(before)
    changed = expected_contours(after)
    assert originals[0] != changed[0]
    assert originals[1:] == changed[1:]
    for expected in originals:
        assert first_loops.count(expected) == 1
    for expected in changed:
        assert next_loops.count(expected) == 1
    # One NFB moves 15 mm in X, so precisely four of its BASE screw centres
    # move. All other eight physical CUTTING screws must be byte-geometry same.
    from collections import Counter
    old, new = Counter(first_screws), Counter(next_screws)
    removed = list((old - new).elements())
    added = list((new - old).elements())
    assert len(removed) == len(added) == 4
    assert sorted((round(a[0]-b[0], 5), a[1], a[2])
                  for a,b in zip(sorted(added), sorted(removed))) == sorted(
        (15., y, radius) for _, y, radius in removed
    )


def test_swt27_current_v5_unapproved_x_state_never_infers_row_from_nominal(
    tmp_path,
):
    """Nominal W800x3 spacing is NOT confirmation of an absent per-hole X."""
    snap = _current(model_second="3P400SN")
    hole = snap["nfb_config"]["holes"][1]
    hole["manual_x_state"] = "NONE"
    hole["manual_x_mm"] = None
    snap["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"] = deepcopy(
        snap["nfb_config"]
    )
    # A preview may legitimately display the legacy physical sheet, but
    # the submitted NFB manufacturing exporter must NEVER silently publish
    # that sheet with the unresolved main aperture/screws missing.
    folder = tmp_path / "unconfirmed_x"
    folder.mkdir()
    with pytest.raises((ValueError, KeyError)):
        _export(snap, _scene(snap), folder)
    assert not list(tmp_path.rglob("*.dxf"))


def test_swt30_exact_committed_w_n_y_model_datum_has_real_dxf_but_cannot_leak_to_other_scope(
    tmp_path,
):
    """One W800 three-unit current V5 contract, never a nominal-pitch whitelist.

    The actual signed operator pair uses committed per-hole X, physical
    Set/Bay and numeric model. Stale scene cannot be reused after changing
    width, model, operator X, unit count or live Bay. The 'approved' witness
    is the freshly regenerated exact FinalScene and reopened original-port
    output, not a filename, preview flag or a nominal hole pitch.
    """
    from ae_engine.receiving_nfb_committed_final_scene import _submitted_csv_holes
    from ae_engine.receiving_nfb_model_identity import selected_numeric_spec

    approved = _current(model_second="3P400SN")
    holes = approved["nfb_config"]["holes"]
    holes[0]["manual_x_mm"] = -180.
    holes[1]["manual_x_mm"] = 0.
    third = deepcopy(holes[0])
    third.update(
        physical_hole_id="nfb:swt30-third",
        slot_index=2, manual_x_mm=180.,
        model_filename="nfbv5:士林:2P400",
    )
    holes.append(third)
    approved["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"] = deepcopy(
        approved["nfb_config"]
    )
    inner_id, selected = _submitted_csv_holes(approved)
    assert approved["w"] == 800.
    assert len(selected) == 3
    assert tuple(h.world_x_mm for h in selected) == (-180., 0., 180.)
    assert all(
        selected_numeric_spec("士林", h.model_ref).dimensionally_complete
        for h in selected
    )
    parts = _scene(approved)
    dest = tmp_path / "approved"
    dest.mkdir()
    receipt = _export(approved, parts, dest)
    assert receipt.source_hole_ids == (
        "nfb:0", "nfb:1", "nfb:swt30-third",
    )
    assert receipt.scope == "CSV_PAIR_PART_ONLY_NOT_WHOLE_CABINET"
    assert len(receipt.check_q_key) == 64
    assert len(list(dest.glob("*.dxf"))) == 2
    door = ezdxf.readfile(receipt.inner_door_path).modelspace()
    base = ezdxf.readfile(receipt.base_plate_path).modelspace()
    door_contours = [
        e for e in door
        if e.dxftype() == "LWPOLYLINE"
        and e.closed and e.dxf.layer == "CUTTING"
    ]
    screw_circles = [
        e for e in base
        if e.dxftype() == "CIRCLE" and e.dxf.layer == "CUTTING"
    ]
    assert len(door_contours) >= 3
    assert len(screw_circles) == 12
    assert any(p.dxf.layer == "BEND" for p in base)

    mutants = {}
    wrong_width = deepcopy(approved)
    wrong_width["w"] = 750.
    mutants["other_width"] = wrong_width
    changed_model = deepcopy(approved)
    changed_model["nfb_config"]["holes"][1]["model_filename"] = "nfbv5:士林:2P125SN"
    changed_model["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"] = deepcopy(
        changed_model["nfb_config"]
    )
    mutants["other_model"] = changed_model
    changed_x = deepcopy(approved)
    changed_x["nfb_config"]["holes"][0]["manual_x_mm"] = -165.
    changed_x["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"] = deepcopy(
        changed_x["nfb_config"]
    )
    mutants["other_world_x"] = changed_x
    changed_number = deepcopy(approved)
    changed_number["nfb_config"]["holes"].pop()
    changed_number["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"] = deepcopy(
        changed_number["nfb_config"]
    )
    mutants["other_row_count"] = changed_number
    wrong_bay = deepcopy(approved)
    wrong_bay["_receiving_runtime_selection"]["bay_id"] = "another-bay"
    mutants["other_bay"] = wrong_bay

    for key, mutant in mutants.items():
        target = tmp_path / key
        target.mkdir()
        with pytest.raises((ValueError, KeyError)):
            _export(mutant, parts, target)
        assert not list(target.glob("*.dxf")), key

    # Current model/row alone are never a release: even a W800 three-row
    # sample must not infer missing per-hole world X from 180-mm nominal pitch.
    pending = deepcopy(approved)
    pending["nfb_config"]["holes"][0]["manual_x_mm"] = None
    pending["nfb_config"]["holes"][0]["manual_x_state"] = "NONE"
    pending["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"] = deepcopy(
        pending["nfb_config"]
    )
    blocked = tmp_path / "unconfirmed"
    blocked.mkdir()
    with pytest.raises((ValueError, KeyError)):
        _export(pending, parts, blocked)
    assert not list(blocked.glob("*.dxf"))


def test_ac51_swt30_exact_verified_v5_pair_receipt_discloses_only_exported_models_and_xy(
    tmp_path,
):
    """Only a real saved/reopened CSV pair can display this scoped manufacture line."""
    from ae_engine.receiving_nfb_committed_final_scene import _submitted_csv_holes
    from ae_engine.receiving_nfb_y_projection import project_nfb_inner_door_nominal_y

    snap = _current()
    inner_id, holes = _submitted_csv_holes(snap)
    before = deepcopy(snap)
    pair = _export(snap, _scene(snap), tmp_path / "success")
    scope = pair.verified_v5_scope
    assert scope is not None
    assert (scope.set_id, scope.bay_id) == ("S", "B")
    assert scope.width_mm == pytest.approx(800.0)
    assert scope.inner_door_id == inner_id
    assert tuple(site.physical_hole_id for site in scope.sites) == (
        "nfb:0", "nfb:1",
    )
    assert tuple(site.model_ref for site in scope.sites) == (
        "nfbv5:士林:2P400", "nfbv5:士林:3P125SN",
    )
    assert [site.world_x_mm for site in scope.sites] == pytest.approx(
        [-150.0, 150.0],
    )
    assert [site.world_y_mm for site in scope.sites] == pytest.approx([
        project_nfb_inner_door_nominal_y(
            snap, inner_id, layer_count=h.layer_count, slot_index=h.slot_index,
        ).box_world_y_mm for h in holes
    ])
    label = scope.operator_label
    assert "可製造（內門）" in label
    for token in ("Set=S", "Bay=B", "W=800", "N=2", "X=-150",
                  "X=150", "nfbv5:士林:2P400", "nfbv5:士林:3P125SN",
                  "其他版本／位置／型號", "整箱未放行"):
        assert token in label
    assert all(Path(path).is_file() for path in (
        pair.inner_door_path, pair.base_plate_path,
    ))
    assert snap == before

    # An old pair receipt still describes ONLY the earlier output. Mutating
    # current committed coordinates cannot use the old scene to release a
    # current/new Bay scope; no new DXF or green status may be produced.
    changed = deepcopy(snap)
    changed["nfb_config"]["holes"][1]["manual_x_mm"] += 15.0
    changed["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"] = deepcopy(
        changed["nfb_config"]
    )
    new_directory = tmp_path / "stale"
    new_directory.mkdir()
    with pytest.raises(ValueError, match="CURRENT_FINALSCENE"):
        _export(changed, _scene(snap), new_directory)
    assert not list(new_directory.glob("*.dxf"))
    assert scope.sites[1].world_x_mm == pytest.approx(150.0)


def test_ac51_swt30_numeric_model_preview_without_successful_export_has_no_scope_label():
    """A constructed preview-style result cannot claim physical approval."""
    from gui_modules.application.receiving_nfb_pair_partial_export_action import (
        NfbCsvPairedPartOnlyDxf,
    )
    preview = NfbCsvPairedPartOnlyDxf(
        inner_door_path="", base_plate_path="",
        source_hole_ids=("nfb:0",), check_q_key="",
    )
    assert preview.verified_v5_scope is None
    assert preview.scope == "CSV_PAIR_PART_ONLY_NOT_WHOLE_CABINET"
