# -*- coding: utf-8 -*-
"""#1502: current committed CSV/NFBConfig feeds ONE normal WHD FinalScene.

Do not create a parallel CSV button, preview cache or DXF-only geometry.
The ordinary Phase6 resolver consumes this projection for both 2D and 3D.
Only an actually confirmed world-X datum may move NFB screw holes; no
guessing an X or hiding existing physical blanks while it is unconfirmed.
"""
from __future__ import annotations

from collections.abc import Mapping

from .contracts import BasePlatePartSpec
from .receiving_base_plate_config import receiving_base_plate_values
from .receiving_nfb_v5_configured_inner_door import (
    NfbV5ConfiguredInnerDoorHole,
    trial_configured_nfb_v5_inner_door_render_data,
)
from .receiving_nfb_v5_live_base_preview import (
    project_csv_v5_onto_existing_assembly_parts,
)
from .receiving_nfb_model_identity import parse_numeric_model_ref


def _physical_feature_from_transport(value):
    """Restore only WHD's trusted feature DTO shapes from Phase6 transport.

    ManufacturingResolveRequest freezes dataclasses into dicts with a type
    marker. The normal resolver must recover real Hole Editor feature types
    before checking the original source; a raw dict is not a cutting part.
    """
    from .sheetmetal_feature_core import (
        CircleFeature, RectFeature, ProfileFeature, FeatureAnchor,
    )
    from .sheetmetal_geometry import Vec2
    classes = {
        "CircleFeature": CircleFeature,
        "RectFeature": RectFeature,
        "ProfileFeature": ProfileFeature,
    }
    if isinstance(value, tuple(classes.values())):
        return value
    if not isinstance(value, Mapping):
        raise ValueError("NFB_COMMITTED_CSV_FEATURE_DTO_INVALID")
    kind = str(value.get("__dataclass_type__") or "")
    target = classes.get(kind.rsplit(".",1)[-1])
    if target is None or kind != (
            "ae_engine.sheetmetal_feature_core." + target.__name__):
        raise ValueError("NFB_COMMITTED_CSV_UNSUPPORTED_FEATURE_DTO")
    def vec(p):
        if isinstance(p, Vec2):
            return p
        if not isinstance(p, Mapping) or "x" not in p or "y" not in p:
            raise ValueError("NFB_COMMITTED_CSV_FEATURE_VEC2_INVALID")
        return Vec2(float(p["x"]), float(p["y"]))
    fields = {k: v for k,v in value.items() if k != "__dataclass_type__"}
    fields["anchor"] = FeatureAnchor(fields["anchor"])
    fields["offset"] = vec(fields["offset"])
    fields["source_params"] = tuple(
        tuple(row) for row in tuple(fields.get("source_params") or ())
    )
    if target is ProfileFeature:
        fields["points"] = tuple(vec(p) for p in fields.get("points") or ())
        fields["layered_profiles"] = tuple(
            (str(layer), tuple(vec(p) for p in points), bool(closed))
            for layer, points, closed in tuple(fields.get("layered_profiles") or ())
        )
    return target(**fields)


def _source_world_x_from_committed_editor_feature(
    snapshot, panel, row, *, brand, model,
):
    """Recover a placed opening's X from its existing original Hole Editor.

    This is not an inferred NFB pitch: the Feature is committed on the
    physical panel with CSV SHA and exact original brand/model. Its centre
    and Y must agree with the same current numeric model and tier datum.
    """
    from hashlib import sha256
    from math import hypot
    from .receiving_nfb_numeric_catalog import brand_csv_path, model_spec
    from .receiving_nfb_y_projection import project_nfb_inner_door_nominal_y
    from .receiving_nfb_manufacturing_release import _resolve_physical_panel
    from .sheetmetal_feature_core import (
        FeatureAnchor, ProfileFeature, _rotate_local_point,
    )

    features = (snapshot.get("part_features") or {}).get(panel.stable_id, ())
    if not isinstance(features, (tuple, list)):
        return None
    features = tuple(_physical_feature_from_transport(p) for p in features)
    wanted = (row.get("physical_hole_id"), row.get("layer_index", 0),
              row.get("slot_index"))
    matches = []
    for feature in features:
        if not isinstance(feature, ProfileFeature) or feature.source_type != "NFB_CSV_SOURCE":
            continue
        params = dict(feature.source_params)
        if params.get("part_id") != panel.stable_id:
            continue
        identity = (
            params.get("hole_id") == wanted[0]
            if "hole_id" in params else
            (params.get("layer_index"), params.get("slot_index")) == wanted[1:]
        )
        if identity:
            matches.append((feature, params))
    if not matches:
        return None
    if len(matches) != 1:
        raise ValueError("NFB_CSV_EDITOR_DUPLICATE_COMMITTED_OPENING")
    feature, params = matches[0]
    csv_sha = sha256(brand_csv_path(brand).read_bytes()).hexdigest()
    spec = model_spec(brand, model)
    if (params.get("brand") != brand or params.get("model") != model
            or params.get("csv_sha256") != csv_sha or spec is None
            or spec.opening_corners_xy_mm is None
            or feature.anchor is not FeatureAnchor.ABSOLUTE_FINISHED_FACE
            or feature.layer != "CUTTING"
            or len(feature.points) != 4
            or feature.layered_profiles):
        raise ValueError("NFB_CSV_EDITOR_OPENING_SOURCE_STALE")
    points = tuple(
        (float(rot.x + feature.offset.x),
         float(rot.y + feature.offset.y))
        for rot in (_rotate_local_point(p, feature.rotation_deg)
                    for p in feature.points)
    )
    source = tuple((float(x),float(y)) for x,y in spec.opening_corners_xy_mm)
    expected_edges = sorted(round(hypot(source[(i+1)%4][0]-source[i][0],
                                        source[(i+1)%4][1]-source[i][1]), 6)
                            for i in range(4))
    actual_edges = sorted(round(hypot(points[(i+1)%4][0]-points[i][0],
                                      points[(i+1)%4][1]-points[i][1]), 6)
                          for i in range(4))
    if expected_edges != actual_edges:
        raise ValueError("NFB_CSV_EDITOR_OPENING_SIZE_DIFFERS_FROM_SOURCE")
    panel_now, placement = _resolve_physical_panel(
        snapshot, panel.inner_door_id,
    )
    if panel_now.stable_id != panel.stable_id:
        raise ValueError("NFB_CSV_EDITOR_PHYSICAL_PANEL_CHANGED")
    centre_x = (min(x for x,y in points)+max(x for x,y in points))/2
    centre_y = (min(y for x,y in points)+max(y for x,y in points))/2
    projection = project_nfb_inner_door_nominal_y(
        snapshot, panel.inner_door_id,
        layer_count=row.get("layer_count", 1),
        slot_index=row.get("layer_index", 0),
    )
    expected_face_y = (float(projection.unfolded_uv_y_mm)
                       - float(panel.fold_bottom) + float(panel.thickness))
    if abs(centre_y-expected_face_y)>1e-6:
        raise ValueError("NFB_CSV_EDITOR_OPENING_Y_DIFFERS_FROM_LAYER")
    core_width = float(panel.unfolded_width)-float(panel.fold_left)-float(panel.fold_right)
    return (centre_x - float(panel.thickness) - core_width/2
            + float(placement.world_offset[0]))


def _submitted_csv_holes(snapshot):
    """Get canonical selected Bay's full config; no separate editor authority."""
    if (not isinstance(snapshot, Mapping)
            or snapshot.get("model") not in ("受電箱", "RECEIVING")
            or snapshot.get("nfb_config_submitted") is not True):
        return ()
    config = snapshot.get("nfb_config")
    if not isinstance(config, Mapping):
        return ()
    rows = config.get("holes")
    if not isinstance(rows, (tuple, list)) or not rows:
        return ()
    # Old projects with DXF references still use their own existing path;
    # a *mixed* CSV/DXF configuration cannot silently drop physical holes.
    parsed = tuple(
        parse_numeric_model_ref(row.get("model_filename"))
        if isinstance(row, Mapping) else None for row in rows
    )
    if not any(parsed):
        return ()
    if any(p is None for p in parsed):
        raise ValueError("NFB_COMMITTED_CSV_MIXED_UNRESOLVED_SOURCE")
    count = config.get("layer_count")
    if type(count) is not int or count not in (1, 2):
        raise ValueError("NFB_COMMITTED_CSV_INVALID_LAYER_COUNT")
    # The original Hole Editor is also a genuine source of physical hole
    # position. If the saved numeric config lacks independent confirmed X,
    # reuse ONLY an exact source-hashed, already-placed editor ProfileFeature.
    # Never guess X from slot number or model pitch.
    from .receiving_nfb_persistence import normalize_nfb_config
    from .receiving_nfb_base_assembly_xy import receiving_nfb_layer_centers
    from .cabinet_types.policy import derive_inner_door_panels

    validated = normalize_nfb_config(config)
    layout = snapshot.get("receiving_layout")
    selector = snapshot.get("_receiving_runtime_selection")
    if not isinstance(layout, Mapping) or not isinstance(selector, Mapping):
        raise ValueError("NFB_COMMITTED_CSV_ACTIVE_SET_BAY_REQUIRED")
    sets = layout.get("sets")
    si, bi = selector.get("set_index"), selector.get("bay_index")
    if (not isinstance(sets, (list, tuple))
            or type(si) is not int or not 0 <= si < len(sets)
            or sets[si].get("stable_id") != selector.get("set_id")):
        raise ValueError("NFB_COMMITTED_CSV_SET_IDENTITY_DRIFT")
    bays = sets[si].get("bays")
    if (not isinstance(bays, (list, tuple))
            or type(bi) is not int or not 0 <= bi < len(bays)
            or bays[bi].get("stable_id") != selector.get("bay_id")
            or bays[bi].get("nfb_config_submitted") is not True
            or bays[bi].get("nfb_config") != config):
        raise ValueError("NFB_COMMITTED_CSV_BAY_IDENTITY_DRIFT")
    upper = tuple(p for p in derive_inner_door_panels(snapshot)
                  if str(p.cell_key).split(":")[-1] == "0")
    if len(upper) != 1:
        raise ValueError("NFB_COMMITTED_CSV_UNIQUE_UPPER_DOOR_REQUIRED")
    door_id = upper[0].inner_door_id
    centers = receiving_nfb_layer_centers(snapshot, door_id)
    # Only the physical tiers actually holding NFBs get a base/screw set.
    owners = {p.layer_index for p in centers}
    if count == 2 and owners != {0, 1}:
        return ()
    if count == 1 and owners != {0}:
        return ()
    holes = []
    seen = set()
    for row, model in zip(validated["holes"], parsed):
        tier = row.get("layer_index", 0 if count == 1 else None)
        brand = row.get("source_brand") or model[0]
        hole_id = row.get("physical_hole_id")
        if (tier not in owners or brand != model[0]
                or hole_id in seen):
            raise ValueError("NFB_COMMITTED_CSV_OWNER_OR_MODEL_MISMATCH")
        x = row.get("manual_x_mm")
        if row.get("manual_x_state") != "CONFIRMED" or x is None:
            x = _source_world_x_from_committed_editor_feature(
                snapshot, upper[0], row, brand=brand, model=model[1],
            )
            if x is None:
                # Existing editor may be in a temporary unconfirmed/draft
                # state. Keep the normal physical blank visible; do not make
                # any source-less screw CUTTING.
                return ()
        seen.add(hole_id)
        holes.append(NfbV5ConfiguredInnerDoorHole(
            physical_hole_id=hole_id,
            brand=brand,
            model_ref=row["model_filename"],
            world_x_mm=float(x),
            layer_count=count,
            slot_index=tier,
            rotation_deg=row.get("rotation_deg", 0),
        ))
    return door_id, tuple(holes)


def _existing_source_specs(snapshot, holes):
    count = holes[0].layer_count
    if count == 2:
        from .receiving_nfb_layer_physical_parts import (
            source_receiving_nfb_tier_base_specs,
        )
        return source_receiving_nfb_tier_base_specs(snapshot)
    physical = receiving_base_plate_values(snapshot)
    if physical is None:
        raise ValueError("NFB_COMMITTED_CSV_REAL_BASE_SOURCE_MISSING")
    spec = BasePlatePartSpec(
        width=float(snapshot["w"]), height=float(physical["h"]),
        thickness=float(snapshot["t"]),
        shrink_top=float(physical["base_plate_shrink_top"]),
        shrink_bottom=float(physical["base_plate_shrink_bottom"]),
        shrink_left=float(physical["base_plate_shrink_left"]),
        shrink_right=float(physical["base_plate_shrink_right"]),
        bend=float(physical["base_plate_bend"]),
        model_name="受電箱",
        receiving_bend_pattern=physical["receiving_bend_pattern"],
        receiving_nfb_depth_pair_mm=physical["receiving_nfb_depth_pair_mm"],
        physical_id="base_plate",
    )
    return {0: spec}


def _without_derived_csv_door_features(snapshot, inner_door_id):
    """CSV Hole Editor Feature is an alias, not a second opening authority.

    The ordinary Hole Editor already materializes a ProfileFeature with
    source_type=NFB_CSV_SOURCE. Before building the same opening from the
    committed numeric NFBConfig, exclude only that derived alias. Retain
    every other actual Hole Editor profile/marking and never mutate saved
    source values or user-authored features.
    """
    from .cabinet_types.policy import derive_inner_door_panels

    upper = tuple(p for p in derive_inner_door_panels(snapshot)
                  if p.inner_door_id == inner_door_id
                  and str(p.cell_key).split(":")[-1] == "0")
    if len(upper) != 1:
        raise ValueError("NFB_COMMITTED_CSV_DOOR_FEATURE_OWNER_UNRESOLVED")
    part_id = upper[0].stable_id
    filtered = dict(snapshot)
    for key in ("part_features", "surface_features"):
        store = snapshot.get(key)
        if not isinstance(store, Mapping) or part_id not in store:
            continue
        original = store[part_id]
        if not isinstance(original, (tuple, list)):
            raise ValueError("NFB_COMMITTED_CSV_DOOR_FEATURES_INVALID")
        typed = tuple(_physical_feature_from_transport(p) for p in original)
        kept = tuple(
            feature for feature in typed
            if getattr(feature, "source_type", None) != "NFB_CSV_SOURCE"
        )
        # Even if no CSV alias is present, forward restored native Feature
        # dataclasses so the existing inner-door FinalScene never sees raw
        # manufacturing DTO dictionaries.
        filtered[key] = {**store, part_id: kept}
    return filtered


def apply_committed_csv_v5_to_canonical_parts(snapshot, assembly_parts):
    """Read current committed CSV once per physical resolve, update same parts.

    Not an extra renderer or manufacturing approval. Incomplete WORLD-X keeps
    the existing editable physical scene (instead of inventing a screw datum).
    All complete and provenance-valid CSV records cut into actual FinalScene.
    """
    parts = tuple(assembly_parts)
    sourced = _submitted_csv_holes(snapshot)
    if not sourced:
        return parts
    inner_door_id, holes = sourced
    if not any(part.part_key.startswith("base_plate") for part in parts):
        # No original material sheet exists. A missing Base Plate may not be
        # manufactured by silently reusing an unrelated door or box-body.
        raise ValueError("NFB_COMMITTED_CSV_REAL_BASE_PART_MISSING")
    # The legacy Hole Editor's NFB_CSV_SOURCE feature is derived from this
    # same committed CSV, not a second source. Excluding only that alias
    # avoids cutting the exact opening twice during standard 2D/3D resolve.
    source_snapshot = _without_derived_csv_door_features(snapshot, inner_door_id)
    proof = trial_configured_nfb_v5_inner_door_render_data(
        source_snapshot, inner_door_id, holes=holes,
    )
    result = project_csv_v5_onto_existing_assembly_parts(
        snapshot, inner_door_id, door=proof,
        configured_holes=holes,
        base_specs=_existing_source_specs(snapshot, holes),
        assembly_parts=parts,
    )
    # The actual door's CUTTING comes from this exact CSV proof as well.
    # Keeping the unmodified legacy derived-hole scene would leave two
    # independent ways to manufacture the same opening.
    owner = next((part for part in result if part.part_key == proof.part_id), None)
    if owner is None:
        return result  # partial source-only caller without a door part
    from dataclasses import replace
    return tuple(
        replace(part, render_data=proof.render_data)
        if part.part_key == proof.part_id else part for part in result
    )
