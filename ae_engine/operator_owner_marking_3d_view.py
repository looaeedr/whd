"""Projection witness for owner ink on the existing standalone display mesh.

Does not fit or modify material, create bends, or authorize DXF. Independent
UV projection supplies the paths; this module only certifies their support or
withholds them rather than bridging discontinuous/ambiguous finite folds.
"""
from .final_scene_independent_annotations import project_independent_scene_annotation_paths
from .operator_manual_marking import _manual_marking_scene_primitives
from math import ceil, hypot, isfinite

from .sheetmetal_drawing import CirclePrimitive, DrawingScene, PolylinePrimitive
from .sheetmetal_feature_core import CircleFeature, ProfileFeature

# Interactive display only. No limit changes on loaded marks, 2D or DXF.
OWNER_MARKING_3D_PREVIEW_BUDGET = "OWNER_MARKING_STANDALONE_PREVIEW_BUDGET"
_MAX_ARTISTS = 128
_MAX_PROJECTED_POINTS = 1024
_MAX_POINT_TRIANGLE_PAIRS = 160000

_PLANE_MM = 1e-7
_PARAMETER_EPS = 1e-9


def within_standalone_marking_budget(rows, guide_count, triangle_count=0):
    """Bound exact existing projection work before geometry or artist allocation."""
    if len(rows) > _MAX_ARTISTS:
        return False
    artist_count = point_count = 0
    for row in rows:
        if isinstance(row, (CircleFeature, CirclePrimitive)):
            artist_count += 1
            point_count += 65 + 2 * guide_count
        else:
            strokes = (row.layered_profiles if isinstance(row, ProfileFeature)
                       else ((row.layer, row.points, row.closed),)
                       if isinstance(row, PolylinePrimitive) else ())
            artist_count += len(strokes)
            if artist_count > _MAX_ARTISTS:
                return False
            for _, points, _ in strokes:
                if len(points) > _MAX_PROJECTED_POINTS:
                    return False
                point_count += 1
                for start, end in zip(points, points[1:]):
                    distance = hypot(end.x - start.x, end.y - start.y)
                    if not isfinite(distance) or distance > _MAX_PROJECTED_POINTS:
                        return False
                    point_count += max(1, ceil(distance)) + guide_count
                    if point_count > _MAX_PROJECTED_POINTS:
                        return False
        if point_count > _MAX_PROJECTED_POINTS:
            return False
    return point_count * triangle_count <= _MAX_POINT_TRIANGLE_PAIRS


class _RenderedSurface:
    def __init__(self, triangles):
        import numpy as np

        self._np = np
        points = np.asarray(triangles, dtype=float)
        self.a = points[:, 0]
        self.u = points[:, 1] - self.a
        self.v = points[:, 2] - self.a
        self.n = np.cross(self.u, self.v)
        self.norm = np.linalg.norm(self.n, axis=1)
        self.uu = self._dot(self.u, self.u)
        self.uv = self._dot(self.u, self.v)
        self.vv = self._dot(self.v, self.v)

    def _dot(self, rows, other):
        return self._np.einsum("ij,ij->i", rows, other)

    def covers(self, start, end):
        np = self._np
        a, b = np.asarray(start), np.asarray(end)
        q, r = a - self.a, b - self.a
        eligible = (
            (self.norm > _PLANE_MM)
            & (np.abs(self._dot(q, self.n)) <= _PLANE_MM * self.norm)
            & (np.abs(self._dot(r, self.n)) <= _PLANE_MM * self.norm)
        )
        index = np.flatnonzero(eligible)
        if not index.size:
            return False
        u, v = self.u[index], self.v[index]
        uu, uv, vv = self.uu[index], self.uv[index], self.vv[index]
        den = self.norm[index] ** 2

        def barycentric(points):
            pu, pv = self._dot(points[index], u), self._dot(points[index], v)
            w1, w2 = (vv * pu - uv * pv) / den, (uu * pv - uv * pu) / den
            return np.stack((1 - w1 - w2, w1, w2), axis=1)

        # Every barycentric coordinate varies linearly on this coplanar
        # segment. Its nonnegative parameter interval gives exact coverage
        # by one triangle, including transitions across shared edges.
        intervals = []
        for initial, final in zip(barycentric(q), barycentric(r)):
            lo, hi = 0.0, 1.0
            for first, last in zip(initial, final):
                if min(first, last) >= -_PARAMETER_EPS:
                    continue
                if max(first, last) < -_PARAMETER_EPS:
                    hi = -1.0
                    break
                crossing = (-_PARAMETER_EPS - first) / (last - first)
                if first < -_PARAMETER_EPS:
                    lo = max(lo, crossing)
                else:
                    hi = min(hi, crossing)
            if hi >= lo:
                intervals.append((lo, hi))
        covered = 0.0
        for lo, hi in sorted(intervals):
            if lo > covered + _PARAMETER_EPS:
                break
            covered = max(hi, covered)
            if covered >= 1.0 - _PARAMETER_EPS:
                return True
        return False


def project_checked_owner_marking_standalone_paths(scene, mesh):
    """Return canonical paths, withholding unsupported saved ink as one set."""
    primitives = tuple(scene.primitives)
    manual = _manual_marking_scene_primitives(scene)
    profiles = mesh.x_profile, mesh.y_profile, mesh.fold_guides
    if not manual:
        return project_independent_scene_annotation_paths(scene, *profiles), None

    manual_ids = {id(row) for row in manual}
    original = DrawingScene([row for row in primitives if id(row) not in manual_ids])
    baseline = project_independent_scene_annotation_paths(original, *profiles)
    if not within_standalone_marking_budget(manual, len(mesh.fold_guides), len(mesh.triangles)):
        return baseline, OWNER_MARKING_3D_PREVIEW_BUDGET
    paths = project_independent_scene_annotation_paths(DrawingScene(list(manual)), *profiles)
    if len(paths) != len(manual) or not mesh.triangles:
        return baseline, "OWNER_MARKING_STANDALONE_SURFACE_UNPROVED"
    surface = _RenderedSurface(mesh.triangles)
    if not all(surface.covers(a, b) for _, path in paths for a, b in zip(path, path[1:])):
        return baseline, "OWNER_MARKING_STANDALONE_SURFACE_UNPROVED"
    return (*baseline, *paths), None
