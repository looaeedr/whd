"""Divider-specific collision-derived relief solver owner.

Generic collision/backprojection and semantic ownership stay injected from the
assembly collision facade so this module cannot become a second generic solver.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DividerFrontFoldReliefCandidate:
    """Collision-derived Divider relief constrained to the pre-core Fold domain."""

    cut_polygon_2d: object
    core_start: float
    pre_pair_count: int
    eligible_segment_count: int
    cut_depths: tuple[tuple[str, float], ...]
    physical_footprints_by_source: object | None = None
    evidence: object | None = None


def divider_front_fold_segments(projection, *, core_start: float, tolerance: float = 1e-6):
    rows = []
    for segment in tuple(getattr(projection, "segments_2d", ()) or ()):
        xs = (float(segment[0][0]), float(segment[1][0]))
        if min(xs) < float(core_start) - float(tolerance):
            rows.append(segment)
    return tuple(rows)


def _divider_physical_target_solid_cut(
    *,
    source_key,
    classified,
    material,
    sheet_thickness,
    tolerance=1e-6,
):
    """Build Divider CUTTING from real FW contact + true-thickness source collision.

    Coordinate domains are deliberately separated:

    * legal FW face contact on the resolved Divider supplies the primary relief
      depth in FINAL_CUTTING space;
    * through-thickness source Fold footprints supply only their own physical
      U span and stage length;
    * a secondary stage attaches to the resolved primary CUTTING boundary.

    Material-space FW coordinates and target-UV absolute endpoints are evidence
    only.  They are never reused as final notch anchors.  Validation constants,
    EndCap dimensions and expected values do not participate.
    """
    from shapely.affinity import translate
    from shapely.geometry import box as shapely_box
    from shapely.ops import unary_union

    minx, miny, maxx, maxy = map(float, material.bounds)
    half_t = max(0.0, float(sheet_thickness)) / 2.0
    tol = float(tolerance)

    def snap_u_to_material_edge(value):
        value = float(value)
        if abs(value - minx) <= tol:
            return float(minx)
        if abs(value - maxx) <= tol:
            return float(maxx)
        return value

    rows = dict(classified.get("bands") or {})

    # The physical FW mating band is the legal, single-skin contact whose
    # semantic identity comes from the authoritative source Fold profile.
    fw_contacts = []
    for band_name, raw in rows.items():
        row = dict(raw or {})
        if "fw" not in str(band_name).lower():
            continue
        if bool(row.get("through_thickness")):
            continue
        bounds = row.get("divider_uv_bounds")
        if bounds is None:
            continue
        x0, x1, y0, y1 = map(float, bounds)
        if x1 - x0 <= float(tolerance):
            continue
        low_depth = max(0.0, y1 - miny)
        high_depth = max(0.0, maxy - y0)
        edge = "MIN_Y" if low_depth <= high_depth else "MAX_Y"
        depth = low_depth if edge == "MIN_Y" else high_depth
        if depth > float(tolerance):
            fw_contacts.append((str(band_name), edge, float(depth), (x0, y0, x1, y1)))

    if len(fw_contacts) != 1:
        return None, None, {
            "_invalid": {
                "reason": "Divider physical relief requires exactly one resolved FW contact",
                "fw_contacts": tuple(fw_contacts),
            }
        }

    fw_band_name, edge, primary_depth, fw_bounds = fw_contacts[0]

    penetrating = []
    required_solid = []
    stages = {}
    for band_name in tuple(classified.get("penetrating_bands") or ()):
        row = dict(rows.get(band_name) or {})
        physical = row.get("physical_footprint_2d")
        if physical is None or getattr(physical, "is_empty", True):
            continue
        physical = physical.intersection(material)
        if getattr(physical, "is_empty", True) or float(physical.area) <= float(tolerance) ** 2:
            continue

        raw_x0, y0, raw_x1, y1 = map(float, physical.bounds)
        # Backprojection may land a nominal exterior endpoint a few ulps inside
        # Final Material.  If an endpoint is already within the solver geometry
        # tolerance of the authoritative material U edge, canonicalize it to
        # that edge so polygon boolean operations cannot retain a near-zero-width
        # exterior sliver.  This is topology normalization, not clearance or a
        # validation-derived manufacturing compensation.
        x0 = snap_u_to_material_edge(raw_x0)
        x1 = snap_u_to_material_edge(raw_x1)
        u_span = max(0.0, x1 - x0)
        v_span = max(0.0, y1 - y0)
        if u_span <= float(tolerance) or v_span <= float(tolerance):
            continue

        # Preserve the actual backprojected source-solid collision footprint as
        # replay evidence. Target sheet thickness is normal to the Divider
        # surface; it must not be converted into an in-plane UV translation.
        required_solid.append(physical)

        penetrating.append({
            "band_name": str(band_name),
            "x0": x0, "x1": x1,
            "u_span": u_span,
            "v_span": v_span,
            "physical": physical,
            "row": row,
        })

    if not penetrating:
        return None, None, stages

    # The primary collision is the penetrating stage with the greatest physical
    # U occupation.  This is geometry-derived and naturally selects zl2/zr2 in
    # the current Receiving fold chain without naming those fields here.
    primary = max(
        penetrating,
        key=lambda item: (
            float(item["u_span"]),
            -abs(float(item["x0"]) - minx),
        ),
    )

    if edge == "MIN_Y":
        primary_cut = shapely_box(
            float(primary["x0"]), miny,
            float(primary["x1"]), miny + primary_depth,
        )
        primary_boundary = miny + primary_depth
    else:
        primary_cut = shapely_box(
            float(primary["x0"]), maxy - primary_depth,
            float(primary["x1"]), maxy,
        )
        primary_boundary = maxy - primary_depth

    cuts = [primary_cut.intersection(material)]
    stages[str(primary["band_name"])] = {
        "role": "PHYSICAL_FW_CONTACT_PRIMARY_RELIEF",
        "edge": edge,
        "source_skin_sides": tuple(primary["row"].get("skin_sides") or ()),
        "source_solid_footprint_bounds": tuple(map(float, primary["physical"].bounds)),
        "fw_contact_band": fw_band_name,
        "fw_contact_bounds": tuple(map(float, fw_bounds)),
        "primary_cutting_depth": float(primary_depth),
        "stage_u_span": float(primary["u_span"]),
        "stage_v_span": float(primary["v_span"]),
        "cut_bounds": tuple(map(float, cuts[-1].bounds)),
        "dimension_source": "PHYSICAL_FW_CONTACT_PLUS_SOURCE_TRUE_THICKNESS",
    }

    # Secondary stages keep their own 3D-collision dimensions, but their
    # material-coordinate anchor is the SAME resolved physical FW inside-face
    # boundary as the primary stage. Using the raw independently-backprojected
    # floating endpoint can leave a nanometre-scale gap between two cuts that are
    # physically the same 27-mm datum; that turns the secondary notch into an
    # artificial interior hole when the CUTTING exterior is rebuilt.
    for item in penetrating:
        if item is primary:
            continue
        if edge == "MIN_Y":
            cut = shapely_box(
                float(item["x0"]), float(primary_boundary),
                float(item["x1"]), float(primary_boundary) + float(item["v_span"]),
            )
        else:
            cut = shapely_box(
                float(item["x0"]), float(primary_boundary) - float(item["v_span"]),
                float(item["x1"]), float(primary_boundary),
            )
        cut = cut.intersection(material)
        if getattr(cut, "is_empty", True) or float(cut.area) <= float(tolerance) ** 2:
            continue
        cuts.append(cut)
        stages[str(item["band_name"])] = {
            "role": "PHYSICAL_SECONDARY_COLLISION_RELIEF",
            "edge": edge,
            "source_skin_sides": tuple(item["row"].get("skin_sides") or ()),
            "source_solid_footprint_bounds": tuple(map(float, item["physical"].bounds)),
            "primary_inside_face_boundary": float(primary_boundary),
            "stage_u_span": float(item["u_span"]),
            "stage_v_span": float(item["v_span"]),
            "cut_bounds": tuple(map(float, cut.bounds)),
            "dimension_source": "PHYSICAL_FW_INSIDE_FACE_PLUS_SOURCE_COLLISION_SPAN",
        }

    cut = unary_union(tuple(cuts)).intersection(material)
    required = (
        None
        if not required_solid
        else unary_union(tuple(required_solid)).intersection(material)
    )
    return cut, required, stages


def build_divider_front_fold_relief_candidate(
    joint,
    *,
    world_triangles_by_part,
    mapped_skin_triangles_by_part,
    flat_material_by_part,
    core_start: float,
    source_geometry_keys,
    source_fold_bands_by_key,
    clearance: float = 0.0,
    sheet_thickness: float = 0.0,
    tolerance: float = 1e-6,
    _joint_relief_ownership=None,
    _project_joint_interference_to_relief_owner=None,
    _classify_source_fold_true_thickness_interference=None,
):
    """Derive Divider relief directly from physical source/target sheet collision.

    Source both-skin crossings prove full-thickness source penetration.
    Manufacturing placement comes from physical FW contact plus the actual
    source-solid collision backprojection on the Divider. Target thickness is
    out-of-plane and is never converted into an in-plane UV offset. Validation
    and EndCap dimensions remain read-only.
    """
    from shapely.ops import unary_union

    ownership = _joint_relief_ownership(joint)
    relief_key = str(ownership.relief_part)
    material = (flat_material_by_part or {}).get(relief_key)
    if material is None or getattr(material, "is_empty", True):
        raise ValueError(f"Divider relief material unavailable: {relief_key}")

    minx, miny, maxx, maxy = map(float, material.bounds)
    core_start = float(core_start)
    if not (minx < core_start < maxx):
        raise ValueError(
            f"Divider relief core_start must lie inside material bounds: {core_start} not in {(minx, maxx)}"
        )
    bands_by_key = dict(source_fold_bands_by_key or {})
    missing = [
        str(key) for key in tuple(source_geometry_keys or ())
        if not tuple(bands_by_key.get(str(key), ()) or ())
    ]
    if missing:
        raise ValueError(
            "Divider true-thickness classification requires authoritative source Fold bands: "
            + ", ".join(missing)
        )

    # Numerical boolean fringe only. It never changes nominal manufacturing
    # dimensions and is never reported as a CUTTING formula input.
    boolean_margin = max(5.0e-4, float(tolerance) * 500.0)
    half_t = max(0.0, float(sheet_thickness)) / 2.0
    cut_polygons = []
    cut_depths = []
    pair_count = 0
    eligible_count = 0
    projection_evidence = {}
    physical_footprints_by_source = {}

    for source_key in tuple(source_geometry_keys or ()):
        source_key = str(source_key)
        projected = _project_joint_interference_to_relief_owner(
            joint,
            world_triangles_by_part=world_triangles_by_part,
            mapped_skin_triangles_by_part=mapped_skin_triangles_by_part,
            flat_material_by_part=flat_material_by_part,
            tolerance=float(tolerance),
            source_geometry_key=source_key,
        )
        pair_count += int(projected.projection.pair_count)
        classified = _classify_source_fold_true_thickness_interference(
            source_geometry_key=source_key,
            relief_geometry_key=relief_key,
            mapped_skin_triangles_by_part=mapped_skin_triangles_by_part,
            source_fold_bands=tuple(bands_by_key[source_key]),
            tolerance=float(tolerance),
        )
        eligible_count += int(classified["penetrating_segment_count"])

        source_physical_footprints = []
        band_validation_evidence = {}
        for band_name in tuple(classified["penetrating_bands"]):
            row = dict(classified["bands"][band_name])
            physical = row.get("physical_footprint_2d")
            if physical is None or getattr(physical, "is_empty", True):
                continue
            physical = physical.intersection(material)
            if getattr(physical, "is_empty", True) or float(physical.area) <= float(tolerance) ** 2:
                continue
            source_physical_footprints.append(physical)
            band_validation_evidence[str(band_name)] = {
                "physical_footprint_bounds_validation_only": tuple(map(float, physical.bounds)),
                "physical_footprint_area_validation_only": float(physical.area),
                "source_skin_sides": tuple(row.get("skin_sides") or ()),
            }

        physical_cut, required_target_solid, stage_evidence = _divider_physical_target_solid_cut(
            source_key=source_key,
            classified=classified,
            material=material,
            sheet_thickness=float(sheet_thickness),
            tolerance=float(tolerance),
        )

        if physical_cut is not None:
            if required_target_solid is None or getattr(required_target_solid, "is_empty", True):
                raise ValueError(
                    f"Divider physical target-solid relief has no required footprint: {source_key}"
                )
            physical_footprints_by_source[source_key] = required_target_solid

            # Explicit clearance may alter manufacturing geometry. Numerical
            # boolean margin may not.
            allowance = max(0.0, float(clearance))
            cut = physical_cut
            if allowance > 0.0:
                cut = cut.buffer(allowance, join_style=2)
            cut = cut.intersection(material)
            if getattr(cut, "is_empty", True) or float(cut.area) <= float(tolerance) ** 2:
                raise ValueError(f"Divider physical collision cut is empty: {source_key}")
            cut_polygons.append(cut)
            depths = []
            for row in dict(stage_evidence or {}).values():
                bounds = row.get("cut_bounds")
                if bounds is None:
                    continue
                _cx0, cy0, _cx1, cy1 = map(float, bounds)
                if str(row.get("edge") or "") == "MAX_Y":
                    depths.append(max(0.0, maxy - cy0))
                else:
                    depths.append(max(0.0, cy1 - miny))
            cut_depths.append((source_key, max(depths) if depths else 0.0))

        retained_names = tuple(
            name for name, row in dict(classified["bands"]).items()
            if tuple(row.get("segments_2d") or ()) and not bool(row.get("through_thickness"))
        )
        projection_evidence[source_key] = {
            "pair_count": int(projected.projection.pair_count),
            "eligible_segments": int(classified["penetrating_segment_count"]),
            "penetrating_bands": tuple(classified["penetrating_bands"]),
            "retained_contact_bands": retained_names,
            "solid_half_thickness": float(half_t),
            "manufacturing_topology": "STANDARD_PLUS_SOURCE_FOLD_BAND_ORTHOGONAL",
            "manufacturing_dimensions_source": "PHYSICAL_FW_CONTACT_AND_SOURCE_COLLISION_BACKPROJECTION",
            "physical_stages": dict(stage_evidence or {}),
            "physical_validation": band_validation_evidence,
            "coverage_rule": "POST_REFOLD_WORLD_TRUE_THICKNESS_IS_ACCEPTANCE_AUTHORITY",
        }

    if not cut_polygons:
        return None
    cut = unary_union(cut_polygons).intersection(material)
    if getattr(cut, "is_empty", True) or float(cut.area) <= float(tolerance) ** 2:
        return None
    return DividerFrontFoldReliefCandidate(
        cut_polygon_2d=cut,
        core_start=core_start,
        pre_pair_count=pair_count,
        eligible_segment_count=eligible_count,
        cut_depths=tuple(cut_depths),
        physical_footprints_by_source=dict(physical_footprints_by_source),
        evidence={
            "core_start": core_start,
            "projection_by_source": projection_evidence,
            "ownership": {
                "preserve_part": str(ownership.preserve_part),
                "relief_part": relief_key,
            },
            "classification": "SOURCE_FOLD_BAND_TRUE_THICKNESS",
            "manufacturing_dimensions_source": "PHYSICAL_FW_CONTACT_AND_SOURCE_COLLISION_BACKPROJECTION",
            "boolean_margin": float(boolean_margin),
            "sheet_thickness": max(0.0, float(sheet_thickness)),
        },
    )


def verify_divider_front_fold_relief(
    joint,
    *,
    world_triangles_by_part,
    mapped_skin_triangles_by_part,
    flat_material_by_part,
    core_start: float,
    source_geometry_keys,
    source_fold_bands_by_key,
    physical_footprints_by_source=None,
    tolerance: float = 1e-6,
    _joint_relief_ownership=None,
    _project_joint_interference_to_relief_owner=None,
    _classify_source_fold_true_thickness_interference=None,
):
    """Verify solved Divider by post-refold positive-area true-thickness overlap.

    Both source skins may still intersect the CUTTING boundary after a precise
    relief. Boundary lines are legal. A band is illegal only when its CURRENT
    post-refold both-skin footprint still overlaps retained Divider material with
    positive area. Pre-solve UV footprints remain diagnostic-only evidence.
    """
    ownership = _joint_relief_ownership(joint)
    relief_key = str(ownership.relief_part)
    material = (flat_material_by_part or {}).get(relief_key)
    if material is None or getattr(material, "is_empty", True):
        raise ValueError(f"Divider verification material unavailable: {relief_key}")

    bands_by_key = dict(source_fold_bands_by_key or {})
    pre_footprints = dict(physical_footprints_by_source or {})
    missing = [
        str(key) for key in tuple(source_geometry_keys or ())
        if not tuple(bands_by_key.get(str(key), ()) or ())
    ]
    if missing:
        raise ValueError(
            "Divider verification requires authoritative source Fold bands: "
            + ", ".join(missing)
        )

    pair_count = 0
    contact_segments = 0
    illegal_band_count = 0
    illegal_segment_count = 0
    illegal_area = 0.0
    precut_validation_overlap = 0.0
    by_source = {}
    minx, miny, maxx, maxy = map(float, material.bounds)
    verification_span = max(maxx - minx, maxy - miny, 1.0)
    # Verification-only numerical area tolerance: one linear solver tolerance
    # swept across the current material span. It never changes CUTTING geometry.
    area_tol = max(float(tolerance) ** 2, float(tolerance) * verification_span)

    for source_key in tuple(source_geometry_keys or ()):
        source_key = str(source_key)
        projected = _project_joint_interference_to_relief_owner(
            joint,
            world_triangles_by_part=world_triangles_by_part,
            mapped_skin_triangles_by_part=mapped_skin_triangles_by_part,
            flat_material_by_part=flat_material_by_part,
            tolerance=float(tolerance),
            source_geometry_key=source_key,
        )
        pair_count += int(projected.projection.pair_count)

        classified = _classify_source_fold_true_thickness_interference(
            source_geometry_key=source_key,
            relief_geometry_key=relief_key,
            mapped_skin_triangles_by_part=mapped_skin_triangles_by_part,
            source_fold_bands=tuple(bands_by_key[source_key]),
            tolerance=float(tolerance),
        )

        positive_bands = []
        boundary_only_bands = []
        source_illegal_area = 0.0
        source_illegal_segments = 0

        for band_name in tuple(classified.get("penetrating_bands") or ()):
            row = dict(classified["bands"][band_name])
            footprint = row.get("physical_footprint_2d")
            overlap_area = 0.0
            if footprint is not None and not getattr(footprint, "is_empty", True):
                overlap = material.intersection(footprint)
                overlap_area = (
                    0.0 if getattr(overlap, "is_empty", True) else float(overlap.area)
                )
            if overlap_area > area_tol:
                positive_bands.append(str(band_name))
                source_illegal_area += overlap_area
                source_illegal_segments += len(tuple(row.get("segments_2d") or ()))
            else:
                boundary_only_bands.append(str(band_name))

        illegal_band_count += len(positive_bands)
        illegal_segment_count += source_illegal_segments
        illegal_area += source_illegal_area

        source_contact = int(classified.get("retained_contact_segment_count") or 0)
        source_contact += sum(
            len(tuple(classified["bands"][name].get("segments_2d") or ()))
            for name in boundary_only_bands
        )
        contact_segments += source_contact

        diagnostic_overlap = 0.0
        old = pre_footprints.get(source_key)
        if old is not None and not getattr(old, "is_empty", True):
            overlap = material.intersection(old)
            diagnostic_overlap = (
                0.0 if getattr(overlap, "is_empty", True) else float(overlap.area)
            )
        precut_validation_overlap += diagnostic_overlap

        by_source[source_key] = {
            "pair_count": int(projected.projection.pair_count),
            "front_illegal_segments": int(source_illegal_segments),
            "true_thickness_penetrating_bands": tuple(positive_bands),
            "boundary_only_bands": tuple(boundary_only_bands),
            "positive_overlap_area": float(source_illegal_area),
            "retained_contact_segments": int(source_contact),
            "precut_uv_overlap_area_validation_only": float(diagnostic_overlap),
        }

    verified = illegal_area <= area_tol and illegal_band_count == 0
    return {
        "pair_count": int(pair_count),
        "front_illegal_segments": int(illegal_segment_count),
        "true_thickness_penetration_segments": int(illegal_segment_count),
        "true_thickness_penetrating_band_count": int(illegal_band_count),
        "positive_overlap_area": float(illegal_area),
        "precut_uv_overlap_area_validation_only": float(precut_validation_overlap),
        "retained_contact_segments": int(contact_segments),
        "verified": bool(verified),
        "classification": "POST_REFOLD_POSITIVE_AREA_TRUE_THICKNESS",
        "core_start_evidence_only": float(core_start),
        "by_source": by_source,
    }
