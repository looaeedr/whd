"""#2517: one persisted Receiving inner-door A/B/D, shared C and panel acceptance.

The three frames, certified physical Divider and real inner-door panel share
one saved operator source, Engine manufacturing results, folded 3D and independently
reopened DXFs. This is a PART_ONLY proof, not NFB or whole-cabinet approval.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import ezdxf
import pytest

from ae_engine import manufacturing_api as api
from ae_engine.cabinet_types import receiving
from ae_engine.contracts import ManufacturingContext, ResolvedManufacturingGeometry, ResolvedManufacturingPart
from ae_engine.door_dividers import divider_part_profiles
from ae_engine.inner_door_frames import (
    derive_all_inner_door_frames, inner_door_frame_part_profiles,
)
from ae_engine.inner_door_panels import inner_door_panel_part_profiles
from gui_modules.application import fold_designer_manufacturing_projection as gui
import phase6_project_file as project

SOURCE = {"w": 800.0, "h": 1600.0, "d": 350.0, "t": 2.0}
COLUMNS = ((800.0, (1100.0, 500.0)),)
CONFIRMATION = "fresh_family_confirmed"


def _factory_parts(dimensions, columns):
    common = {
        "confirmation": CONFIRMATION,
        "confirmed_door_layout_columns": columns,
    }
    frames = api.build_receiving_factory_confirmed_inner_door_frames(
        dimensions, **common,
    )
    panels = api.build_receiving_factory_confirmed_inner_door_panels(
        dimensions, **common,
    )
    divider = api.build_receiving_factory_confirmed_inner_door_lower_support(
        dimensions, **common,
    )
    certified_c = api.resolve_receiving_factory_confirmed_lower_divider_final_scene(
        dimensions, box_body_render_data=None, **common,
    )
    return frames, panels, divider, certified_c


def _real_sheets(frames, panels, divider, certified):
    by_key = {}
    for frame in frames:
        by_key[frame.stable_id] = (
            frame, api.build_inner_door_frame_render_data(frame),
            inner_door_frame_part_profiles((frame,))[frame.stable_id],
        )
    for panel in panels:
        by_key[panel.stable_id] = (
            panel, api.build_inner_door_panel_render_data(panel),
            inner_door_panel_part_profiles((panel,))[panel.stable_id],
        )
    by_key[divider.stable_id] = (
        divider, certified, divider_part_profiles((divider,))[divider.stable_id],
    )
    return by_key


def test_saved_receiving_abd_c_panel_2d_3d_gui_engine_dxf_parity(tmp_path):
    original = receiving.apply_family_defaults({"model": "受電箱", **SOURCE})
    original["multi_door_enabled"] = True
    original["door_layout_columns"] = COLUMNS
    untouched = deepcopy(original)
    target = project.write_project(
        tmp_path / "inner-door-physical-source.p6fold",
        {"schema": project.PROJECT_SCHEMA, "snapshot": original},
    )
    saved = project.read_project(target)["snapshot"]
    assert saved["model"] == original["model"]
    assert saved["w"] == SOURCE["w"]
    assert saved["h"] == SOURCE["h"]

    # Actual Family identity and the independent confirmed-source Engine API
    # must resolve the same physical parts after persistence.
    dims = {key: saved[key] for key in ("w", "h", "d", "t")}
    columns = saved["door_layout_columns"]
    before = _factory_parts(SOURCE, COLUMNS)
    after = _factory_parts(dims, columns)
    before_frames, before_panels, before_c, before_scene_c = before
    frames, panels, divider, scene_c = after
    assert frames == before_frames
    assert panels == before_panels
    assert divider == before_c
    assert scene_c.scene == before_scene_c.scene
    assert scene_c.material.equals(before_scene_c.material)
    assert scene_c.fold_guides == before_scene_c.fold_guides

    assert frames == derive_all_inner_door_frames(
        receiving.derive_inner_door_frame_sets(saved)
    )
    assert panels == receiving.derive_inner_door_panels(saved)
    assert {f.side for f in frames} == {"top", "left", "right"}
    assert {f.side: f.blank_width for f in frames} == {
        "top": 90.0, "left": 90.0, "right": 110.0,
    }
    assert {f.side: f.span for f in frames} == {
        "top": 696.0, "left": 1098.0, "right": 1098.0,
    }
    assert len(panels) == 1
    assert panels[0].stable_id == "inner_door:upper:panel"
    assert panels[0].unfolded_width == pytest.approx(723.0)
    assert panels[0].unfolded_height == pytest.approx(1075.0)
    assert divider.axis == "HORIZONTAL"
    assert divider.stable_id.startswith("box_body:divider:")
    assert "bottom_frame" not in divider.stable_id
    assert scene_c.metadata["divider_assembly_relief"]["verified"] is True
    assert scene_c.metadata["divider_assembly_relief"]["candidate_status"] == (
        "CERTIFIED_REGISTRY_VERIFIED"
    )

    raw_c = api.build_box_body_divider_render_data(divider)
    assert scene_c.material.area < raw_c.material.area  # real CROSS, not a rectangle
    sheets = _real_sheets(frames, panels, divider, scene_c)
    keys = {
        "inner_door:upper:top_frame",
        "inner_door:upper:left_frame",
        "inner_door:upper:right_frame",
        "inner_door:upper:panel",
        divider.stable_id,
    }
    assert set(sheets) == keys

    physical = []
    for key, (part, render, xy) in sheets.items():
        assert render.material.is_valid and not render.material.is_empty
        assert render.scene.primitives
        mesh = api.project_independent_part_view_mesh(
            key, render, x_profile=xy["X"], y_profile=xy["Y"],
            thickness=SOURCE["t"],
        )
        assert mesh.triangles
        physical.append(ResolvedManufacturingPart(
            part_key=key, render_data=render,
            x_profile=tuple(xy["X"]), y_profile=tuple(xy["Y"]),
        ))
    geometry = ResolvedManufacturingGeometry(parts=tuple(physical))
    door_only = api.select_resolved_export_geometry(
        geometry, {"door": "true", "box_body": "false"},
    )
    assert {item.part_key for item in door_only.parts} == keys
    body_only = api.select_resolved_export_geometry(
        geometry, {"door": "false", "box_body": "true"},
    )
    assert {item.part_key for item in body_only.parts} == {divider.stable_id}

    # The shipped GUI export adapter must consume the same authoritative
    # cached Engine FinalScene, not rebuild an unverified frame or raw C blank.
    gui_dir = tmp_path / "gui"
    gui_dir.mkdir()
    context = ManufacturingContext(resource_root=Path(__file__).resolve().parents[1])
    host = SimpleNamespace(
        _flush_phase6_authoritative_state=lambda: None,
        _require_verified_baseline_sources_for_manufacturing=lambda: None,
        _authoritative_render_data=lambda spec, _context: sheets[spec.stable_id][1],
    )
    for key, (part, _render, _xy) in sheets.items():
        out = gui_dir / (key.replace(":", "_") + ".dxf")
        gui._export_authoritative_part(host, part, out, context)
        assert out.is_file()

    # Separate GUI and Engine DXFs must both be independently reopened and
    # verified against each canonical physical sheet, including certified C.
    output = api.save_selected_resolved_manufacturing_dxf(
        saved, geometry, {"door": "true", "box_body": "false"},
        tmp_path / "engine",
    )
    assert set(output) == keys
    for key, (_part, render, _xy) in sheets.items():
        gui_path = gui_dir / (key.replace(":", "_") + ".dxf")
        for dxf in (gui_path, Path(output[key])):
            reopened = ezdxf.readfile(dxf)
            assert reopened.audit().errors == []
            assert any(x.dxf.layer == "CUTTING" for x in reopened.modelspace())
            assert api.verify_saved_part_render_data_dxf(render, dxf).ok
    assert original == untouched


@pytest.mark.parametrize("invalid", (True, 0, -2.0, float("nan")))
def test_saved_inner_door_invalid_thickness_does_not_grant_manufacturing(
    tmp_path, invalid,
):
    source = receiving.apply_family_defaults({"model": "受電箱", **SOURCE})
    source["t"] = invalid
    target = project.write_project(
        tmp_path / "invalid-inner-door.p6fold",
        {"schema": project.PROJECT_SCHEMA, "snapshot": source},
    )
    loaded = project.read_project(target)["snapshot"]
    with pytest.raises((ValueError, TypeError)):
        api.build_receiving_factory_confirmed_inner_door_frames(
            {k: loaded[k] for k in ("w", "h", "d", "t")},
            confirmation=CONFIRMATION,
            confirmed_door_layout_columns=COLUMNS,
        )
    assert not (tmp_path / "invalid-dxf").exists()
