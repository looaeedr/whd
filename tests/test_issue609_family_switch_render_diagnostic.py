from __future__ import annotations

import json
import os

import pytest


pytestmark = pytest.mark.skipif(
    not os.environ.get("DISPLAY"),
    reason="#609 family-switch diagnostic requires real Tk/Xvfb",
)


def _pump(root, cycles=8):
    for _ in range(cycles):
        root.update_idletasks()
        root.update()


def _mesh_bounds(triangles):
    points = [
        tuple(float(v) for v in point)
        for triangle in tuple(triangles or ())
        for point in tuple(triangle or ())
    ]
    if not points:
        return None
    axes = tuple(zip(*points))
    return tuple(
        (round(min(axis), 6), round(max(axis), 6))
        for axis in axes
    )


def test_vault_to_receiving_assembly_switch_has_one_authoritative_visible_render():
    import tkinter as tk
    import gui

    root = tk.Tk()
    root.geometry("1400x900+0+0")
    app = gui.Phase6PrimaryApplication(root)
    designer = app.fold_designer_app
    assert designer is not None

    try:
        try:
            designer.root.deiconify()
            designer.root.geometry("1400x900+0+0")
        except Exception:
            pass
        _pump(root, 6)

        designer.baseline_model_var.set("金庫型")
        _pump(root, 8)
        assert designer._phase6_3d_display_mode == "assembly"

        scene = designer.final_scene_view
        assert scene is not None
        real_render = scene.render
        events = []

        def traced_render(request):
            before = {
                "model": str(designer._phase6_input_snapshot.get("model") or ""),
                "display_mode": str(designer._phase6_3d_display_mode or ""),
                "active_part": str(designer.designer_workspace.active_part or ""),
                "available_parts": tuple(
                    str(key) for key in designer.designer_workspace.available_parts
                ),
                "request_parts": tuple(
                    str(getattr(part, "part_key", "") or "")
                    for part in tuple(
                        getattr(getattr(request, "render_data", None), "assembly_parts", ())
                        or ()
                    )
                ),
            }
            result = real_render(request)
            before["mesh_bounds"] = _mesh_bounds(scene.last_cutting_mesh)
            events.append(before)
            return result

        scene.render = traced_render
        scheduler = getattr(designer, "_phase6_update_scheduler", None)
        metrics_before = (
            scheduler.metrics_snapshot()
            if scheduler is not None and hasattr(scheduler, "metrics_snapshot")
            else {}
        )

        designer.baseline_model_var.set("受電箱")
        _pump(root, 12)

        scheduler = getattr(designer, "_phase6_update_scheduler", None)
        metrics_after = (
            scheduler.metrics_snapshot()
            if scheduler is not None and hasattr(scheduler, "metrics_snapshot")
            else {}
        )
        payload = {
            "events": events,
            "metrics_before": metrics_before,
            "metrics_after": metrics_after,
            "final_model": str(designer._phase6_input_snapshot.get("model") or ""),
            "final_display_mode": str(designer._phase6_3d_display_mode or ""),
            "final_available_parts": tuple(
                str(key) for key in designer.designer_workspace.available_parts
            ),
        }
        print("ISSUE609_FAMILY_SWITCH_RENDER_TRACE=" + json.dumps(
            payload, ensure_ascii=False, sort_keys=True
        ))

        expected_children = {
            "box_body:left_side",
            "box_body:back",
            "box_body:right_side",
        }
        assert payload["final_model"] == "受電箱"
        assert payload["final_display_mode"] == "assembly"
        assert expected_children <= set(payload["final_available_parts"])

        assert len(events) == 1, (
            "Vault→Receiving assembly switch must expose exactly one FinalScene render; "
            f"trace={payload!r}"
        )
        only = events[0]
        assert only["model"] == "受電箱", payload
        assert only["display_mode"] == "assembly", payload
        assert expected_children <= set(only["available_parts"]), payload
        assert only["mesh_bounds"] is not None, payload
    finally:
        try:
            if designer is not None:
                designer.root.destroy()
        except Exception:
            pass
        try:
            root.destroy()
        except tk.TclError:
            pass
