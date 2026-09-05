# -*- coding: utf-8 -*-
import json
from pathlib import Path
from types import SimpleNamespace

import ezdxf
from shapely.geometry import Point

import fold_designer_bridge as bridge
from ae_engine import ae, manufacturing_api
from ae_engine.sheetmetal_drawing import DrawingScene, PolylinePrimitive


def _snapshot():
    return {
        "w": 500.0, "h": 600.0, "d": 200.0, "t": 2.0, "fw": 25.0,
        "yl1": 15.0, "yr1": 17.0, "ytop1": 16.0, "ybottom1": 18.0,
        "door_gap_w": 3.5, "door_gap_h": 3.5,
        "door_fold_l": 19.0, "door_fold_r": 19.0,
        "door_fold_t": 19.0, "door_fold_b": 19.0,
    }


def test_tail_endcap_y_profile_uses_native_min_y_to_max_y_order():
    head = bridge.build_endcap_xy_profiles(_snapshot(), part_key="head")
    tail = bridge.build_endcap_xy_profiles(_snapshot(), part_key="tail")

    assert [seg.get("phase6_key") for seg in head["Y"]] == [
        "ytop1", "fw", "endcap_d_core", "ybottom1"
    ]
    assert [seg.get("phase6_key") for seg in tail["Y"]] == [
        "ybottom1", "endcap_d_core", "fw", "ytop1"
    ]
    assert [seg.get("angle") for seg in tail["Y"]] == [-90, -90, -90, None]


def test_door_baseline_preserves_complex_closed_cutting_handle_polyline(tmp_path, monkeypatch):
    path = tmp_path / "門.dxf"
    doc = ezdxf.new("R2010")
    for name, color in [("CUTTING", 3), ("BEND", 5)]:
        if name not in doc.layers:
            doc.layers.new(name=name, dxfattribs={"color": color})
    msp = doc.modelspace()
    msp.add_lwpolyline([(0, 0), (400, 0), (400, 600), (0, 600)], close=True,
                       dxfattribs={"layer": "CUTTING"})
    for x in (20, 380):
        msp.add_line((x, 0), (x, 600), dxfattribs={"layer": "BEND"})
    for y in (20, 580):
        msp.add_line((0, y), (400, y), dxfattribs={"layer": "BEND"})

    # Real handle/window profiles are often rounded and contain >10 vertices.
    # Point-count is not a valid way to decide that a CUTTING polyline is an old outline.
    handle = []
    import math
    for i in range(24):
        a = 2 * math.pi * i / 24.0
        handle.append((170 + 30 * math.cos(a), 160 + 55 * math.sin(a)))
    msp.add_lwpolyline(handle, close=True, dxfattribs={"layer": "CUTTING"})
    doc.saveas(path)

    monkeypatch.setattr(ae, "baseline_part_path", lambda model, filename: str(path))
    monkeypatch.setattr(ae, "baseline_expected_path", lambda model, filename: str(path))

    scene = ae.get_stretched_door_data(
        "TEST", 500, 600, 2, 25, 3.5, 3.5, 30, 30, 30, 30
    ).scene
    complex_profiles = [
        p for p in scene.primitives
        if isinstance(p, PolylinePrimitive)
        and str(p.layer).upper() == "CUTTING"
        and p.closed and len(p.points) > 10
    ]
    # One complex CUTTING is the formula outer contour; the other is the handle.
    handle_profile = min(
        complex_profiles,
        key=lambda p: (
            (max(q.x for q in p.points) - min(q.x for q in p.points))
            * (max(q.y for q in p.points) - min(q.y for q in p.points))
        ),
    )
    assert len(handle_profile.points) == 24
    material = manufacturing_api.material_polygon_from_final_scene(scene)
    mapped_center_x = sum(float(p.x) for p in handle_profile.points) / len(handle_profile.points)
    mapped_center_y = sum(float(p.y) for p in handle_profile.points) / len(handle_profile.points)
    assert not material.contains(Point(mapped_center_x, mapped_center_y))



def test_door_baseline_preserves_cutting_handle_inside_insert_block(tmp_path, monkeypatch):
    path = tmp_path / "門.dxf"
    doc = ezdxf.new("R2010")
    for name, color in [("CUTTING", 3), ("BEND", 5)]:
        if name not in doc.layers:
            doc.layers.new(name=name, dxfattribs={"color": color})
    msp = doc.modelspace()
    msp.add_lwpolyline([(0, 0), (400, 0), (400, 600), (0, 600)], close=True,
                       dxfattribs={"layer": "CUTTING"})
    for x in (20, 380):
        msp.add_line((x, 0), (x, 600), dxfattribs={"layer": "BEND"})
    for y in (20, 580):
        msp.add_line((0, y), (400, y), dxfattribs={"layer": "BEND"})

    block = doc.blocks.new(name="HANDLE_CUT")
    block.add_lwpolyline(
        [(0, 0), (60, 0), (60, 90), (0, 90)], close=True,
        dxfattribs={"layer": "CUTTING"},
    )
    msp.add_blockref("HANDLE_CUT", (140, 120), dxfattribs={"layer": "CUTTING"})
    doc.saveas(path)

    monkeypatch.setattr(ae, "baseline_part_path", lambda model, filename: str(path))
    monkeypatch.setattr(ae, "baseline_expected_path", lambda model, filename: str(path))

    scene = ae.get_stretched_door_data(
        "TEST", 500, 600, 2, 25, 3.5, 3.5, 30, 30, 30, 30
    ).scene
    material = manufacturing_api.material_polygon_from_final_scene(scene)
    # Locate the mapped block polyline and prove it became a real material hole.
    profiles = [
        p for p in scene.primitives
        if isinstance(p, PolylinePrimitive)
        and str(p.layer).upper() == "CUTTING" and p.closed and len(p.points) == 4
    ]
    handle = min(
        profiles,
        key=lambda p: (max(q.x for q in p.points)-min(q.x for q in p.points))
                    * (max(q.y for q in p.points)-min(q.y for q in p.points)),
    )
    cx = sum(float(q.x) for q in handle.points) / 4.0
    cy = sum(float(q.y) for q in handle.points) / 4.0
    assert not material.contains(Point(cx, cy))

def test_diagnostic_snapshot_contains_fold_profiles_and_exact_final_geometry():
    scene = DrawingScene()
    scene.add_polyline([(0, 0), (100, 0), (100, 60), (0, 60)], layer="CUTTING", closed=True)
    scene.add_circle((30, 30), 5, layer="CUTTING")
    render_data = manufacturing_api.PartRenderData(
        scene=scene, material=manufacturing_api.material_polygon_from_final_scene(scene)
    )
    profiles = bridge.build_standard_part_profiles(_snapshot(), "door")

    from phase6_designer_workspace import Phase6DesignerWorkspace
    workspace = Phase6DesignerWorkspace.from_snapshot({
        "existing_parts": ["box_body", "door", "tail"],
        "active_part": "door",
        "part_features": {"door": [], "tail": []},
        "part_face_features": {},
        "part_profiles": {
            "door": profiles,
            "tail": bridge.build_endcap_xy_profiles(_snapshot(), part_key="tail"),
        },
    })
    holder = SimpleNamespace(
        designer_workspace=workspace,
        _phase6_input_snapshot={**_snapshot(), "model": "PW"},
        _settings_values=dict(_snapshot()),
        _phase6_box_whd={"w": 500.0, "h": 600.0, "d": 200.0},
        _phase6_corner_state={},
        _phase6_corner_pair_same={},
        _phase6_assembly_type=bridge.CornerTypeId.INSERT_OVERLAY,
        _phase6_endcap_fw_state={},
        _scene_query_callback=lambda part, payload: render_data,
        state=SimpleNamespace(
            profiles={"X": profiles["X"], "Y": profiles["Y"]},
            profiles_vault={"箱身": []},
        ),
        baseline_model_var=SimpleNamespace(get=lambda: "PW"),
        _phase6_baseline_initial_model="PW",
    )

    data = bridge._phase6_build_diagnostic_snapshot(holder)
    assert data["schema"] == "phase6-fold-diagnostic-v1"
    assert data["active_part"] == "door"
    assert "tail" in data["workspace"]["part_profiles"]
    assert data["active_part_payload"]["model"] == "PW"
    assert any(p["layer"] == "CUTTING" and p["type"] == "CirclePrimitive"
               for p in data["final_geometry"]["scene"]["primitives"])
    assert data["final_geometry"]["material"]["interior_count"] == 1
    assert data["final_geometry"]["material"]["geojson"]["type"] == "Polygon"


def test_diagnostic_json_writer_is_utf8_and_round_trips(tmp_path):
    path = tmp_path / "折彎診斷.json"
    payload = {"schema": "phase6-fold-diagnostic-v1", "label": "封尾", "x": 12.5}
    bridge._phase6_write_diagnostic_json(path, payload)
    assert json.loads(path.read_text(encoding="utf-8")) == payload


def test_project_file_controls_are_global_not_in_fold_designer_footer():
    source = Path(bridge.__file__).read_text(encoding="utf-8")
    gui_source = Path(__file__).resolve().parents[1].joinpath("gui.py").read_text(encoding="utf-8")
    assert 'text="開啟專案"' in gui_source
    assert 'text="儲存專案"' in gui_source
    assert 'text="另存新檔"' in gui_source
    assert 'text="讀檔"' not in source
    assert 'text="存檔"' not in source
    assert ".p6fold" in gui_source
