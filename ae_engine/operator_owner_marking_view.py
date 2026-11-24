"""Read-only display from existing owner-locked canonical marking intent."""
from dataclasses import replace

from .operator_manual_marking import OWNER_MARKING_VIEW_ONLY
from .operator_persisted_marking_candidate import _read_current
from .operator_root_marking_store import read_workspace_marking_owner_record
from .operator_selected_marking_receipt import selected_normal_marking_inventory
from .sheetmetal_drawing import DrawingScene
from .workspace_state import resolve_workspace_physical_root_owner

OWNER_MARKING_VIEW_DIAGNOSTIC = "owner_marking_view_diagnostic"


def project_workspace_owner_marking_display(snapshot, part_key, render):
    """Return the view only; never alter stock, attach role features or authorize DXF."""
    if render is None:
        return None
    try:
        owner = resolve_workspace_physical_root_owner(snapshot, part_key)
        if owner is None or read_workspace_marking_owner_record(snapshot, owner) is None:
            return render
        geometry = selected_normal_marking_inventory(part_key, render)
        _receipt, _draft, evidence = _read_current(snapshot, geometry, part_key)
    except ValueError as exc:
        # Old/invalid ink must not be made to look like a legal current mark.
        # Keep the actual unmarked geometry on screen with a view diagnostic.
        return replace(render, metadata={
            **render.metadata, OWNER_MARKING_VIEW_ONLY: True,
            OWNER_MARKING_VIEW_DIAGNOSTIC: str(exc),
        })
    if not evidence.ink:
        return render
    return replace(
        render, scene=DrawingScene([*render.scene.primitives, *evidence.ink]),
        metadata={**render.metadata, OWNER_MARKING_VIEW_ONLY: True},
    )
