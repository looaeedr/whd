"""Read-only display from existing owner-locked canonical marking intent."""
from dataclasses import replace

from .operator_manual_marking import OWNER_MARKING_VIEW_ONLY, _manual_marking_scene_primitives
from .operator_owner_marking_3d_view import (
    OWNER_MARKING_3D_PREVIEW_BUDGET, within_standalone_marking_budget,
)
from .operator_persisted_marking_candidate import _read_current, require_ordinary_selected_marking_stock
from .operator_quantity_marking_owner import (
    open_quantity_physical_marking, read_quantity_physical_marking, uses_quantity_physical_marking_editor,
)
from .operator_root_marking_store import read_workspace_marking_owner_record
from .operator_selected_marking_receipt import open_selected_owner_receipt, selected_normal_marking_inventory
from .sheetmetal_drawing import DrawingScene
from .workspace_state import resolve_workspace_physical_root_owner

OWNER_MARKING_VIEW_DIAGNOSTIC = "owner_marking_view_diagnostic"


def _structural_piece_display_ink(snapshot, part_key, render, resolve_geometry):
    from .operator_box_body_piece_marking import (
        box_body_piece_marking_owner, read_persisted_box_body_piece_evidence,
    )

    owner = box_body_piece_marking_owner(snapshot, part_key)
    if owner is None or read_workspace_marking_owner_record(snapshot, owner) is None:
        return ()
    if not callable(resolve_geometry):
        raise ValueError("ROOT_MARKING_CURRENT_SOURCE_REQUIRED")
    receipt, _draft, evidence = read_persisted_box_body_piece_evidence(
        snapshot, resolve_geometry(), part_key,
    )
    stock = receipt.source._render
    if (type(render) is not type(stock)
            or render.unfolded_topology != stock.unfolded_topology
            or render.material.wkb != stock.material.wkb
            or tuple(render.scene.primitives) != tuple(stock.scene.primitives)):
        raise ValueError("ROOT_MARKING_DISPLAY_SOURCE_MISMATCH")
    return evidence.ink


def project_workspace_owner_marking_display(snapshot, part_key, render, *, standalone_3d=False, resolve_geometry=None):
    """Return the view only; never alter stock, attach role features or authorize DXF."""
    if render is None:
        return None
    try:
        from .operator_box_body_piece_marking import supports_box_body_piece_marking_editor

        if not standalone_3d and supports_box_body_piece_marking_editor(snapshot, part_key):
            ink = _structural_piece_display_ink(snapshot, part_key, render, resolve_geometry)
        else:
            owner = resolve_workspace_physical_root_owner(snapshot, part_key)
            record = None if owner is None else read_workspace_marking_owner_record(snapshot, owner)
            scoped = record is None and owner is not None and uses_quantity_physical_marking_editor(snapshot, part_key)
            if scoped:
                record = read_quantity_physical_marking(snapshot, part_key)
            if record is None:
                return render
            geometry = selected_normal_marking_inventory(part_key, render)
            if scoped:
                from .operator_physical_sheet_marking_preview import project_selected_physical_marking_features
                stock_inventory = resolve_geometry() if callable(resolve_geometry) else geometry
                receipt = open_quantity_physical_marking(snapshot, stock_inventory, part_key)
                if standalone_3d and not within_standalone_marking_budget(record["features"], len(render.fold_guides)):
                    raise ValueError(OWNER_MARKING_3D_PREVIEW_BUDGET)
                ink = project_selected_physical_marking_features(
                    receipt.stock.source, record["features"], _allow_shapes=True,
                )
            elif standalone_3d and not within_standalone_marking_budget(record["features"], len(render.fold_guides)):
                # Keep the original source mismatch priority; never paint unchecked
                # data just because it is too large to replay interactively.
                require_ordinary_selected_marking_stock(snapshot, geometry, part_key)
                receipt = open_selected_owner_receipt(snapshot, geometry, part_key)
                if receipt.source_sha256 != record["source_sha256"]:
                    raise ValueError("ROOT_MARKING_SOURCE_STALE")
                raise ValueError(OWNER_MARKING_3D_PREVIEW_BUDGET)
            else:
                _receipt, _draft, evidence = _read_current(snapshot, geometry, part_key)
                ink = evidence.ink
    except ValueError as exc:
        # Old/invalid ink must not be made to look like a legal current mark.
        # Keep the actual unmarked geometry on screen with a view diagnostic.
        return replace(render, metadata={
            **render.metadata, OWNER_MARKING_VIEW_ONLY: True,
            OWNER_MARKING_VIEW_DIAGNOSTIC: str(exc),
        })
    if not ink:
        return render
    return replace(
        render, scene=DrawingScene([*render.scene.primitives, *ink]),
        metadata={**render.metadata, OWNER_MARKING_VIEW_ONLY: True},
    )


def project_scene_without_operator_marking(scene):
    """Remove only registered authored ink for display. Do not transform stock."""
    manual_ids = {id(row) for row in _manual_marking_scene_primitives(scene)}
    if not manual_ids:
        return scene
    return DrawingScene([row for row in scene.primitives if id(row) not in manual_ids])
