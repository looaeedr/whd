"""Reuse immutable local meshes only within one manufacturing resolve.

World placement and collision checks still run on current inputs. No mesh survives
its owning solve, including failed or nested solves.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps

_active_meshes = ContextVar('manufacturing_local_meshes', default=None)


@contextmanager
def mesh_build_scope():
    token = _active_meshes.set({})
    try:
        yield
    finally:
        _active_meshes.reset(token)


def reuse_local_mesh(build):
    @wraps(build)
    def resolve(material, x_profile, y_profile, *, fold_exemptions=(), fold_guides=()):
        cache = _active_meshes.get()
        if cache is None:
            return build(material, x_profile, y_profile,
                         fold_exemptions=fold_exemptions, fold_guides=fold_guides)
        from .assembly_geometry_folded_mesh import _segment_value
        xp, yp = tuple(x_profile or ()), tuple(y_profile or ())
        exemptions, guides = tuple(fold_exemptions or ()), tuple(fold_guides or ())
        # Keep both length spellings: the existing profile/mask paths have
        # distinct legacy fallback rules. Do not round or normalize inputs.
        def profile_key(rows):
            return tuple(tuple(_segment_value(row, field, None)
                               for field in ('length', 'len', 'angle', 'core'))
                         for row in rows)
        key = (build, material.wkb, profile_key(xp), profile_key(yp),
               tuple((str(axis), polygon.wkb) for axis, polygon in exemptions),
               tuple((str(g.axis), float(g.position), float(g.span_start), float(g.span_end))
                     for g in guides))
        try:
            hash(key)
        except TypeError:
            # Unusual extension profile values retain the uncached contract.
            return build(material, xp, yp, fold_exemptions=exemptions, fold_guides=guides)
        if key not in cache:
            result = build(material, xp, yp, fold_exemptions=exemptions, fold_guides=guides)
            # Bound temporary memory even for unusually large assemblies.
            if len(cache) < 256:
                cache[key] = result
            return result
        return cache[key]
    return resolve
