"""Display owner ink only when the installed assembly surface is unambiguous."""
from collections import Counter

from .assembly_geometry_primitives import place_assembly_points, place_assembly_triangles
from .independent_part_view_mesh import IndependentPartViewMesh
from .operator_manual_marking import OWNER_MARKING_VIEW_ONLY
from .operator_owner_marking_3d_view import _RenderedSurface, project_checked_owner_marking_standalone_paths
from .operator_owner_marking_view import (
    OWNER_MARKING_VIEW_DIAGNOSTIC,
    project_workspace_owner_marking_display,
)
from .sheetmetal_drawing import DrawingScene

_HELD = "OWNER_MARKING_ASSEMBLY_SURFACE_UNPROVED"


def project_workspace_owner_marking_assembly_views(snapshot, parts, visible_keys):
    """Keep raw assembly parts untouched; look up only visible current owners."""
    visible = None if visible_keys is None else frozenset(visible_keys)
    parts = tuple(parts)
    counts = Counter(part.part_key for part in parts)
    rows = []
    for part in parts:
        if counts[part.part_key] != 1 or (visible is not None and part.part_key not in visible):
            continue
        render = project_workspace_owner_marking_display(
            snapshot, part.part_key, part.render_data, standalone_3d=True,
        )
        if render is not part.render_data:
            rows.append((part.part_key, render))
    return tuple(rows)


def project_checked_owner_marking_assembly_paths(part, view, local, installed, dimensions):
    """Only the exact existing generic map and actual painted skin can admit ink.

    EndCap semantic placement is a different transform and has two physical
    skins. A 2D owner feature does not yet designate a world face on it.
    """
    meta = getattr(view, "metadata", None) or {}
    if not meta.get(OWNER_MARKING_VIEW_ONLY):
        return (), _HELD
    if meta.get(OWNER_MARKING_VIEW_DIAGNOSTIC):
        return (), meta[OWNER_MARKING_VIEW_DIAGNOSTIC]
    stock = part.render_data
    original = tuple(stock.scene.primitives)
    current = tuple(view.scene.primitives)
    if (current[:len(original)] != original or view.material is not stock.material
            or view.fold_guides != stock.fold_guides
            or view.unfolded_topology != stock.unfolded_topology):
        return (), _HELD
    placement = str(part.placement).lower()
    # The nominal Center/Offset mapper has no authority over distinct world
    # skins, including a temporarily missing BoxBody mating source.
    if placement in {"top", "head", "bottom", "tail"} or not installed:
        return (), _HELD
    if tuple(installed) != place_assembly_triangles(local, placement, dimensions, part.offset):
        return (), _HELD
    mesh = IndependentPartViewMesh(tuple(local), part.x_profile, part.y_profile, stock.fold_guides)
    rows, warning = project_checked_owner_marking_standalone_paths(
        DrawingScene(list(current[len(original):])), mesh,
    )
    if warning:
        return (), warning
    coords = tuple(point for _layer, path in rows for point in path)
    world = place_assembly_points(coords, local, placement, dimensions, part.offset)
    if len(world) != len(coords):
        return (), _HELD
    result = []
    surface = _RenderedSurface(installed)
    start = 0
    for layer, path in rows:
        end = start + len(path)
        placed = world[start:end]
        if not all(surface.covers(a, b) for a, b in zip(placed, placed[1:])):
            return (), _HELD
        result.append((layer, placed))
        start = end
    return tuple(result), None
