from __future__ import annotations

from copy import deepcopy
import os

import pytest

pytestmark = pytest.mark.skipif(
    not (os.name == "nt" or os.environ.get("DISPLAY")),
    reason="requires Tk display",
)


DIVIDER_KEY = "box_body:divider:receiving-main:HORIZONTAL:C0_R0|R1"


def _pump(root):
    root.update_idletasks()
    root.update()


def _open_receiving():
    import tkinter as tk
    import gui

    root = tk.Tk()
    root.withdraw()
    app = gui.BoxCalculatorGUI(root)
    app.baseline_var.set("受電箱")
    _pump(root)
    designer = app.open_original_fold_designer()
    designer.root.deiconify()
    designer.root.geometry("1120x720+0+0")
    _pump(root)
    return root, app, designer


def _close(root, designer):
    try:
        if designer is not None:
            designer.root.destroy()
    except Exception:
        pass
    try:
        root.destroy()
    except Exception:
        pass


def _solve_divider(designer):
    import fold_designer_bridge as bridge

    resolved = bridge._phase6_resolve_manufacturing_geometry(designer)
    solved = resolved.part(DIVIDER_KEY).render_data
    relief = dict(getattr(solved, "metadata", {}) or {}).get("divider_assembly_relief") or {}
    assert relief.get("verified") is True
    assert len(list(solved.material.exterior.coords)) > 5
    return solved


def test_t48_3_scene_query_callback_replays_exact_solved_divider_final_material():
    import fold_designer_bridge as bridge

    root = app = designer = None
    try:
        root, app, designer = _open_receiving()
        solved = _solve_divider(designer)

        payload = bridge._phase6_scene_query_payload_for_part(designer, DIVIDER_KEY)
        replayed = app._query_fold_designer_render_data(DIVIDER_KEY, payload)

        assert replayed.material.symmetric_difference(solved.material).area == pytest.approx(0.0, abs=1e-8)
        replay_relief = dict(getattr(replayed, "metadata", {}) or {}).get("divider_assembly_relief") or {}
        assert replay_relief.get("verified") is True
    finally:
        if root is not None:
            _close(root, designer)


def test_t48_3_project_roundtrip_preserves_divider_final_material(tmp_path):
    import fold_designer_bridge as bridge
    from phase6_project_file import PROJECT_SCHEMA, read_project, write_project

    root = app = designer = None
    root2 = app2 = None
    try:
        root, app, designer = _open_receiving()
        solved = _solve_divider(designer)

        # Publish the canonical solved state to the main GUI before saving.
        assert bridge._phase6_publish_live_state(designer, force=True) in {True, False}
        snapshot = app._compose_phase6_project_snapshot_from_main_gui()

        path = tmp_path / "receiving-divider.p6fold"
        write_project(path, {"schema": PROJECT_SCHEMA, "snapshot": snapshot, "final_geometry": {}})
        loaded = read_project(path)["snapshot"]

        state = dict(loaded.get("divider_relief_state") or {})
        assert state.get("schema_version") == 1
        assert dict(state.get("parts") or {}).get(DIVIDER_KEY, {}).get("verified") is True

        import tkinter as tk
        import gui
        root2 = tk.Tk()
        root2.withdraw()
        app2 = gui.BoxCalculatorGUI(root2)
        app2._apply_phase6_project_snapshot(deepcopy(loaded))
        _pump(root2)

        replay_payload = deepcopy(loaded)
        replay_payload["_use_committed_relief"] = True
        replayed = app2._query_fold_designer_render_data(DIVIDER_KEY, replay_payload)
        assert replayed.material.symmetric_difference(solved.material).area == pytest.approx(0.0, abs=1e-8)
    finally:
        if root2 is not None:
            try:
                root2.destroy()
            except Exception:
                pass
        if root is not None:
            _close(root, designer)


def test_t48_3_dxf_sink_serializes_replayed_divider_final_cutting(tmp_path):
    import ezdxf
    import fold_designer_bridge as bridge
    from ae_engine.manufacturing_api import save_part_render_data_dxf

    root = app = designer = None
    try:
        root, app, designer = _open_receiving()
        solved = _solve_divider(designer)
        bridge._phase6_publish_live_state(designer, force=True)

        payload = bridge._phase6_scene_query_payload_for_part(designer, DIVIDER_KEY)
        replayed = app._query_fold_designer_render_data(DIVIDER_KEY, payload)
        assert replayed.material.symmetric_difference(solved.material).area == pytest.approx(0.0, abs=1e-8)

        out = tmp_path / "divider.dxf"
        save_part_render_data_dxf(replayed, out, overwrite=True)
        doc = ezdxf.readfile(out)
        msp = doc.modelspace()

        cutting_polylines = []
        for entity in msp:
            if str(getattr(entity.dxf, "layer", "")).upper() != "CUTTING":
                continue
            if entity.dxftype() == "LWPOLYLINE" and bool(entity.closed):
                cutting_polylines.append(entity)
            elif entity.dxftype() == "POLYLINE" and bool(entity.is_closed):
                cutting_polylines.append(entity)

        assert cutting_polylines, "DXF missing closed CUTTING outline"
        # Relief makes the Divider exterior non-rectangular; the final outline
        # must therefore contain more than four distinct vertices.
        entity = max(
            cutting_polylines,
            key=lambda item: len(list(item.get_points())) if item.dxftype() == "LWPOLYLINE" else len(list(item.vertices)),
        )
        if entity.dxftype() == "LWPOLYLINE":
            vertices = [(float(row[0]), float(row[1])) for row in entity.get_points()]
        else:
            vertices = [(float(v.dxf.location.x), float(v.dxf.location.y)) for v in entity.vertices]
        assert len(vertices) > 4
    finally:
        if root is not None:
            _close(root, designer)
