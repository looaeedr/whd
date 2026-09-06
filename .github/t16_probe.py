from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def bounds(triangles):
    points = [point for tri in triangles or () for point in tri[:3]]
    if not points:
        return None
    return tuple((min(p[i] for p in points), max(p[i] for p in points)) for i in range(3))


import tkinter as tk
import gui
import fold_designer_bridge as bridge
from ae_engine.assembly_placement import resolve_assembly_placement

root = tk.Tk(); root.withdraw()
app = gui.BoxCalculatorGUI(root)
designer = None
try:
    app.baseline_var.set("受電箱")
    root.update_idletasks(); root.update()
    designer = app.open_original_fold_designer()
    root.update_idletasks(); root.update()
    resolved = bridge._phase6_resolve_manufacturing_geometry(designer)
    dims = bridge._phase6_operator_finished_dimensions(designer)
    world = bridge._phase6_build_joint_world_geometry(resolved.parts, dims, 2.0)
    print("DIMS", dims)
    print("PARTS", [part.part_key for part in resolved.parts])
    for key in sorted(world["world_triangles_by_part"]):
        if key.startswith("box_body") or key.startswith("door_") or key.startswith("inner_door:"):
            print("WORLD_BOUNDS", key, bounds(world["world_triangles_by_part"][key]))
    for key in [
        "door_c1_r1",
        "door_c1_r2",
        "box_body:divider:receiving-main:HORIZONTAL:C0_R0|R1",
        "inner_door:upper:top_frame",
        "inner_door:upper:left_frame",
        "inner_door:upper:right_frame",
    ]:
        try:
            p = resolve_assembly_placement(designer._phase6_input_snapshot, key)
            print("PLACEMENT", key, p.to_dict())
        except Exception as exc:
            print("PLACEMENT_ERROR", key, type(exc).__name__, str(exc))
    for part in resolved.parts:
        if part.part_key.startswith("door_") or part.part_key.startswith("inner_door:") or part.part_key.startswith("box_body:divider:"):
            print("SCENE_PART", part.part_key, part.placement, part.offset)
finally:
    try:
        if designer is not None:
            designer.root.destroy()
    except Exception:
        pass
    try:
        root.destroy()
    except Exception:
        pass
