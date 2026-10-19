"""Receiving-family physical Base Plate configuration adapter.

Only the EXISTING BasePlatePartSpec is manufactured. These values select an
explicit physical plate variant; source DXF layout is not a placement datum.
Unconfigured legacy projects remain previewable, not production-authorized.
"""
from __future__ import annotations

from collections.abc import Mapping
from math import isfinite

from .sheetmetal_part_adapters import (
    RECEIVING_BASE_PATTERNS, build_receiving_base_plate_result,
)

RECEIVING_FAMILIES = frozenset(("受電箱", "RECEIVING"))
_REQUIRED = (
    "pattern", "height", "shrink_top", "shrink_bottom",
    "shrink_left", "shrink_right", "bend",
)


def _source_center_base_config(data):
    """Resolve only the uniquely identified two-depth CENTER source blank.

    The reference 受電箱底板(5).dxf contains CENTER CUTTING 772 x 240 at
    W800/T2, side BENDING 40/73/699/732 and EAR slots 20 from blank edges.
    That source is a physical shape reference, NOT an absolute installation
    datum or a rule that all Receiving bays have a center pattern. A
    submitted same-row two-depth NFB config uniquely requires the center
    double-side fold; other arrangements remain explicitly unresolved.
    """
    from .receiving_nfb_depth_surface_policy import committed_receiving_nfb_depth_pair_mm
    from .receiving_weld_ear_policy import (
        LARGE_EAR_EDGE_TO_HOLE_CENTER_MM,
        LARGE_EAR_SOURCE_BEND_MM,
        LARGE_EAR_MATERIAL_THICKNESS_MM,
    )
    from .sheetmetal_part_adapters import RECEIVING_BASE_PATTERN_CENTER

    pair = committed_receiving_nfb_depth_pair_mm(data)
    if pair is None:
        return None
    t = float(data["t"])
    if abs(t - 2.0) > 1e-6:
        # The actual CENTER folded source is certified only for T2.
        raise ValueError("RECEIVING_CENTER_SOURCE_REQUIRES_T2")
    inside_offset = (
        LARGE_EAR_EDGE_TO_HOLE_CENTER_MM
        - LARGE_EAR_SOURCE_BEND_MM
        + LARGE_EAR_MATERIAL_THICKNESS_MM
    )  # actual T2 fixing plate: 84 - 23 + 2 = 63
    # CENTER physical face width: installed fixing-hole pitch minus two
    # original-source 20-mm offsets. The 40-mm first side fold spans from
    # blank edge to first BEND. Never copy W800's 670/772 into other widths.
    from .receiving_weld_ear_policy import receiving_source_fixing_pitch_x_mm
    box_w = float(data["w"])
    pitch_x = receiving_source_fixing_pitch_x_mm(
        box_outer_width_mm=box_w, box_side_thickness_mm=t,
    )
    flat_source_slot_inset = 20.0  # both measured source blank EAR columns
    first_side_fold = 40.0  # CENTER source's first side BEND
    face_width = pitch_x - 2.0 * flat_source_slot_inset
    side_shrink = (box_w - face_width) / 2.0
    if (face_width <= 0
            or abs(side_shrink - (t + inside_offset
                                  + flat_source_slot_inset)) > 1e-6):
        raise ValueError("RECEIVING_CENTER_SOURCE_FIXING_DATUM_CONFLICT")
    # Source CENTER unfolds to H240 with upper/lower 20-mm folds; physical
    # nominal height is therefore 280. An NFB tier's Y is *placement*, not
    # this height. Actual NFB screw envelopes must still pass their own
    # per-part work-face containment checks downstream.
    return {
        "pattern": RECEIVING_BASE_PATTERN_CENTER,
        "height": 240.0 + 2.0 * 20.0,
        "shrink_top": 20.0,
        "shrink_bottom": 20.0,
        "shrink_left": side_shrink,
        "shrink_right": side_shrink,
        "bend": 20.0,
    }


def _source_left_flat_base_config(data):
    """Match real LEFT source NFB screw geometry, never guess a flat variant.

    受電箱底板(5).dxf LEFT contains 710x300 CUTTING at W800/T2,
    two 44x194 groups of 5.1-mm NFB screws, source EAR columns 20 mm
    from its outer edges, and upper/lower 20-mm BEND. The RIGHT sheet
    contains different hole groups and H320; no model-depth-only choice.
    """
    from .receiving_nfb_depth_surface_policy import committed_receiving_flat_nfb_depth_mm
    from .receiving_nfb_model_identity import parse_numeric_model_ref
    from .receiving_nfb_numeric_catalog import model_spec
    from .receiving_weld_ear_policy import receiving_source_fixing_pitch_x_mm
    from .sheetmetal_part_adapters import RECEIVING_BASE_PATTERN_LEFT

    # A two-tier source is handled by independent tier parts, never by
    # guessing that both tiers share a single LEFT/RIGHT root Base Plate.
    active = data.get("nfb_config")
    if isinstance(active, Mapping) and active.get("layer_count") != 1:
        return None
    try:
        depth = committed_receiving_flat_nfb_depth_mm(data)
    except ValueError as exc:
        if str(exc) == "RECEIVING_FLAT_NFB_MULTIPLE_ROWS_NEED_DISTINCT_BASE":
            return None
        raise
    if depth is None:
        return None
    # The live Bay/Set identity is already verified by the flat depth
    # resolver; now require a single fully matching physical NFB model.
    config = data.get("nfb_config")
    if not isinstance(config, Mapping):
        layout = data.get("receiving_layout")
        sets = layout.get("sets") if isinstance(layout, Mapping) else None
        if isinstance(sets, (tuple, list)) and len(sets) == 1:
            bays = sets[0].get("bays") if isinstance(sets[0], Mapping) else None
            if isinstance(bays, (tuple, list)) and len(bays) == 1:
                config = bays[0].get("nfb_config")
    holes = config.get("holes") if isinstance(config, Mapping) else None
    if not isinstance(holes, (tuple, list)) or not holes:
        return None
    models = {str(h.get("model_filename") or "") for h in holes
              if isinstance(h, Mapping)}
    if len(models) != 1:
        return None
    resolved = parse_numeric_model_ref(next(iter(models)))
    if resolved is None:
        return None
    spec = model_spec(*resolved)
    # Both source LEFT and CSV must agree *exactly*; another model/pitch
    # cannot borrow this illustrated plate simply for matching its depth.
    if (spec is None or spec.screw_pitch_mm != (44.0, 194.0)
            or abs(float(spec.screw_diameter_mm or 0.0) - 5.1) > 1e-6
            or spec.depth_mm is None
            or abs(float(spec.depth_mm) - depth) > 1e-6):
        return None
    t = float(data["t"])
    # Fixed-plate T is the source T2 and independent of the cabinet skin T.
    pitch_x = receiving_source_fixing_pitch_x_mm(
        box_outer_width_mm=float(data["w"]), box_side_thickness_mm=t,
    )
    source_ear_inset = 20.0  # source LEFT CUTTING EAR column to sheet edge
    blank_width = pitch_x + 2.0 * source_ear_inset
    side_shrink = (float(data["w"]) - blank_width) / 2.0
    if blank_width <= 2.0 * source_ear_inset:
        raise ValueError("RECEIVING_LEFT_SOURCE_BLANK_TOO_NARROW")
    return {
        "pattern": RECEIVING_BASE_PATTERN_LEFT,
        "height": 300.0 + 2.0 * 20.0,  # actual LEFT H300 and top/bottom BEND20
        "shrink_top": 20.0,
        "shrink_bottom": 20.0,
        "shrink_left": side_shrink,
        "shrink_right": side_shrink,
        "bend": 20.0,
    }


def receiving_base_plate_values(snapshot):
    """Return existing BasePlatePartSpec input values; never guess a variant.

    The explicit mapping is attached to the Receiving cabinet snapshot, not
    manufactured as a new/derived part. Height is the nominal physical plate
    dimension, NOT the height of the 1100-mm upper door or the full cabinet.
    """
    data = dict(snapshot or {})
    if str(data.get("model") or "").strip() not in RECEIVING_FAMILIES:
        return None
    config = data.get("receiving_base_plate")
    if config is None:
        # Source-backed, *unambiguous* CENTER variant requires no redundant
        # operator-entered dimensions. Never choose LEFT versus RIGHT for a
        # flat tier solely because both happen to pass an envelope check.
        config = _source_center_base_config(data)
        if config is None:
            config = _source_left_flat_base_config(data)
        if config is None:
            return None
    if not isinstance(config, Mapping):
        raise ValueError("RECEIVING_BASE_PLATE_CONFIG_INVALID")
    missing = tuple(key for key in _REQUIRED if key not in config)
    if missing:
        raise ValueError("RECEIVING_BASE_PLATE_CONFIG_INCOMPLETE: " + ",".join(missing))
    pattern = str(config["pattern"] or "").strip()
    if pattern not in RECEIVING_BASE_PATTERNS:
        raise ValueError("RECEIVING_BASE_PLATE_PATTERN_INVALID")
    values = {}
    for key in _REQUIRED[1:]:
        try:
            value = float(config[key])
        except (ValueError, TypeError) as exc:
            raise ValueError("RECEIVING_BASE_PLATE_CONFIG_INVALID: " + key) from exc
        if not isfinite(value):
            raise ValueError("RECEIVING_BASE_PLATE_CONFIG_INVALID: " + key)
        values[key] = value
    if values["height"] <= 0 or values["bend"] <= 0:
        raise ValueError("RECEIVING_BASE_PLATE_CONFIG_INVALID: dimensions")
    values["receiving_bend_pattern"] = pattern
    # #1502: selected source depths come from the CURRENT submitted Bay's
    # NFBConfig and its owning Set brand.  Do NOT persist an independent
    # Base Plate brand/depth. Legacy or unsubmitted previews keep None.
    pair = None
    reference = None
    from .sheetmetal_part_adapters import RECEIVING_BASE_PATTERN_CENTER
    if pattern == RECEIVING_BASE_PATTERN_CENTER:
        from .receiving_nfb_depth_surface_policy import (
            committed_receiving_nfb_depth_pair_mm,
        )
        pair = committed_receiving_nfb_depth_pair_mm(data)
    else:
        # A flat-sided physical mounting face follows ONE exact submitted
        # model depth. A mixed-depth / multi-layer NFB row is NOT silently
        # declared to fit this flat plate; the PAD is separately controlled.
        from .receiving_nfb_depth_surface_policy import (
            committed_receiving_flat_nfb_depth_mm,
        )
        reference = committed_receiving_flat_nfb_depth_mm(data)
    return {
        "receiving_nfb_reference_depth_mm": reference,
        "receiving_nfb_depth_pair_mm": pair,
        "h": values["height"],
        "base_plate_shrink_top": values["shrink_top"],
        "base_plate_shrink_bottom": values["shrink_bottom"],
        "base_plate_shrink_left": values["shrink_left"],
        "base_plate_shrink_right": values["shrink_right"],
        "base_plate_bend": values["bend"],
        "receiving_bend_pattern": pattern,
    }


def receiving_base_plate_blank_dimensions(snapshot):
    """Physical unfolded envelope from ONE canonical structural formula."""
    override = receiving_base_plate_values(snapshot)
    if override is None:
        return None
    data = dict(snapshot or {})
    result = build_receiving_base_plate_result(
        w=float(data["w"]), h=override["h"], t=float(data["t"]),
        shrink_top=override["base_plate_shrink_top"],
        shrink_bottom=override["base_plate_shrink_bottom"],
        shrink_left=override["base_plate_shrink_left"],
        shrink_right=override["base_plate_shrink_right"],
        bend=override["base_plate_bend"],
        pattern=override["receiving_bend_pattern"],
        nfb_depth_pair_mm=override["receiving_nfb_depth_pair_mm"],
    )
    return float(result.width), float(result.height)
