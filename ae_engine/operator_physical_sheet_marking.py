"""One draft/editor contract for physically sourced manual marking.

Eligibility remains with the existing source providers and ordinary DXF
admission. An editor receipt cannot authorize a manufacturing operation.
"""
from copy import deepcopy
from dataclasses import dataclass, field

from .operator_manual_marking import (
    MANUAL_MARK_SOURCE,
    create_physical_manual_marking,
    create_physical_manual_round_marking,
    is_manual_mark,
    require_first_sheet_manual_marking_render,
)
from .operator_manual_marking_groups import create_physical_manual_marking_group
from .operator_scoped_base_plate_marks import (
    open_scoped_base_plate_editor,
    commit_scoped_base_plate_marks,
)
from .physical_sheet_editor_context import (
    PhysicalSheetEditorContext,
    propose_operator_physical_sheet_hole_features,
    resolve_physical_sheet_editor_context,
)

_ORDINARY_TOOLS = ("line", "circle", "cross", "l", "pair_l", "quad_l")


@dataclass(frozen=True)
class PhysicalSheetMarkingDraft:
    context: PhysicalSheetEditorContext
    owner_id: str
    allowed_tools: tuple[str, ...]
    features: tuple
    _source: tuple = field(repr=False)
    _selection: object = field(default=None, repr=False)
    _snapshot: object = field(default=None, repr=False, compare=False)

    @property
    def saved_marks(self):
        return tuple(row for row in self.features if is_manual_mark(row))


@dataclass(frozen=True)
class PhysicalSheetMarkingUpdate:
    features: tuple
    scoped_store: dict | None = None


def _source(context):
    render = context.render_data
    return (context.part_key, context.width, context.height, context.reference_guide,
            context.feature_surface.polygon.wkb, render.unfolded_topology,
            tuple(render.fold_guides), tuple(render.scene.primitives), render.material.wkb)


def open_physical_sheet_marking(part_key, *, context=None, features=(),
                                snapshot=None, selection=None, expected_owner=None,
                                geometry=None):
    """Bind current stock; a scoped owner witness only rejects a mismatch."""
    if geometry is not None:
        if selection is not None or expected_owner is not None or context is not None or features:
            raise ValueError("PHYSICAL_SHEET_MARKING_SELECTION_UNSUPPORTED")
        from .operator_selected_marking_receipt import open_selected_owner_receipt
        return open_selected_owner_receipt(snapshot, geometry, part_key)
    if selection is not None:
        if (part_key != "base_plate" or context is not None or features
                or not isinstance(snapshot, dict)
                or not isinstance(selection, (tuple, list)) or len(selection) != 2):
            raise ValueError("PHYSICAL_SHEET_MARKING_SELECTION_UNSUPPORTED")
        snapshot = deepcopy(snapshot)
        scoped = open_scoped_base_plate_editor(
            snapshot, *selection, expected_owner=expected_owner,
        )
        return PhysicalSheetMarkingDraft(
            scoped.context, scoped.owner, ("line",), scoped.saved_marks,
            _source(scoped.context), scoped, snapshot,
        )
    if (snapshot is not None or expected_owner is not None
            or not isinstance(context, PhysicalSheetEditorContext)):
        raise ValueError("PHYSICAL_SHEET_MARKING_SOURCE_UNSUPPORTED")
    if context.part_key != part_key:
        raise ValueError("PHYSICAL_SHEET_MARKING_PART_MISMATCH")
    render = require_first_sheet_manual_marking_render(part_key, context.render_data)
    canonical = resolve_physical_sheet_editor_context(part_key, render)
    if _source(context) != _source(canonical):
        raise ValueError("PHYSICAL_SHEET_MARKING_CONTEXT_MISMATCH")
    return PhysicalSheetMarkingDraft(
        canonical, render.metadata["stable_id"], _ORDINARY_TOOLS,
        tuple(deepcopy(tuple(features))), _source(canonical),
    )


def _require_draft(draft):
    if not isinstance(draft, PhysicalSheetMarkingDraft):
        raise ValueError("PHYSICAL_SHEET_MARKING_DRAFT_REQUIRED")
    ctx = draft.context
    require_first_sheet_manual_marking_render(ctx.part_key, ctx.render_data)
    if _source(ctx) != draft._source:
        raise ValueError("PHYSICAL_SHEET_MARKING_SOURCE_STALE")
    return ctx


def validate_physical_sheet_marking_draft(draft, features):
    """Use the same existing full-stroke/material/hole validator for all receipts."""
    from .operator_selected_marking_receipt import SelectedPhysicalMarkingReceipt
    if isinstance(draft, SelectedPhysicalMarkingReceipt) and draft.output_capability == "verified_normal":
        from .operator_manual_marking import is_manual_mark
        parts = tuple(features)
        role_rows = tuple(row for row in parts if not is_manual_mark(row))
        accepted_role = propose_operator_physical_sheet_hole_features(draft.part_key, draft.context, role_rows)
        marks = draft.validate(tuple(row for row in parts if is_manual_mark(row)))
        return (*accepted_role, *marks)
    ctx = _require_draft(draft)
    checked = propose_operator_physical_sheet_hole_features(ctx.part_key, ctx, features)
    if draft._selection is not None and any(
        getattr(row, "source_type", None) != MANUAL_MARK_SOURCE for row in checked
    ):
        raise ValueError("SCOPED_MARK_LEDGER_STRAIGHT_MARK_ONLY")
    return checked


def create_physical_sheet_mark(draft, features, *, tool="line", **raw):
    """Produce a single candidate; the caller's draft and storage are untouched."""
    from .operator_selected_marking_receipt import SelectedPhysicalMarkingReceipt
    if isinstance(draft, SelectedPhysicalMarkingReceipt) and draft.output_capability == "verified_normal":
        from .operator_manual_marking import is_manual_mark
        if tool != "line" or raw.get("pattern", "solid") != "solid":
            raise ValueError("PHYSICAL_SHEET_MARKING_TOOL_UNSUPPORTED")
        return draft.create(
            tuple(row for row in features if is_manual_mark(row)),
            midpoint=raw["midpoint"], length=raw["length"], angle_deg=raw["angle_deg"],
        )
    ctx = _require_draft(draft)
    if tool not in draft.allowed_tools:
        raise ValueError("PHYSICAL_SHEET_MARKING_TOOL_UNSUPPORTED")
    rows = validate_physical_sheet_marking_draft(draft, features)
    if tool == "line":
        return create_physical_manual_marking(ctx.part_key, ctx, rows, **raw)
    if tool == "circle":
        return create_physical_manual_round_marking(ctx.part_key, ctx, rows, **raw)
    return create_physical_manual_marking_group(ctx.part_key, ctx, rows, kind=tool, **raw)


def commit_physical_sheet_marking(current, opened, features):
    """Compare freshly resolved receipt and return an existing transport update."""
    _require_draft(opened)
    _require_draft(current)
    if (current.owner_id != opened.owner_id
            or current.allowed_tools != opened.allowed_tools
            or (current._selection is None) != (opened._selection is None)):
        raise ValueError("PHYSICAL_SHEET_MARKING_OWNER_STALE")
    if current._source != opened._source or current.features != opened.features:
        raise ValueError("PHYSICAL_SHEET_MARKING_SOURCE_STALE")
    rows = validate_physical_sheet_marking_draft(current, features)
    if current._selection is None:
        return PhysicalSheetMarkingUpdate(rows)
    store = commit_scoped_base_plate_marks(current._snapshot, opened._selection, rows)
    return PhysicalSheetMarkingUpdate(rows, store)


def propose_legacy_root_occupancy_for_mark_confirm(
    snapshot, *, selected_spec, manufacturing_context, current, opened, features,
):
    """Detached first-mark owner proposal; no store, UI or DXF authority mutation.

    Consumers must obtain the fresh receipt from the actual selected root and
    recheck the project/session at their eventual atomic commit. An ordinary
    copy of a context alone is not a durable project owner.
    """
    from collections.abc import Mapping
    from .workspace_state import (
        SharedWorkspaceState, ROOT_PHYSICAL_OCCUPANCY_KEY,
        normalize_workspace_root_occupancy,
    )
    if (not isinstance(snapshot, Mapping) or not isinstance(current, PhysicalSheetMarkingDraft)
            or current._selection is not None):
        raise ValueError("PHYSICAL_ROOT_MARK_CONFIRM_SOURCE_REQUIRED")
    update = commit_physical_sheet_marking(current, opened, features)
    key = current.context.part_key
    if not any(is_manual_mark(row) for row in update.features):
        raise ValueError("PHYSICAL_ROOT_FIRST_MARK_REQUIRED")
    nested = snapshot.get("workspace")
    nested = nested if isinstance(nested, Mapping) else {}
    parts = snapshot.get("existing_parts", nested.get("existing_parts", ()))
    if key not in (parts or ()):
        raise ValueError("PHYSICAL_ROOT_MARK_CONFIRM_SOURCE_REQUIRED")
    from .cabinet_types.policy import canonical_family_name
    from .manufacturing_api import build_part_render_data
    family = canonical_family_name(snapshot.get("model"))
    selected_family = canonical_family_name(getattr(selected_spec, "model_name", None))
    if not family or family != selected_family:
        raise ValueError("PHYSICAL_ROOT_MARK_CONFIRM_SOURCE_REQUIRED")
    # Rebuild from the selected typed source with the existing canonical
    # engine, not from GUI geometry, and compare the same full material
    # witness against the freshly resolved editor receipt.
    canonical = resolve_physical_sheet_editor_context(
        key, build_part_render_data(selected_spec, manufacturing_context),
    )
    if _source(canonical) != current._source:
        raise ValueError("PHYSICAL_ROOT_MARK_CONFIRM_SOURCE_STALE")
    existing = normalize_workspace_root_occupancy(
        snapshot.get(ROOT_PHYSICAL_OCCUPANCY_KEY, nested.get(ROOT_PHYSICAL_OCCUPANCY_KEY)),
        existing_parts=parts, model=family,
    )
    if key in existing:
        return existing
    return SharedWorkspaceState(
        existing_parts=parts, root_occupancy=existing,
        custom_parts=snapshot.get("custom_parts", nested.get("custom_parts")),
    )._propose_marked_legacy_root(key, family)
