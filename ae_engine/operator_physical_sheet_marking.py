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
                                snapshot=None, selection=None, expected_owner=None):
    """Bind current stock; a scoped owner witness only rejects a mismatch."""
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
    ctx = _require_draft(draft)
    checked = propose_operator_physical_sheet_hole_features(ctx.part_key, ctx, features)
    if draft._selection is not None and any(
        getattr(row, "source_type", None) != MANUAL_MARK_SOURCE for row in checked
    ):
        raise ValueError("SCOPED_MARK_LEDGER_STRAIGHT_MARK_ONLY")
    return checked


def create_physical_sheet_mark(draft, features, *, tool="line", **raw):
    """Produce a single candidate; the caller's draft and storage are untouched."""
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
