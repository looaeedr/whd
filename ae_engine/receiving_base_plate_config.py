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
    # The actual LEFT original CUTTING has TWO independent 44x194/Ø5.1
    # hole quartets. A second selected switch (slot 1) need not reuse the
    # exact same model name, but must share the SAME full CSV shape source.
    shape = None
    for hole in holes:
        parsed = parse_numeric_model_ref(hole.get("model_filename"))
        if parsed is None:
            return None
        brand, model = parsed
        if hole.get("source_brand") not in (None, brand):
            return None
        spec = model_spec(brand, model)
        # A matching depth or pitch alone is NOT permission to borrow LEFT.
        if (spec is None or spec.screw_pitch_mm != (44.0, 194.0)
                or abs(float(spec.screw_diameter_mm or 0.0) - 5.1) > 1e-6
                or spec.depth_mm is None
                or abs(float(spec.depth_mm) - depth) > 1e-6):
            return None
        source = (
            brand, spec.width_mm, spec.height_mm, spec.opening_mm,
            spec.screw_pitch_mm, spec.screw_diameter_mm,
            spec.screw_offset_x_mm, spec.screw_offset_y_mm, spec.depth_mm,
        )
        if shape is not None and source != shape:
            return None
        shape = source
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



def _source_two_tier_matching_left_base_config(data):
    """Derive two separate source LEFT tier blanks without a manual base choice.

    Only the *existing* LEFT source's exact 44x194 / diameter 5.1 numeric
    cutting pattern qualifies. Current Bay/Set, each physical tier, and all
    per-model CSV owners are checked against the committed source; a model
    that could instead require RIGHT/CENTER cannot silently borrow LEFT.
    This selects an original blank *shape*, not screw X, installed Y/Z,
    quantity, or manufacturing approval. The original two 400 screw quartets
    are example openings, not a limit on operator-selected horizontal NFBs;
    per-hole geometry and sheet clearance are checked downstream.
    """
    config = data.get("nfb_config")
    if (data.get("nfb_config_submitted") is not True
            or not isinstance(config, Mapping)
            or config.get("layer_count") != 2):
        return None
    from .receiving_tier_ear_z_targets import _current_brand_config
    legacy_brand, current = _current_brand_config(data)
    if current != config:
        raise ValueError("RECEIVING_TIER_LEFT_SOURCE_BAY_IDENTITY_DRIFT")
    holes = config.get("holes")
    if not isinstance(holes, (list, tuple)) or len(holes) < 2:
        return None
    from .receiving_nfb_model_identity import parse_numeric_model_ref
    from .receiving_nfb_numeric_catalog import model_spec
    tiers = {0: [], 1: []}
    for hole in holes:
        if not isinstance(hole, Mapping):
            return None
        tier = hole.get("layer_index")
        if (type(tier) is not int or tier not in tiers
                or hole.get("layer_count", 2) != 2):
            return None
        parsed = parse_numeric_model_ref(hole.get("model_filename"))
        if parsed is None:
            return None
        brand, model = parsed
        if (hole.get("source_brand") not in (None, brand)
                or (legacy_brand and legacy_brand != brand)):
            # A wrong/cross-brand row cannot authorize this LEFT blank;
            # return no *shape* instead of killing other correctly sourced
            # tier Z previews. The per-tier source resolver independently
            # refuses the affected tier's uncertified depth/installation.
            return None
        spec = model_spec(brand, model)
        if (spec is None or spec.screw_pitch_mm != (44.0, 194.0)
                or spec.screw_diameter_mm != 5.1
                or spec.depth_mm is None or spec.depth_mm <= 0):
            return None
        # Distinct CSV model names can describe the SAME physical machining
        # source (e.g. 士林 2P400 and 3P400SN). Use exact dimensional
        # source identity, never a filename equality test or depth alone.
        # Keep brand, body/opening, fixing-hole shape and offsets in this
        # signature so near-matching variants cannot borrow the LEFT blank.
        tiers[tier].append((
            brand, spec.width_mm, spec.height_mm, spec.opening_mm,
            spec.screw_pitch_mm, spec.screw_diameter_mm,
            spec.screw_offset_x_mm, spec.screw_offset_y_mm,
            float(spec.depth_mm),
        ))
    if any(not rows or len({r for r in rows}) != 1
           for rows in tiers.values()):
        return None
    if float(data["t"]) != 2.0:
        raise ValueError("RECEIVING_TIER_LEFT_SOURCE_REQUIRES_T2")
    from .receiving_weld_ear_policy import receiving_source_fixing_pitch_x_mm
    from .sheetmetal_part_adapters import RECEIVING_BASE_PATTERN_LEFT
    pitch_x = receiving_source_fixing_pitch_x_mm(
        box_outer_width_mm=float(data["w"]),
        box_side_thickness_mm=float(data["t"]),
    )
    source_ear_inset = 20.0
    blank_width = pitch_x + 2.0 * source_ear_inset
    side_shrink = (float(data["w"]) - blank_width) / 2.0
    if blank_width <= 2.0 * source_ear_inset:
        raise ValueError("RECEIVING_TIER_LEFT_SOURCE_BLANK_TOO_NARROW")
    return {
        "pattern": RECEIVING_BASE_PATTERN_LEFT,
        "height": 300.0 + 2.0 * 20.0,
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
    # The selected/submitted NFBConfig and the current brand CSV are the
    # physical source authority, even when an older project has saved a
    # separate manual base pattern.  Resolve source FIRST: accepting a stale
    # saved RIGHT/LEFT or W800 shrink silently changes the manufactured sheet.
    source_config = _source_center_base_config(data)
    if source_config is None:
        source_config = _source_left_flat_base_config(data)
    if source_config is None:
        source_config = _source_two_tier_matching_left_base_config(data)
    if source_config is not None:
        # Matching legacy values are geometrically equivalent and may remain
        # in the project file, but the source-derived values own this PartSpec.
        # Mismatching legacy values are not silently promoted to authority.
        config = source_config
    elif data.get("nfb_config_submitted") is True:
        # A submitted *numeric CSV V5* model is not proof that an unknown
        # RIGHT/flat/tier source exists. Do not revive a manual pattern when
        # the typed source lacks a unique physical match. Legacy DXF-backed
        # saved jobs retain their previous preview/settings compatibility;
        # they have separate independent manufacturing proof obligations.
        nfb = data.get("nfb_config")
        holes = nfb.get("holes") if isinstance(nfb, Mapping) else None
        has_numeric_csv = (
            isinstance(holes, (list, tuple))
            and any(isinstance(hole, Mapping)
                    and str(hole.get("model_filename") or "").startswith("nfbv5:")
                    for hole in holes)
        )
        if has_numeric_csv:
            # Two tiers already have separate submitted physical owners, and
            # current CENTER/LEFT one-row source recognition cannot resolve
            # their variant from both rows at once. Keep an existing physical
            # root *for preview/skin target calculation only*: the tier
            # assembly explicitly marks every resulting FinalScene unreleased.
            # One-row unknown CSV sources must NEVER borrow a saved pattern.
            if not (isinstance(nfb, Mapping)
                    and nfb.get("layer_count") == 2):
                return None
        config = data.get("receiving_base_plate")
    else:
        # Older projects without submitted NFBs retain their existing manual
        # settings for normal editing/preview; this does not certify MFG-2.
        config = data.get("receiving_base_plate")
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
        # In the two-tier shape-proven LEFT case, each tier's actual
        # independently selected CSV model/depth owns its *own* Z datum in
        # resolve_receiving_tier_base_z_targets. Do not ask the one-tier
        # flat-depth helper to collapse the two physical layers into one.
        config_now = data.get("nfb_config")
        if (isinstance(config_now, Mapping)
                and config_now.get("layer_count") == 2):
            reference = None
        else:
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
