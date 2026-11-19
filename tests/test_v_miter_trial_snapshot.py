"""#3317 V-miter source-only preview metadata survives real .p6fold Save->Reload."""
from __future__ import annotations

from copy import deepcopy
import json

import ezdxf
import pytest

from ae_engine import manufacturing_api
from ae_engine.dxf_serialization import save_scene_dxf
from ae_engine.sheetmetal_drawing import DrawingScene, LinePrimitive, PolylinePrimitive
from ae_engine.sheetmetal_geometry_core import GeometryError, Vec2
from phase6_project_file import PROJECT_SCHEMA_V1, read_project, write_project


def _scene(angle=90):
    first = LinePrimitive(Vec2(-100, 0), Vec2(0, 0), "BEND")
    second = LinePrimitive(Vec2(0, 0), Vec2(0, 100), "BEND")
    input_args = dict(
        thickness_mm=2, first_flange_height_mm=20,
        second_flange_height_mm=30, second_fold_angle_deg=angle,
        relief_mode="RELIEF_HOLE", relief_t_factor=1.5,
    )
    ideal = manufacturing_api.project_ideal_v_miter_mating_candidate(
        DrawingScene([first, second]), first, second, **input_args,
    )
    a, b = ideal.first_flat_miter_ray[1], ideal.second_flat_miter_ray[1]
    outline = PolylinePrimitive(
        (Vec2(-100, a.y), Vec2(b.x, a.y),
         Vec2(b.x, 0), Vec2(30, 10),
         Vec2(30, 100), Vec2(-100, 100)),
        "CUTTING", closed=True,
    )
    return DrawingScene([outline, first, second]), first, second, input_args


def _new_scene_with_same_saved_physical_geometry(old):
    """Simulate a fresh PartSpec->Engine scene, with no old Python identities."""
    rows = []
    for p in old.primitives:
        if isinstance(p, PolylinePrimitive):
            rows.append(PolylinePrimitive(
                tuple(Vec2(x.x, x.y) for x in p.points),
                p.layer, closed=p.closed,
            ))
        elif isinstance(p, LinePrimitive):
            rows.append(LinePrimitive(
                Vec2(p.p1.x, p.p1.y), Vec2(p.p2.x, p.p2.y), p.layer,
            ))
    return DrawingScene(rows)


@pytest.mark.parametrize("angle", (60, 90, 120))
@pytest.mark.parametrize("relief_mode", ("ROUND_R", "RELIEF_HOLE"))
def test_real_p6fold_saved_trial_recomputes_same_2d_3d_and_check_dxf(
    tmp_path, angle, relief_mode,
):
    scene, first, second, args = _scene(angle)
    args["relief_mode"] = relief_mode
    captured = manufacturing_api.capture_v_miter_relief_trial_snapshot(
        scene, first, second, **args,
    )
    before = list(scene.primitives)
    assert captured["manufacturing_status"] == "V_MITER_RELIEF_FORMED_CONTACT_UNCERTIFIED"
    assert set(captured["parameters"]) == {
        "thickness_mm", "first_flange_height_mm",
        "second_flange_height_mm", "second_fold_angle_deg",
        "relief_mode", "relief_t_factor",
    }
    assert "trial_remaining_outline" not in json.dumps(captured)
    assert "CUTTING" not in captured
    original = manufacturing_api.replay_v_miter_relief_trial_snapshot(
        scene, captured,
    )

    saved = write_project(tmp_path / "v_miter_trial.p6fold", {
        "schema": PROJECT_SCHEMA_V1,
        "snapshot": {
            "model": "金庫型", "w":500, "h":600, "d":400, "t":2,
            "v_miter_trial_preview": captured,
        },
    })
    reread = read_project(saved)
    snapshot = reread["snapshot"]["v_miter_trial_preview"]
    assert snapshot == captured
    rebuilt = _new_scene_with_same_saved_physical_geometry(scene)
    assert rebuilt.primitives[1] is not first
    replay = manufacturing_api.replay_v_miter_relief_trial_snapshot(
        rebuilt, snapshot,
    )
    assert replay.relief.trial_remaining_outline == original.relief.trial_remaining_outline
    assert replay.formed_contact_start == original.formed_contact_start
    assert replay.formed_contact_end == original.formed_contact_end
    assert replay.formed_contact_length_mm == pytest.approx(
        original.formed_contact_length_mm,
    )
    preview = manufacturing_api.build_saved_v_miter_relief_trial_check_scene(
        rebuilt, snapshot,
    )
    assert [p.layer for p in preview.primitives] == [
        "DATUM", "CHECK", "DATUM", "DATUM",
    ]
    assert preview.primitives[1].points == replay.relief.trial_remaining_outline
    dxf_path = tmp_path / "v_miter_reloaded_check.dxf"
    save_scene_dxf(dxf_path, preview)
    entities = list(ezdxf.readfile(dxf_path).modelspace())
    assert [e.dxf.layer for e in entities] == [
        "DATUM", "CHECK", "DATUM", "DATUM",
    ]
    assert not any(e.dxf.layer in {"CUTTING", "BEND", "MARKING"} for e in entities)
    assert scene.primitives == before


@pytest.mark.parametrize("angle", (90, 120))
@pytest.mark.parametrize("mode", ("ROUND_R", "RELIEF_HOLE"))
@pytest.mark.parametrize("family", ("金庫型", "受電箱"))
def test_measured_r_ba_v2_p6fold_replays_same_physical_3d_and_check_dxf(
    tmp_path, angle, mode, family,
):
    from math import radians, pi
    from ae_engine.receiving_layout import new_receiving_layout

    scene, first, second, base = _scene(angle)
    base["relief_mode"] = mode
    measurement = {
        "first_inner_radius_mm": .5,
        "second_inner_radius_mm": .5,
        "first_bend_allowance_mm": (pi / 2) * (0.5 + .4 * 2),
        "second_bend_allowance_mm": radians(angle) * (0.5 + .4 * 2),
        "max_permitted_edge_trim_mm": 12,
    }
    before = tuple(scene.primitives)
    captured = manufacturing_api.capture_v_miter_radius_ba_trial_snapshot(
        scene, first, second, **base, **measurement,
    )
    assert captured["contract"] == "V_MITER_RADIUS_BA_SOURCE_V2"
    assert captured["manufacturing_status"] == "V_MITER_RADIUS_BA_INTERFACE_UNCERTIFIED"
    assert set(captured["parameters"]) == set(base) | set(measurement)
    encoded = json.dumps(captured)
    assert "triangles" not in encoded and "solid" not in encoded
    assert "corrected_check_outline" not in encoded
    original = manufacturing_api.replay_v_miter_radius_ba_trial_snapshot(
        scene, captured,
    )
    assert original.formed_volume_containment_meshes_closed

    project_snapshot = {
        "model": family, "w": 800, "h": 1600, "d": 350, "t": 2,
        "v_miter_radius_ba_trial_preview": captured,
    }
    if family == "受電箱":
        project_snapshot["active_mode"] = "set_bay"
        project_snapshot["receiving_layout"] = new_receiving_layout(
            width=800, height=1600, depth=350,
        )
    saved = write_project(tmp_path / "measured_r_ba_source.p6fold", {
        "schema": PROJECT_SCHEMA_V1,
        "snapshot": project_snapshot,
    })
    recovered = read_project(saved)["snapshot"]["v_miter_radius_ba_trial_preview"]
    assert recovered == captured
    rebuilt = _new_scene_with_same_saved_physical_geometry(scene)
    assert rebuilt.primitives[1] is not first
    replay = manufacturing_api.replay_v_miter_radius_ba_trial_snapshot(
        rebuilt, recovered,
    )
    assert replay.first_thick_solid_triangles == original.first_thick_solid_triangles
    assert replay.second_thick_solid_triangles == original.second_thick_solid_triangles
    assert replay.full_corrected_check_outline == original.full_corrected_check_outline
    assert replay.first_source_cut_face == original.first_source_cut_face
    assert replay.second_source_cut_face == original.second_source_cut_face
    assert replay.source_cut_face_continuity_trial == original.source_cut_face_continuity_trial
    assert replay.manufacturing_status.endswith("UNCERTIFIED")

    preview = manufacturing_api.build_saved_v_miter_radius_ba_check_scene(
        rebuilt, recovered,
    )
    assert [item.layer for item in preview.primitives] == [
        "DATUM", "CHECK", "DATUM", "DATUM",
    ]
    assert preview.primitives[1].points == replay.full_corrected_check_outline
    dxf = tmp_path / "saved_measured_r_ba_CHECK_only.dxf"
    save_scene_dxf(dxf, preview)
    layers = [item.dxf.layer for item in ezdxf.readfile(dxf).modelspace()]
    assert layers == ["DATUM", "CHECK", "DATUM", "DATUM"]
    assert not ({"CUTTING", "BEND", "MARKING"} & set(layers))
    assert tuple(scene.primitives) == before



@pytest.mark.parametrize("family", ("金庫型", "受電箱"))
@pytest.mark.parametrize("mode", ("ROUND_R", "RELIEF_HOLE"))
@pytest.mark.parametrize("angle", (90, 120))
def test_main_gui_open_save_preserves_legacy_v1_true_source_and_check_only_dxf(
    tmp_path, family, mode, angle,
):
    """A V1 .p6fold must not lose its R/hole trial at main-GUI re-save."""
    from types import SimpleNamespace
    from ae_engine.receiving_layout import new_receiving_layout
    from gui_modules.application import lifecycle as gui

    scene, first, second, params = _scene(angle)
    params["relief_mode"] = mode
    captured = manufacturing_api.capture_v_miter_relief_trial_snapshot(
        scene, first, second, **params,
    )
    original = manufacturing_api.replay_v_miter_true_thickness_collision_snapshot(
        scene, captured,
    )
    data = {
        "model": family, "w": 800, "h": 1600, "d": 350, "t": 2,
        "v_miter_trial_preview": captured,
    }
    if family == "受電箱":
        data["active_mode"] = "set_bay"
        data["receiving_layout"] = new_receiving_layout(
            width=800, height=1600, depth=350,
        )
    source_path = write_project(tmp_path / "source_v1.p6fold", {
        "schema": PROJECT_SCHEMA_V1, "snapshot": data,
    })
    opened = read_project(source_path)["snapshot"]
    preview = manufacturing_api.project_operator_v_miter_relief_preview_source(
        opened,
    )
    assert preview == captured
    assert preview is not captured
    assert preview["parameters"] is not captured["parameters"]

    host = SimpleNamespace(
        _v_miter_relief_trial_preview=preview,
        _v_miter_radius_ba_trial_preview=None,
        _make_original_fold_designer_snapshot=lambda: {
            key: value for key, value in opened.items()
            if key != "v_miter_trial_preview"
        },
        workspace_controller=SimpleNamespace(
            workspace_snapshot=lambda: {
                "existing_parts": [], "active_part": None,
                "part_profiles": {}, "box_body_structure": {},
            },
        ),
        endcap_fw_state={},
        endcap_bottom_wrap_state={},
    )
    composed = gui._compose_phase6_project_snapshot_from_main_gui(host)
    assert composed["v_miter_trial_preview"] == captured
    assert composed["v_miter_trial_preview"] is not captured
    assert "v_miter_radius_ba_trial_preview" not in composed
    resaved = write_project(tmp_path / "main_gui_resaved_v1.p6fold", {
        "schema": PROJECT_SCHEMA_V1, "snapshot": composed,
    })
    reopened = read_project(resaved)["snapshot"]
    assert reopened["v_miter_trial_preview"] == captured

    detached_scene = _new_scene_with_same_saved_physical_geometry(scene)
    restored = manufacturing_api.replay_v_miter_true_thickness_collision_snapshot(
        detached_scene, reopened["v_miter_trial_preview"],
    )
    assert restored.first_thick_solid_triangles == original.first_thick_solid_triangles
    assert restored.second_thick_solid_triangles == original.second_thick_solid_triangles
    check = manufacturing_api.build_saved_v_miter_relief_trial_check_scene(
        detached_scene, reopened["v_miter_trial_preview"],
    )
    output = tmp_path / "v1_gui_resaved_check.dxf"
    save_scene_dxf(output, check)
    assert [row.dxf.layer for row in ezdxf.readfile(output).modelspace()] == [
        "DATUM", "CHECK", "DATUM", "DATUM",
    ]
    assert check.primitives[1].points == restored.mating.relief.trial_remaining_outline

    # The next project has no V1: the previous source must not reappear.
    host._v_miter_relief_trial_preview = (
        manufacturing_api.project_operator_v_miter_relief_preview_source({})
    )
    missing = gui._compose_phase6_project_snapshot_from_main_gui(host)
    assert "v_miter_trial_preview" not in missing


@pytest.mark.parametrize("field,invalid", (
    ("thickness_mm", True),
    ("first_flange_height_mm", "20"),
    ("second_flange_height_mm", float("nan")),
    ("second_fold_angle_deg", 180),
    ("second_fold_angle_deg", False),
    ("relief_t_factor", None),
    ("relief_t_factor", float("inf")),
    ("relief_mode", "CERTIFIED"),
))
def test_legacy_v1_gui_open_rejects_corrupt_source_before_any_session_reset(
    field, invalid,
):
    from types import SimpleNamespace
    from gui_modules.application import lifecycle as gui

    scene, first, second, params = _scene()
    saved = manufacturing_api.capture_v_miter_relief_trial_snapshot(
        scene, first, second, **params,
    )
    bad = deepcopy(saved)
    bad["parameters"][field] = invalid
    events = []
    host = SimpleNamespace(
        _v_miter_relief_trial_preview={"previous": "V1"},
        _v_miter_radius_ba_trial_preview={"previous": "V2"},
        workspace_controller=SimpleNamespace(
            reset_receiving_mode_session=lambda: events.append("reset"),
        ),
        _reset_manual_corner_parameter_locks=lambda: events.append("corners"),
    )
    with pytest.raises(GeometryError, match="V-miter saved physical source"):
        manufacturing_api.project_operator_v_miter_relief_preview_source({
            "v_miter_trial_preview": bad,
        })
    with pytest.raises(GeometryError, match="V-miter saved physical source"):
        gui._apply_phase6_project_snapshot(host, {
            "model": "金庫型", "v_miter_trial_preview": bad,
        })
    assert events == []
    assert host._v_miter_relief_trial_preview == {"previous": "V1"}
    assert host._v_miter_radius_ba_trial_preview == {"previous": "V2"}


def test_v1_v2_check_metadata_both_survive_main_gui_composition_independently(
    tmp_path,
):
    """Different CHECK revisions can be stored without overwriting one another."""
    from math import pi
    from types import SimpleNamespace
    from gui_modules.application import lifecycle as gui

    scene, first, second, params = _scene()
    first_source = manufacturing_api.capture_v_miter_relief_trial_snapshot(
        scene, first, second, **params,
    )
    second_source = manufacturing_api.capture_v_miter_radius_ba_trial_snapshot(
        scene, first, second, **params,
        first_inner_radius_mm=.5, second_inner_radius_mm=.5,
        first_bend_allowance_mm=(pi / 2) * (0.5 + .4 * 2),
        second_bend_allowance_mm=(pi / 2) * (0.5 + .4 * 2),
        max_permitted_edge_trim_mm=12,
    )
    host = SimpleNamespace(
        _v_miter_relief_trial_preview=first_source,
        _v_miter_radius_ba_trial_preview=second_source,
        _make_original_fold_designer_snapshot=lambda: {
            "model": "金庫型", "w": 800, "h": 1600, "d": 350, "t": 2,
        },
        workspace_controller=SimpleNamespace(
            workspace_snapshot=lambda: {
                "existing_parts": [], "active_part": None,
                "part_profiles": {}, "box_body_structure": {},
            },
        ),
        endcap_fw_state={}, endcap_bottom_wrap_state={},
    )
    project = gui._compose_phase6_project_snapshot_from_main_gui(host)
    target = write_project(tmp_path / "both_check_sources.p6fold", {
        "schema": PROJECT_SCHEMA_V1, "snapshot": project,
    })
    reread = read_project(target)["snapshot"]
    assert reread["v_miter_trial_preview"] == first_source
    assert reread["v_miter_radius_ba_trial_preview"] == second_source
    assert "CERTIFIED" not in (
        reread["v_miter_trial_preview"]["manufacturing_status"],
        reread["v_miter_radius_ba_trial_preview"]["manufacturing_status"],
    )



def test_main_gui_committed_resave_preserves_existing_v2_r_ba_source_without_geometry(
    tmp_path,
):
    """Actual GUI project-composition path must not drop checked R/BA inputs."""
    from math import pi
    from types import SimpleNamespace
    from gui_modules.application import lifecycle as gui

    scene, first, second, source = _scene()
    measured = {
        "first_inner_radius_mm": .5,
        "second_inner_radius_mm": .5,
        "first_bend_allowance_mm": (pi / 2) * (0.5 + .4 * 2),
        "second_bend_allowance_mm": (pi / 2) * (0.5 + .4 * 2),
        "max_permitted_edge_trim_mm": 12,
    }
    captured = manufacturing_api.capture_v_miter_radius_ba_trial_snapshot(
        scene, first, second, **source, **measured,
    )
    saved_metadata = manufacturing_api.project_operator_v_miter_radius_ba_preview_source({
        "v_miter_radius_ba_trial_preview": captured,
    })
    assert saved_metadata == captured
    assert saved_metadata is not captured
    assert saved_metadata["parameters"] is not captured["parameters"]

    host = SimpleNamespace(
        _v_miter_radius_ba_trial_preview=saved_metadata,
        _make_original_fold_designer_snapshot=lambda: {
            "model": "金庫型", "w": 800, "h": 1600, "d": 350,
            "t": 2, "box_body_profile": [{"phase6_key": "zr1", "len": 25}],
        },
        workspace_controller=SimpleNamespace(
            workspace_snapshot=lambda: {
                "existing_parts": [], "active_part": None,
                "part_profiles": {}, "box_body_structure": {},
            },
        ),
        endcap_fw_state={},
        endcap_bottom_wrap_state={},
    )
    composed = gui._compose_phase6_project_snapshot_from_main_gui(host)
    assert composed["v_miter_radius_ba_trial_preview"] == captured
    assert composed["v_miter_radius_ba_trial_preview"] is not captured

    # Main GUI's actual phase6_file writer and independent read codec.
    path = write_project(tmp_path / "gui_v_miter_resaved.p6fold", {
        "schema": PROJECT_SCHEMA_V1, "snapshot": composed,
    })
    reopened = read_project(path)["snapshot"]
    assert reopened["v_miter_radius_ba_trial_preview"] == captured
    true_replay = manufacturing_api.replay_v_miter_radius_ba_trial_snapshot(
        _new_scene_with_same_saved_physical_geometry(scene),
        reopened["v_miter_radius_ba_trial_preview"],
    )
    assert true_replay.formed_volume_containment_meshes_closed
    assert true_replay.manufacturing_status.endswith("UNCERTIFIED")

    # Opening another project without saved R/BA is not permission to
    # accidentally carry the previous project's orphaned trial source.
    host._v_miter_radius_ba_trial_preview = manufacturing_api.project_operator_v_miter_radius_ba_preview_source({})
    missing = gui._compose_phase6_project_snapshot_from_main_gui(host)
    assert "v_miter_radius_ba_trial_preview" not in missing


def test_main_gui_open_preflights_forged_v2_before_reset_and_does_not_lose_old_state():
    from types import SimpleNamespace
    from gui_modules.application import lifecycle as gui

    events = []
    host = SimpleNamespace(
        _v_miter_radius_ba_trial_preview={"prior": "owned"},
        workspace_controller=SimpleNamespace(
            reset_receiving_mode_session=lambda: events.append("reset"),
        ),
        _reset_manual_corner_parameter_locks=lambda: events.append("corner_reset"),
    )
    corrupt = {
        "model": "金庫型",
        "v_miter_radius_ba_trial_preview": {
            "contract": "V_MITER_RADIUS_BA_SOURCE_V2",
            "manufacturing_status": "CERTIFIED",
            "parameters": {},
        },
    }
    with pytest.raises(GeometryError, match="saved trial"):
        gui._apply_phase6_project_snapshot(host, corrupt)
    assert events == []
    assert host._v_miter_radius_ba_trial_preview == {"prior": "owned"}



def test_v2_main_gui_open_rejects_all_untyped_or_invalid_physical_source_fields():
    """A saved CHECK-only V2 preview must fail before the GUI mutates state.

    #3356 preflight previously validated only measured R/BA/trim values.
    Changing an older base source field still passed through Open->Save,
    even though a fresh physical solver would refuse the same input.
    """
    from math import pi
    from types import SimpleNamespace
    from gui_modules.application import lifecycle as gui

    scene, first, second, source = _scene()
    measured = {
        "first_inner_radius_mm": .5,
        "second_inner_radius_mm": .5,
        "first_bend_allowance_mm": (pi / 2) * (0.5 + .4 * 2),
        "second_bend_allowance_mm": (pi / 2) * (0.5 + .4 * 2),
        "max_permitted_edge_trim_mm": 12,
    }
    captured = manufacturing_api.capture_v_miter_radius_ba_trial_snapshot(
        scene, first, second, **source, **measured,
    )
    events = []
    host = SimpleNamespace(
        _v_miter_radius_ba_trial_preview={"prior": "unchanged"},
        workspace_controller=SimpleNamespace(
            reset_receiving_mode_session=lambda: events.append("reset"),
        ),
        _reset_manual_corner_parameter_locks=lambda: events.append("corner_reset"),
    )
    invalid_sources = (
        ("thickness_mm", True),
        ("thickness_mm", "2"),
        ("thickness_mm", 0),
        ("first_flange_height_mm", float("nan")),
        ("first_flange_height_mm", 0),
        ("second_flange_height_mm", float("inf")),
        ("second_flange_height_mm", -1),
        ("second_fold_angle_deg", True),
        ("second_fold_angle_deg", "90"),
        ("second_fold_angle_deg", 0),
        ("second_fold_angle_deg", 180),
        ("relief_mode", "UNKNOWN"),
        ("relief_mode", True),
        ("relief_t_factor", None),
        ("relief_t_factor", False),
        ("relief_t_factor", "1.5"),
        ("relief_t_factor", -1),
    )
    for field, value in invalid_sources:
        invalid = deepcopy(captured)
        invalid["parameters"][field] = value
        envelope = {"v_miter_radius_ba_trial_preview": invalid}
        with pytest.raises(GeometryError, match="V-miter saved physical source"):
            manufacturing_api.project_operator_v_miter_radius_ba_preview_source(
                envelope,
            )
        with pytest.raises(GeometryError, match="V-miter saved physical source"):
            manufacturing_api.replay_v_miter_radius_ba_trial_snapshot(
                scene, invalid,
            )
        with pytest.raises(GeometryError, match="V-miter saved physical source"):
            gui._apply_phase6_project_snapshot(host, {
                "model": "金庫型", **envelope,
            })
        assert events == [], (field, value)
        assert host._v_miter_radius_ba_trial_preview == {
            "prior": "unchanged",
        }
    assert captured["manufacturing_status"].endswith("UNCERTIFIED")
    assert captured["parameters"]["thickness_mm"] == source["thickness_mm"]



def test_measured_r_ba_saved_source_rejects_stale_or_forged_inputs():
    from math import radians, pi

    scene, first, second, basic = _scene()
    measured = {
        "first_inner_radius_mm": .5,
        "second_inner_radius_mm": .5,
        "first_bend_allowance_mm": (pi / 2) * (0.5 + .4 * 2),
        "second_bend_allowance_mm": radians(90) * (0.5 + .4 * 2),
        "max_permitted_edge_trim_mm": 12,
    }
    saved = manufacturing_api.capture_v_miter_radius_ba_trial_snapshot(
        scene, first, second, **basic, **measured,
    )
    # V1 relief snapshot and V2 measured-R/BA snapshot must never be
    # silently interpreted as the other contract.
    with pytest.raises(GeometryError, match="contract revision"):
        manufacturing_api.replay_v_miter_relief_trial_snapshot(scene, saved)
    v1 = manufacturing_api.capture_v_miter_relief_trial_snapshot(
        scene, first, second, **basic,
    )
    with pytest.raises(GeometryError, match="contract revision"):
        manufacturing_api.replay_v_miter_radius_ba_trial_snapshot(scene, v1)
    corrupt = []
    for key, invalid in (
        ("contract", "V_MITER_CERTIFIED"),
        ("manufacturing_status", "V_MITER_CUTTING_CERTIFIED"),
        ("first_bend_index", True),
    ):
        trial = deepcopy(saved)
        trial[key] = invalid
        corrupt.append(trial)
    for field, value in (
        ("first_inner_radius_mm", True),
        ("second_inner_radius_mm", "0.5"),
        ("first_bend_allowance_mm", float("nan")),
        ("second_bend_allowance_mm", float("inf")),
        ("max_permitted_edge_trim_mm", 0),
    ):
        trial = deepcopy(saved)
        trial["parameters"][field] = value
        corrupt.append(trial)
    missing = deepcopy(saved)
    del missing["parameters"]["second_bend_allowance_mm"]
    corrupt.append(missing)
    extra = deepcopy(saved)
    extra["parameters"]["verified"] = True
    corrupt.append(extra)
    for bad in corrupt:
        with pytest.raises(GeometryError):
            manufacturing_api.replay_v_miter_radius_ba_trial_snapshot(
                scene, bad,
            )
        with pytest.raises(GeometryError):
            manufacturing_api.build_saved_v_miter_radius_ba_check_scene(
                scene, bad,
            )
    stale = _new_scene_with_same_saved_physical_geometry(scene)
    old = stale.primitives[0]
    stale.primitives[0] = PolylinePrimitive(
        tuple(Vec2(p.x + .5, p.y) for p in old.points),
        layer="CUTTING", closed=True,
    )
    with pytest.raises(GeometryError, match="source geometry has changed"):
        manufacturing_api.replay_v_miter_radius_ba_trial_snapshot(
            stale, saved,
        )
    assert saved["manufacturing_status"].endswith("UNCERTIFIED")


def test_saved_trial_rejects_changed_cutting_source_after_reload():
    scene, first, second, args = _scene()
    captured = manufacturing_api.capture_v_miter_relief_trial_snapshot(
        scene, first, second, **args,
    )
    stale = _new_scene_with_same_saved_physical_geometry(scene)
    old = stale.primitives[0]
    stale.primitives[0] = PolylinePrimitive(
        tuple(Vec2(p.x + 0.5, p.y) for p in old.points),
        layer="CUTTING", closed=True,
    )
    with pytest.raises(GeometryError, match="source geometry has changed"):
        manufacturing_api.replay_v_miter_relief_trial_snapshot(stale, captured)


@pytest.mark.parametrize("mutator", [
    lambda p: p.update(manufacturing_status="CERTIFIED"),
    lambda p: p.update(contract="V_MITER_CUTTING_CERTIFIED"),
    lambda p: p.update(first_bend_index=True),
    lambda p: p.update(second_bend_index=p["first_bend_index"]),
    lambda p: p["parameters"].update(relief_t_factor=False),
    lambda p: p["parameters"].update(relief_mode="UNKNOWN"),
    lambda p: p["parameters"].update(verified=True),
    lambda p: p.update(verified=True),
])
def test_saved_trial_tamper_never_promotes_certified_or_reuses_old_preview(mutator):
    scene, first, second, args = _scene()
    valid = manufacturing_api.capture_v_miter_relief_trial_snapshot(
        scene, first, second, **args,
    )
    changed = deepcopy(valid)
    mutator(changed)
    with pytest.raises(GeometryError):
        manufacturing_api.replay_v_miter_relief_trial_snapshot(scene, changed)


def test_snapshot_replay_rejects_changed_bend_role_even_with_same_geometry():
    scene, first, second, args = _scene()
    captured = manufacturing_api.capture_v_miter_relief_trial_snapshot(
        scene, first, second, **args,
    )
    replay_source = _new_scene_with_same_saved_physical_geometry(scene)
    replay_source.primitives[1], replay_source.primitives[2] = (
        replay_source.primitives[2], replay_source.primitives[1],
    )
    with pytest.raises(GeometryError, match="source geometry has changed"):
        manufacturing_api.replay_v_miter_relief_trial_snapshot(
            replay_source, captured,
        )


def test_preview_snapshot_does_not_approve_new_corner_selection():
    from ae_engine.sheetmetal_geometry_core import CornerTypeId, EDITABLE_CORNER_TYPE_IDS
    assert len(EDITABLE_CORNER_TYPE_IDS) == 4
    with pytest.raises(ValueError):
        CornerTypeId("V_MITER")



def test_receiving_p6fold_v2_keeps_v_miter_preview_uncertified(tmp_path):
    """Independent Receiving Family project must not drop preview source."""
    from ae_engine.receiving_layout import new_receiving_layout
    from phase6_project_file import PROJECT_SCHEMA_V2

    scene, first, second, args = _scene(120)
    captured = manufacturing_api.capture_v_miter_relief_trial_snapshot(
        scene, first, second, **args,
    )
    filename = write_project(tmp_path / "receiving_v_miter.p6fold", {
        "schema": PROJECT_SCHEMA_V1,
        "snapshot": {
            "model": "受電箱", "w": 800, "h": 1600, "d": 350, "t": 2,
            "active_mode": "set_bay",
            "receiving_layout": new_receiving_layout(
                width=800, height=1600, depth=350,
            ),
            "v_miter_trial_preview": captured,
        },
    })
    payload = read_project(filename)
    assert payload["schema"] == PROJECT_SCHEMA_V2
    snapshot = payload["snapshot"]["v_miter_trial_preview"]
    assert snapshot == captured
    clone = _new_scene_with_same_saved_physical_geometry(scene)
    trial = manufacturing_api.replay_v_miter_relief_trial_snapshot(
        clone, snapshot,
    )
    assert trial.manufacturing_status == "V_MITER_RELIEF_FORMED_CONTACT_UNCERTIFIED"
    assert trial.relief.relief_mode.value == "RELIEF_HOLE"



@pytest.mark.parametrize("angle", (90, 120))
@pytest.mark.parametrize("relief_mode", ("ROUND_R", "RELIEF_HOLE"))
@pytest.mark.parametrize("family", ("金庫型", "受電箱"))
def test_p6fold_true_t_solid_replayed_from_same_source_without_saved_mesh(
    tmp_path, angle, relief_mode, family,
):
    """Real project file -> new Scene identities -> identical true-T 3D shadow.

    No second 2D source is allowed: the DXF CHECK polygon and recomputed
    thick 3D flanges must be based on the one validated saved trial source.
    """
    from ae_engine.receiving_layout import new_receiving_layout

    scene, first, second, args = _scene(angle)
    args["relief_mode"] = relief_mode
    before = list(scene.primitives)
    captured = manufacturing_api.capture_v_miter_relief_trial_snapshot(
        scene, first, second, **args,
    )
    assert "solid" not in json.dumps(captured).lower()
    assert "triangles" not in json.dumps(captured).lower()
    original = manufacturing_api.replay_v_miter_true_thickness_collision_snapshot(
        scene, captured,
    )
    payload = {
        "model": family, "w": 800, "h": 1600, "d": 350, "t": 2,
        "v_miter_trial_preview": captured,
    }
    if family == "受電箱":
        payload["active_mode"] = "set_bay"
        payload["receiving_layout"] = new_receiving_layout(
            width=800, height=1600, depth=350,
        )
    path = write_project(tmp_path / "v_miter_true_t.p6fold", {
        "schema": PROJECT_SCHEMA_V1,
        "snapshot": payload,
    })
    reread = read_project(path)
    recovered = reread["snapshot"]["v_miter_trial_preview"]
    assert recovered == captured
    reloaded_scene = _new_scene_with_same_saved_physical_geometry(scene)
    assert reloaded_scene.primitives[1] is not first
    shadow = manufacturing_api.replay_v_miter_true_thickness_collision_snapshot(
        reloaded_scene, recovered,
    )
    assert shadow.manufacturing_status == "V_MITER_TRUE_T_COLLISION_UNCERTIFIED"
    assert shadow.first_formed_skin_triangles == original.first_formed_skin_triangles
    assert shadow.second_formed_skin_triangles == original.second_formed_skin_triangles
    assert shadow.first_thick_solid_triangles == original.first_thick_solid_triangles
    assert shadow.second_thick_solid_triangles == original.second_thick_solid_triangles
    assert shadow.surface_interference_pair_count == original.surface_interference_pair_count
    assert shadow.surface_intersection_segments == original.surface_intersection_segments
    assert shadow.mating.relief.trial_remaining_outline == original.mating.relief.trial_remaining_outline

    scene_2d = manufacturing_api.build_saved_v_miter_relief_trial_check_scene(
        reloaded_scene, recovered,
    )
    assert scene_2d.primitives[1].points == shadow.mating.relief.trial_remaining_outline
    output = tmp_path / "from_saved_source_CHECK_only.dxf"
    save_scene_dxf(output, scene_2d)
    layers = [e.dxf.layer for e in ezdxf.readfile(output).modelspace()]
    assert layers == ["DATUM", "CHECK", "DATUM", "DATUM"]
    assert not ({"CUTTING", "BEND", "MARKING"} & set(layers))
    assert scene.primitives == before


def test_saved_60_degree_trial_rejects_unproven_true_t_material_extension():
    scene, first, second, args = _scene(60)
    captured = manufacturing_api.capture_v_miter_relief_trial_snapshot(
        scene, first, second, **args,
    )
    reloaded = _new_scene_with_same_saved_physical_geometry(scene)
    # Older 2D CHECK preview may remain inspectable; new *physical*
    # collision proof cannot silently treat an unowned BEND extension as stock.
    assert manufacturing_api.replay_v_miter_relief_trial_snapshot(
        reloaded, captured,
    ).manufacturing_status.endswith("UNCERTIFIED")
    with pytest.raises(GeometryError, match="independent source material extension"):
        manufacturing_api.replay_v_miter_true_thickness_collision_snapshot(
            reloaded, captured,
        )


def test_saved_true_t_collision_disallows_forged_certification_or_stale_material():
    scene, first, second, args = _scene(90)
    saved = manufacturing_api.capture_v_miter_relief_trial_snapshot(
        scene, first, second, **args,
    )
    forged = deepcopy(saved)
    forged["manufacturing_status"] = "CERTIFIED"
    with pytest.raises(GeometryError, match="cannot claim certified"):
        manufacturing_api.replay_v_miter_true_thickness_collision_snapshot(
            scene, forged,
        )
    stale = _new_scene_with_same_saved_physical_geometry(scene)
    original = stale.primitives[0]
    stale.primitives[0] = PolylinePrimitive(
        tuple(Vec2(p.x + 1, p.y) for p in original.points),
        layer="CUTTING", closed=True,
    )
    with pytest.raises(GeometryError, match="source geometry has changed"):
        manufacturing_api.replay_v_miter_true_thickness_collision_snapshot(
            stale, saved,
        )
