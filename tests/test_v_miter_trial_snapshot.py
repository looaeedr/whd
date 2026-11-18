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
