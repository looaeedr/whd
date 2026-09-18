"""Application orchestration for authoritative 2D render snapshots.

This module does not define manufacturing/part-spec authority.  It coordinates
host-owned state and host-owned T7 authority into immutable presentation payloads
consumed by gui_modules.rendering.
"""

import ae_engine.ae as ae
from ae_engine import manufacturing_api
import ae_engine.assembly_placement as assembly_placement
from ae_engine.cabinet_types import policy as cabinet_family_policy
from ae_engine.corner_type_ui import is_unknown_model
import ae_engine.door_dividers as door_dividers
import ae_engine.inner_door_frames as inner_door_frames
from ae_engine.sheetmetal_features import (
    DoorIndicatorContext,
    box_body_face_dimensions,
    measure_door_indicator_position,
    resolve_door_indicator_dimension_guides,
    resolve_door_indicator_layout,
)
from ae_engine.sheetmetal_geometry import Vec2


def indicator_box_render_snapshot(host, val):
    count = max(1, int(host.indicator_l_var.get()))
    layer_groups = tuple(int(host.indicator_layer_g_vars[i].get()) for i in range(count))
    spec = host._indicator_box_part_spec(
        val, layer_groups, features=host.surface_features["indicator_box"]
    )
    context = host._manufacturing_context(draw_stock=False)
    render_data = host._authoritative_render_data(spec, context)
    bounds = tuple(float(v) for v in render_data.material.bounds)
    return {
        "render_data": render_data,
        "bounds": bounds,
        "layer_groups": layer_groups,
        "baseline_label": ae.indicator_shared_baseline_source_label("盒子.dxf"),
    }


def indicator_door_render_snapshot(host, val):
    count = max(1, int(host.indicator_l_var.get()))
    layer_groups = tuple(int(host.indicator_layer_g_vars[i].get()) for i in range(count))
    spec, context = host._indicator_door_part_spec_from_values(
        val, layer_groups, features=host.surface_features["indicator_door"]
    )
    render_data = host._authoritative_render_data(spec, context)
    bounds = tuple(float(v) for v in render_data.material.bounds)
    finished_size = manufacturing_api.door_finished_face_size(spec, context)
    return {
        "render_data": render_data,
        "bounds": bounds,
        "finished_size": tuple(float(v) for v in finished_size),
    }


def door_layout_overview_snapshot(host, render_data_by_part_key=None):
    try:
        total_w = float(host.w_var.get())
        total_h = float(host.h_var.get())
        columns = host.get_door_layout_columns()
        cells = host.get_door_layout_cells()
        val = host.get_float_values()
    except Exception as exc:
        return {"error": exc}

    cell_payloads = {}
    for cell in cells:
        column_index = int(cell.column_index)
        row_index = int(cell.row_index)
        key = f"{column_index}:{row_index}"
        if render_data_by_part_key is None:
            result = host._door_layout_cell_result(cell, val)
            baseline_scene, _baseline_status = host._door_layout_baseline_scene(cell, val)
            resolved = host._door_layout_cell_resolved_features(cell, result, key)
            cell_payloads[(column_index, row_index)] = {
                "mode": "local",
                "scene": baseline_scene,
                "resolved": resolved,
                "width": float(result.width),
                "height": float(result.height),
            }
        else:
            stable_key = f"door_c{column_index + 1}_r{row_index + 1}"
            peer_render_data = render_data_by_part_key.get(stable_key)
            material = getattr(peer_render_data, "material", None)
            scene = getattr(peer_render_data, "scene", None)
            if (
                material is not None
                and scene is not None
                and not bool(getattr(material, "is_empty", False))
            ):
                minx, miny, maxx, maxy = (float(v) for v in material.bounds)
                cell_payloads[(column_index, row_index)] = {
                    "mode": "peer",
                    "scene": scene,
                    "width": max(maxx - minx, 1e-9),
                    "height": max(maxy - miny, 1e-9),
                }
            else:
                cell_payloads[(column_index, row_index)] = {"mode": "none"}

    baseline_model = host._baseline_source_model() or ""
    return {
        "error": None,
        "total_w": total_w,
        "total_h": total_h,
        "columns": columns,
        "cells": cells,
        "val": val,
        "selected_key": host.door_layout_selected_var.get(),
        "cell_payloads": cell_payloads,
        "baseline_status": ae.baseline_source_label(baseline_model, "門.dxf"),
    }


def door_layout_divider_frame_snapshot(host, columns, val):
    t_val = float(val.get("t", 2.0))
    project_snapshot = host._compose_phase6_project_snapshot_from_main_gui()
    total_w = float(project_snapshot.get("w", val.get("w", 0.0)))
    total_h = float(project_snapshot.get("h", val.get("h", 0.0)))
    divider_payloads = []
    frame_payloads = []

    try:
        normalized = tuple(
            (float(c[0]), tuple(float(h) for h in c[1])) for c in columns
        )
        dividers = door_dividers.derive_box_body_dividers(
            normalized,
            depth=float(val.get("d", 350.0)),
            thickness=t_val,
            layout_scope=getattr(host, "door_layout_scope", "main"),
            handle_edges=getattr(host, "door_layout_handle_edges", {}),
        )
        for div in dividers:
            placement = assembly_placement.resolve_assembly_placement(project_snapshot, div.stable_id)
            divider_payloads.append({
                "axis": str(div.axis),
                "span": float(div.span),
                "formed_core_depth": float(div.formed_core_depth),
                "world_offset": tuple(float(v) for v in placement.world_offset),
            })
    except Exception:
        pass

    try:
        if cabinet_family_policy.has_inner_door_frame_derivation(project_snapshot):
            frame_sets = cabinet_family_policy.derive_inner_door_frame_sets(project_snapshot)
            for fset in frame_sets:
                for side in tuple(fset.included_sides):
                    if side not in {"top", "left", "right"}:
                        continue
                    stable_id = inner_door_frames.inner_door_frame_stable_id(fset.inner_door_id, side)
                    placement = assembly_placement.resolve_assembly_placement(project_snapshot, stable_id)
                    frame_payloads.append({
                        "side": str(side),
                        "span": float(fset.spans[side]),
                        "world_offset": tuple(float(v) for v in placement.world_offset),
                    })
    except Exception:
        pass

    return {
        "total_w": total_w,
        "total_h": total_h,
        "dividers": tuple(divider_payloads),
        "frames": tuple(frame_payloads),
    }


def single_door_render_snapshot(host):
    door_val = {
        "w": float(host.w_var.get()),
        "h": float(host.h_var.get()),
        "t": float(host.t_var.get()),
        "fw": float(host.fw_z_var.get()),
        "door_gap_w": float(host.door_gap_w_var.get()),
        "door_gap_h": float(host.door_gap_h_var.get()),
        "door_fold_l": float(host.door_fold_l_var.get()),
        "door_fold_r": float(host.door_fold_r_var.get()),
        "door_fold_t": float(host.door_fold_t_var.get()),
        "door_fold_b": float(host.door_fold_b_var.get()),
    }

    indicator_hole = None
    if host.is_indicator_box_var.get():
        try:
            count = max(1, int(host.indicator_l_var.get()))
            groups = tuple(int(host.indicator_layer_g_vars[i].get()) for i in range(count))
            indicator_hole = manufacturing_api.indicator_box_opening_size(
                groups, thickness=door_val["t"]
            )
        except Exception:
            indicator_hole = None

    door_indicator = None
    if host.is_door_indicator_var.get():
        try:
            count = max(1, int(host.door_indicator_l_var.get()))
            door_indicator = tuple(
                int(host.door_indicator_layer_g_vars[i].get()) for i in range(count)
            )
        except Exception:
            door_indicator = None

    spec = host._single_door_part_spec(
        door_val, indicator_hole=indicator_hole, door_indicator=door_indicator
    )
    render_context = host._manufacturing_context(draw_stock=False)
    render_data = host._authoritative_render_data(spec, render_context)
    bounds = tuple(float(v) for v in render_data.material.bounds)
    minx, miny, maxx, maxy = bounds
    if maxx - minx <= 0 or maxy - miny <= 0:
        raise ValueError("門板 Final Part Geometry 尺寸無效")

    finished_context = host._manufacturing_context(draw_stock=False)
    finished_size = tuple(
        float(v) for v in manufacturing_api.door_finished_face_size(spec, finished_context)
    )

    indicator_context = None
    indicator_layout = None
    x_guide = None
    y_guide = None
    indicator_groups = tuple(door_indicator or ())
    if indicator_groups:
        try:
            finished_w, finished_h = finished_size
            indicator_context = DoorIndicatorContext(
                finished_width=finished_w,
                finished_height=finished_h,
                left_fold=door_val["door_fold_l"],
                bottom_fold=door_val["door_fold_b"],
            )
            indicator_layout = resolve_door_indicator_layout(
                indicator_context,
                indicator_groups,
                Vec2(host.door_indicator_offset_x, host.door_indicator_offset_y),
            )
            position = measure_door_indicator_position(
                indicator_layout,
                indicator_context,
                frame_width=door_val["fw"],
                thickness=door_val["t"],
                use_box_distance=spec.use_box_distance,
                frame_edges=spec.frame_edges,
                gap_w=door_val["door_gap_w"],
                gap_h=door_val["door_gap_h"],
            )
            x_guide, y_guide = resolve_door_indicator_dimension_guides(position)
        except Exception:
            indicator_context = None
            indicator_layout = None
            x_guide = None
            y_guide = None

    return {
        "render_data": render_data,
        "bounds": bounds,
        "finished_size": finished_size,
        "door_val": door_val,
        "model_name": spec.model_name,
        "frame_edges": spec.frame_edges,
        "indicator_context": indicator_context,
        "indicator_groups": indicator_groups,
        "indicator_layout": indicator_layout,
        "x_guide": x_guide,
        "y_guide": y_guide,
    }


def base_plate_render_snapshot(host, val):
    shrink_top = float(host.base_plate_shrink_top_var.get())
    shrink_bottom = float(host.base_plate_shrink_bottom_var.get())
    shrink_left = float(host.base_plate_shrink_left_var.get())
    shrink_right = float(host.base_plate_shrink_right_var.get())
    bend = float(host.base_plate_bend_var.get())
    spec_val = dict(val)
    spec_val.update({
        "base_plate_shrink_top": shrink_top,
        "base_plate_shrink_bottom": shrink_bottom,
        "base_plate_shrink_left": shrink_left,
        "base_plate_shrink_right": shrink_right,
        "base_plate_bend": bend,
    })
    spec = host._base_plate_part_spec(spec_val)
    context = host._manufacturing_context(draw_stock=False)
    render_data = host._authoritative_render_data(spec, context)
    bounds = tuple(float(v) for v in render_data.material.bounds)
    minx, miny, maxx, maxy = bounds
    box_l = -(shrink_left - bend)
    box_b = -(shrink_bottom - bend)
    world_bounds = (
        min(minx, box_l),
        min(miny, box_b),
        max(maxx, box_l + val["w"]),
        max(maxy, box_b + val["h"]),
    )
    return {
        "render_data": render_data,
        "bounds": bounds,
        "world_bounds": tuple(float(v) for v in world_bounds),
        "box_rect": (float(box_l), float(box_b), float(val["w"]), float(val["h"])),
        "bend": float(bend),
    }


def box_body_render_snapshot(host, val, *, face_dimensions_fn=box_body_face_dimensions):
    spec = host._box_body_part_spec(val)
    render_data = host._authoritative_render_data(
        spec, host._manufacturing_context(draw_stock=False)
    )
    selected_piece_key = host._refresh_box_body_piece_tabs_2d(render_data)
    if selected_piece_key:
        selected_role = selected_piece_key.split(":", 1)[1]
        selected_piece = next(
            (
                piece
                for piece in tuple(getattr(render_data, "pieces", ()) or ())
                if str(getattr(piece, "role", "") or "") == selected_role
            ),
            None,
        )
        if selected_piece is not None:
            return {
                "mode": "piece",
                "render_data": render_data,
                "piece": selected_piece,
                "piece_key": selected_piece_key,
            }

    bounds = tuple(float(v) for v in render_data.material.bounds)
    contexts = getattr(render_data, "box_body_face_contexts", None)
    if not contexts:
        raise ValueError("authoritative Box Body face contexts unavailable")
    baseline = host._baseline_source_model()
    return {
        "mode": "aggregate",
        "render_data": render_data,
        "bounds": bounds,
        "contexts": contexts,
        "selected_face": host.box_body_face_selected_var.get(),
        "baseline_status": ae.box_body_baseline_source_label(baseline),
        "dimensions": face_dimensions_fn(
            w=val["w"], h=val["h"], d=val["d"]
        ),
        "piece_keys": tuple(
            f"box_body:{str(piece.role)}"
            for piece in tuple(getattr(render_data, "pieces", ()) or ())
        ),
    }


def end_cap_render_snapshot(host, val, *, part_label="封頭/尾", is_tail=False):
    baseline = host._baseline_source_model()
    spec = host._end_cap_part_spec(val, is_tail=is_tail)
    context = host._manufacturing_context(draw_stock=False)
    render_data = host._authoritative_render_data(spec, context)
    bounds = tuple(float(v) for v in render_data.material.bounds)
    if is_unknown_model(host.baseline_var.get()):
        baseline_hint = " (自訂 / Final Part Geometry)"
    elif baseline:
        baseline_hint = f" ({baseline} Final Part Geometry)"
    else:
        baseline_hint = " (Y-Cap Final Part Geometry)"
    return {
        "render_data": render_data,
        "bounds": bounds,
        "baseline_hint": baseline_hint,
        "part_label": part_label,
        "is_tail": bool(is_tail),
    }
