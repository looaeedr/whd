# -*- coding: utf-8 -*-
"""On-demand, fail-closed inventory of ALL final-assembly physical pair crossings.

Surface intersections are NOT proof of illegal solid-volume penetration.
Certified divider/endcap relief remains the manufacturing owner. The UI must
show unresolved non-terminal crossings rather than falsely say "no collision".
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from math import isfinite

from .assembly_geometry import detect_world_mesh_surface_interference


@dataclass(frozen=True)
class AssemblyPhysicalPair:
    left: str
    right: str
    status: str
    pair_count: int
    segments: tuple
    region_xyz: tuple | None = None


@dataclass(frozen=True)
class AssemblyPhysicalCollisionAudit:
    pairs: tuple[AssemblyPhysicalPair, ...]
    visible_keys: tuple[str, ...]

    @property
    def unresolved(self):
        return tuple(row for row in self.pairs if row.status == "UNRESOLVED_CROSSING")

    @property
    def contacts(self):
        return tuple(row for row in self.pairs if row.status in {
            "VERIFIED_TERMINAL_CONTACT", "VERIFIED_CERTIFIED_RELIEF_CONTACT",
        })

    @property
    def evaluated_pair_count(self):
        return len(self.pairs)

    def require_no_unresolved(self):
        if self.unresolved:
            names = "; ".join(f"{x.left} ↔ {x.right}: {x.pair_count} crossing pairs"
                              for x in self.unresolved)
            raise ValueError("ASSEMBLY_PHYSICAL_CROSSING_UNVERIFIED: " + names)
        return True


def collision_part_display_name(key):
    """Operator-facing names for exact audited physical part IDs."""
    names = {
        "head": "封頭", "tail": "封尾",
        "box_body:left_side": "左側板", "box_body:right_side": "右側板",
        "box_body:back": "後面板",
    }
    key = str(key)
    if key in names:
        return names[key]
    if key.startswith("box_body:divider:"):
        return "中隔"
    if key.startswith("inner_door:") and key.endswith("_frame"):
        side = key.rsplit(":", 1)[-1]
        return "內門" + {"left_frame":"左框","right_frame":"右框",
                       "top_frame":"上框","bottom_frame":"下框"}.get(side, side)
    if key.startswith("inner_door:") and key.endswith(":panel"):
        return "內門"
    return key


def _bounds(triangles):
    points = (pt for tri in triangles for pt in tri)
    lo = [float("inf")] * 3
    hi = [float("-inf")] * 3
    count = 0
    for pt in points:
        count += 1
        try:
            raw = tuple(pt)
            if len(raw) != 3 or any(isinstance(v, bool) for v in raw):
                raise ValueError("nonphysical world vertex")
            xyz = tuple(float(v) for v in raw)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("ASSEMBLY_COLLISION_INVALID_WORLD_MESH") from exc
        if not all(isfinite(v) for v in xyz):
            raise ValueError("ASSEMBLY_COLLISION_INVALID_WORLD_MESH")
        for axis, value in enumerate(xyz):
            lo[axis] = min(lo[axis], value)
            hi[axis] = max(hi[axis], value)
    if not count:
        raise ValueError("ASSEMBLY_COLLISION_MISSING_PHYSICAL_MESH")
    return tuple((lo[axis], hi[axis]) for axis in range(3))


def _bbox_touch(a, b, tolerance):
    return all(x[1] + tolerance >= y[0] and y[1] + tolerance >= x[0]
               for x, y in zip(a, b))


def _frame_terminal_contact(key_a, key_b, a_bounds, b_bounds, intersections, tol):
    """Allow ONLY the actual edge-to-endcap/divider horizontal terminal plane.

    A frame's lower and upper edges may meet the certified Divider or head
    respectively. The intersection must lie wholly at the frame's boundary,
    while the other part must terminate at that same plane from the other side.
    Neither generic AABB overlap nor an arbitrary pair-name whitelist suffices.
    """
    if not intersections:
        return False
    left_is_frame = "inner_door:" in key_a and key_a.endswith("_frame")
    right_is_frame = "inner_door:" in key_b and key_b.endswith("_frame")
    if left_is_frame == right_is_frame:
        return False
    frame_key, other_key = ((key_a, key_b) if left_is_frame else (key_b, key_a))
    frame_bounds, other_bounds = ((a_bounds, b_bounds) if left_is_frame else (b_bounds, a_bounds))
    if not (other_key == "head" or other_key == "tail"
            or other_key.startswith("box_body:divider:")):
        return False
    ys = [float(point[1]) for point in intersections]
    frame_low, frame_high = frame_bounds[1]
    other_low, other_high = other_bounds[1]
    for frame_edge in (frame_low, frame_high):
        if not all(abs(y - frame_edge) <= tol for y in ys):
            continue
        # Must meet an opposed terminal; an overlapping core is not allowed.
        other_edge = (other_high if abs(frame_edge - other_high) <= tol
                      else other_low if abs(frame_edge - other_low) <= tol else None)
        if other_edge is None:
            continue
        if (abs(frame_edge-frame_low) <= tol and abs(frame_edge-other_high) <= tol
                or abs(frame_edge-frame_high) <= tol and abs(frame_edge-other_low) <= tol):
            return True
    return False


def _certified_pair_allowances(diagnostics):
    """Only accept explicit post-solve TRUE-THICKNESS evidence, not a status guess."""
    approved = set()
    for row in tuple(diagnostics or ()):
        if (
            str(getattr(row, "candidate_status", "")) != "CERTIFIED_REGISTRY_VERIFIED"
            or bool(getattr(row, "illegal_penetration", True))
            or str(getattr(row, "target_part", "")) != "box_body"
        ):
            continue
        divider = str(getattr(row, "subject_part", ""))
        post = dict((getattr(row, "evidence", {}) or {}).get("post") or {})
        if not divider.startswith("box_body:divider:"):
            continue
        if int(post.get("true_thickness_penetrating_band_count", -1)) != 0:
            continue
        for side in ("box_body:left_side", "box_body:right_side"):
            approved.add(frozenset((divider,side)))
    return frozenset(approved)


def audit_all_physical_part_pairs(world_triangles_by_part, *,
                                  visible_part_keys=None, tolerance=1e-5,
                                  certified_relief_diagnostics=()):
    """Check every unordered distinct piece pair with broad-phase AABB pruning.

    Composite 'box_body' is excluded in favor of its independent, named pieces.
    All other generated parts (including future panels/frames/endcaps) participate.
    Missing selected mesh is a hard error, never a misleading zero result.
    """
    # An invalid tolerance must never make the broad-phase report a false
    # separation or implicitly allow a nonphysical contact at FinalScene.
    if isinstance(tolerance, bool):
        raise ValueError("ASSEMBLY_COLLISION_INVALID_TOLERANCE")
    try:
        tolerance = float(tolerance)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("ASSEMBLY_COLLISION_INVALID_TOLERANCE") from exc
    if not isfinite(tolerance) or tolerance < 0:
        raise ValueError("ASSEMBLY_COLLISION_INVALID_TOLERANCE")
    raw = dict(world_triangles_by_part or {})
    selected = None if visible_part_keys is None else frozenset(visible_part_keys)
    keys = tuple(sorted(k for k, v in raw.items()
                        if k != "box_body" and v and (selected is None or k in selected)))
    if selected is not None:
        missing = tuple(sorted(key for key in selected if key not in raw))
        if missing:
            raise ValueError("ASSEMBLY_COLLISION_MISSING_VISIBLE_PARTS: " + ", ".join(missing))
    meshes = {key: tuple(raw[key]) for key in keys}
    bounds = {key: _bounds(meshes[key]) for key in keys}
    result = []
    certified_pairs = _certified_pair_allowances(certified_relief_diagnostics)
    for a, b in combinations(keys, 2):
        ba, bb = bounds[a], bounds[b]
        if not _bbox_touch(ba, bb, tolerance):
            result.append(AssemblyPhysicalPair(a,b,"AABB_SEPARATED",0,()))
            continue
        crossing = detect_world_mesh_surface_interference(
            meshes[a], meshes[b], tolerance=tolerance)
        if not crossing.pair_count:
            # NO_NONCOPLANAR_CROSSING is not a proof of no 3D overlap.
            status = "NO_NONCOPLANAR_CROSSING"
        elif frozenset((a,b)) in certified_pairs:
            # Existing post-cut 7mm certified C sample demonstrates zero
            # positive-thickness penetrating bands for BOTH physical sides.
            status = "VERIFIED_CERTIFIED_RELIEF_CONTACT"
        elif _frame_terminal_contact(
            a,b,ba,bb,crossing.intersection_points,tolerance):
            status = "VERIFIED_TERMINAL_CONTACT"
        else:
            status = "UNRESOLVED_CROSSING"
        points = tuple(crossing.intersection_points or ())
        region = (tuple((round(min(p[i] for p in points), 5),
                         round(max(p[i] for p in points), 5))
                        for i in range(3)) if points else None)
        result.append(AssemblyPhysicalPair(
            a,b,status,int(crossing.pair_count),
            tuple(crossing.intersection_segments or ()),region))
    return AssemblyPhysicalCollisionAudit(tuple(result),keys)
