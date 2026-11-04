# -*- coding: utf-8 -*-
"""Engine-owned Receiving operator projection and Family capability.

These are read-only projections of the existing canonical Receiving defaults,
Family registry and BoxBody topology.  They do not grant manufacturing export.
"""
from __future__ import annotations

from math import isfinite

from .box_body_structure_state import BoxBodyStructureType
from .cabinet_types.policy import canonical_family_name
from .cabinet_types.receiving import BOX_BODY_DEFAULTS


def receiving_default_box_dimensions() -> dict[str, int]:
    """Fresh W/H/D operator values from Receiving Family, never a shared dict."""
    return {axis: int(BOX_BODY_DEFAULTS[axis]) for axis in ("w", "h", "d")}


def receiving_default_preview_dimensions(snapshot) -> tuple[float, float, float]:
    """Read-only active mode dimensions for the Receiving settings preview."""
    data = dict(snapshot or {})
    if data.get("active_mode") == "quantity":
        box = data.get("receiving_quantity_box") or BOX_BODY_DEFAULTS
    else:
        sets = (data.get("receiving_layout") or {}).get("sets") or ()
        bays = sets[0].get("bays") or () if sets else ()
        box = ({"w": bays[0]["width"], "h": bays[0]["height"],
                "d": bays[0]["depth"]} if bays else BOX_BODY_DEFAULTS)
    return tuple(float(box[axis]) for axis in ("w", "h", "d"))



def project_receiving_operator_bay_door_split_ratio(bay) -> float | None:
    """Read-only two-row Bay seam for the lightweight operator sketch.

    The drawn line must use the saved canonical Door topology, not a GUI
    1100-mm fabrication guess. A Family-default schematic uses the actual
    Receiving default ratio even when an operator changes Bay H. Complex
    Door grids cannot be represented by a *single* horizontal seam, so the
    caller must omit the fake line instead of fabricating two Door faces.
    This is display provenance only; never manufacture from this ratio.
    """
    from collections.abc import Mapping
    from .cabinet_types.receiving import default_door_layout_columns
    from .sheetmetal_part_adapters import (
        _finite_float, validate_door_layout_dimensions,
    )

    default = default_door_layout_columns()[0][1]
    default_ratio = float(default[0]) / sum(float(h) for h in default)
    if bay is None:
        return default_ratio
    if not isinstance(bay, Mapping):
        raise ValueError("Receiving Bay preview source must be a mapping")
    width = _finite_float(bay.get("width"), "Receiving Bay width")
    height = _finite_float(bay.get("height"), "Receiving Bay height")
    if width <= 0 or height <= 0:
        raise ValueError("Receiving Bay preview dimensions must be positive")
    state = bay.get("door_state")
    if state is None:
        return default_ratio
    if not isinstance(state, Mapping):
        raise ValueError("Receiving Bay Door source must be a mapping")
    if "multi_door_enabled" not in state:
        # Migrated legacy projects may have a saved root Door column list but
        # no saved enable decision. Validate that list if present, yet draw
        # only the unconfirmed Family schematic: it is not active topology.
        legacy_columns = state.get("door_layout_columns")
        if legacy_columns:
            validate_door_layout_dimensions(
                legacy_columns, total_width=width, total_height=height,
            )
        return default_ratio
    enabled = state["multi_door_enabled"]
    if type(enabled) is not bool:
        raise ValueError("Receiving Bay Door enable source must be boolean")
    if not enabled:
        return None
    columns = state.get("door_layout_columns") or ()
    if not columns:
        raise ValueError("Receiving Bay enabled Door topology lacks columns")
    cells = validate_door_layout_dimensions(
        columns, total_width=width, total_height=height,
    )
    first_rows = [cell.start_height for cell in cells if cell.row_index == 0]
    second_rows = [cell for cell in cells if cell.row_index == 1]
    if len(first_rows) != len(columns) or len(second_rows) != len(columns):
        return None
    if len(cells) != 2 * len(columns):
        return None
    if any(abs(row - first_rows[0]) > 1e-6 for row in first_rows[1:]):
        return None
    return float(first_rows[0]) / height


def receiving_family_supports_back_panel_mode(snapshot) -> bool:
    """Use the registered Family identity, never GUI string matching."""
    return canonical_family_name(snapshot) == "受電箱"


def receiving_back_panel_mode_control_applicable(snapshot, structure_state) -> bool:
    """Only Receiving's physical three-piece side/back split exposes this mode."""
    return (
        receiving_family_supports_back_panel_mode(snapshot)
        and str((structure_state or {}).get("active_type") or "")
        == BoxBodyStructureType.THREE_PIECE_SIDE_BACK_SPLIT.value
    )


def project_receiving_original_door_marks(scene):
    """Project only identified original Door nameplate holes and handle contour.

    No fallback coordinates: when the original baseline does not identify the
    features unambiguously, the lightweight sketch draws none.
    Normalized vectors are presentation-only, never manufacturing geometry.
    """
    from .sheetmetal_drawing import CirclePrimitive, PolylinePrimitive

    empty = {"nameplate": (), "handle": ()}
    if scene is None:
        return empty
    outlines = [
        p for p in scene.primitives
        if isinstance(p, PolylinePrimitive) and p.layer == "CUTTING"
        and p.closed and len(p.points) >= 3
    ]
    if not outlines:
        return empty

    def bounds(polyline):
        xs = [float(pt.x) for pt in polyline.points]
        ys = [float(pt.y) for pt in polyline.points]
        return min(xs), min(ys), max(xs), max(ys)

    outer = max(outlines, key=lambda item:
                (bounds(item)[2] - bounds(item)[0]) *
                (bounds(item)[3] - bounds(item)[1]))
    x0, y0, x1, y1 = bounds(outer)
    if x1 <= x0 or y1 <= y0:
        return empty

    def xy(point):
        return ((float(point.x) - x0) / (x1 - x0),
                1.0 - (float(point.y) - y0) / (y1 - y0))

    # Only the stable feature identity from the original Door baseline
    # identifies nameplate circles; do not guess from radius or position.
    nameplate = tuple(
        (*xy(p.center), float(p.radius) / (x1 - x0),
         float(p.radius) / (y1 - y0))
        for p in scene.primitives
        if isinstance(p, CirclePrimitive)
        and p.layer == "CUTTING" and p.source_type == "nameplate_mount"
    )
    # The certified Door baseline has exactly one extra interior CUTTING
    # contour for the handle. Multiple candidates are ambiguous: draw none.
    interior = [
        p for p in outlines if p is not outer
        and bounds(p)[0] > x0 and bounds(p)[1] > y0
        and bounds(p)[2] < x1 and bounds(p)[3] < y1
    ]
    handle = tuple(xy(pt) for pt in interior[0].points) if len(interior) == 1 else ()
    return {"nameplate": nameplate, "handle": handle}



def project_receiving_operator_door_cell_sources(
    snapshot, *, set_index: int, bay_index: int,
):
    """Select the one original two-face Receiving Bay Door source via Engine.

    This preserves current Bay legacy projection and strict physical topology
    selection. Unsupported sketches are absent, never replaced by fabricated
    cells. The caller may render each corresponding baseline scene.
    """
    from .receiving_layout import project_receiving_bay_legacy_aliases
    from .sheetmetal_part_adapters import derive_door_layout_cells

    projected = project_receiving_bay_legacy_aliases(
        snapshot, set_index=set_index, bay_index=bay_index,
    )
    columns = projected.get("door_layout_columns") or ()
    if not projected.get("multi_door_enabled") or not columns:
        return None
    cells = derive_door_layout_cells(columns)
    if len(cells) != 2 or any(cell.column_index != 0 for cell in cells):
        return None
    return projected, tuple(sorted(cells, key=lambda item: item.row_index))


def project_receiving_initial_door_source_scenes(snapshot, resolved):
    """Read exactly the original pair of Door scenes from committed Receiving.

    Return source scene objects only, not new geometry or a manufacturing grant.
    Identity and order derive from canonical Door part keys.
    """
    if canonical_family_name(snapshot) != "受電箱":
        return ()
    parts = {
        str(part.part_key): getattr(part.render_data, "scene", None)
        for part in tuple(getattr(resolved, "parts", ()) or ())
        if str(getattr(part, "part_key", "") or "") in {
            "door_c1_r1", "door_c1_r2",
        }
    }
    if any(parts.get(key) is None for key in ("door_c1_r1", "door_c1_r2")):
        return ()
    return (parts["door_c1_r1"], parts["door_c1_r2"])



def project_receiving_nfb_work_area_height_mm(snapshot) -> float:
    """Project the existing NFB editor's actual Door work area, never a new Y.

    A single top Door cell owns the preview height; for other layouts the
    existing whole-box H fallback is preserved. Invalid dimensions fail
    closed rather than authorizing a synthetic millimetre length.
    """
    from .sheetmetal_part_adapters import derive_door_layout_cells

    source = dict(snapshot or {})
    columns = source.get("door_layout_columns") or ()
    cells = derive_door_layout_cells(columns) if columns else ()
    upper = [cell for cell in cells if cell.row_index == 0]
    raw = (upper[0].start_height if len(upper) == 1
           else source.get("h", 0.0))
    if isinstance(raw, bool):
        raise ValueError("內門作業區高度未定")
    try:
        height = float(raw)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("內門作業區高度未定") from exc
    if not isfinite(height) or height <= 0:
        raise ValueError("內門作業區高度未定")
    return height


def validate_receiving_nfb_layer_heights_for_work_area(
    snapshot, heights, *, layer_count: int,
) -> list[float]:
    """Use the same Engine source for saved tier validation and preview.

    This validates an editor input only. It does not approve a nominal Y,
    physical NFB source, cutting hole, or manufacturing release.
    """
    from .receiving_shared_settings import validate_setting

    checked = validate_setting("inner_door_layer_heights_mm", heights)
    count = validate_setting("inner_door_layers", layer_count)
    height = project_receiving_nfb_work_area_height_mm(snapshot)
    if checked[count - 1] >= height:
        raise ValueError("層高必須在目前內門作業區內，且第一層須在第二層上方")
    return checked


def operator_base_plate_edge_shrink_editable(snapshot) -> bool:
    """Source-derived Receiving BasePlate never exposes free shrink editing."""
    return not receiving_family_supports_back_panel_mode(snapshot)


def project_operator_receiving_base_plate_snapshot_source(snapshot, persisted):
    """Detach the saved explicit Receiving BasePlate source for GUI snapshots.

    Family routing comes from the same registered physical owner as Settings
    and manufacturing. A missing source stays missing, and an explicit reset
    stays None; source-flat geometry / NFB patterns are never inferred here.
    """
    from collections.abc import Mapping
    from copy import deepcopy

    if not receiving_family_supports_back_panel_mode(snapshot):
        return {}
    if not isinstance(persisted, Mapping):
        raise ValueError("RECEIVING_BASE_PLATE_SNAPSHOT_SOURCE_INVALID")
    if "receiving_base_plate" not in persisted:
        return {}
    config = persisted["receiving_base_plate"]
    if config is not None and not isinstance(config, Mapping):
        raise ValueError("RECEIVING_BASE_PLATE_SNAPSHOT_SOURCE_INVALID")
    return {"receiving_base_plate": deepcopy(config)}


def project_operator_receiving_base_plate_settings(snapshot, *, context="base_plate"):
    """Read-only BasePlate settings from the SAME physical Family source as MFG.

    A stale/unresolved NFB source reports its error; it cannot be converted
    into a GUI-local guessed bend variant or a manufacturing approval.
    """
    if str(context) != "base_plate" or not receiving_family_supports_back_panel_mode(snapshot):
        return None
    from copy import deepcopy
    from .receiving_base_plate_config import receiving_base_plate_values

    source = dict(snapshot or {})
    stored = source.get("receiving_base_plate")
    derived = None
    error = ""
    if stored is None:
        try:
            resolved = receiving_base_plate_values(source)
        except (ValueError, TypeError, KeyError) as exc:
            error = str(exc)
        else:
            if resolved is not None:
                derived = {
                    "pattern": resolved["receiving_bend_pattern"],
                    "height": resolved["h"],
                    "shrink_top": resolved["base_plate_shrink_top"],
                    "shrink_bottom": resolved["base_plate_shrink_bottom"],
                    "shrink_left": resolved["base_plate_shrink_left"],
                    "shrink_right": resolved["base_plate_shrink_right"],
                    "bend": resolved["base_plate_bend"],
                }
    return {
        "configured": stored is not None or derived is not None,
        "values": deepcopy(stored or derived or {}),
        "source_derived": derived is not None,
        "source_error": error,
    }


def project_operator_receiving_base_plate_reload(saved_snapshot, effective_snapshot):
    """Plan physical BasePlate restore and post-load navigation from source.

    Read-only plan: no saved project mutation and no inferred part identity.
    Even a submitted NFB flag cannot create an unproven physical BasePlate.
    """
    from copy import deepcopy
    from .receiving_base_plate_config import receiving_base_plate_values

    saved = dict(saved_snapshot or {})
    effective = dict(effective_snapshot or {})
    receiving = receiving_family_supports_back_panel_mode(saved)
    restore = receiving and "receiving_base_plate" in saved
    stored = deepcopy(saved.get("receiving_base_plate")) if restore else None
    if restore:
        effective["receiving_base_plate"] = deepcopy(stored)
    should_refresh = False
    if (receiving and receiving_family_supports_back_panel_mode(effective)
            and effective.get("nfb_config_submitted") is True):
        try:
            should_refresh = receiving_base_plate_values(effective) is not None
        except (ValueError, TypeError, KeyError):
            should_refresh = False
    return {
        "restore": restore,
        "saved_base_plate": stored,
        "refresh_derived_navigation": should_refresh,
    }
