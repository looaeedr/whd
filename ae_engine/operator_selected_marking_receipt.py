"""Isolated receipt proof: selected stock + current durable owner.

No persistence or new export eligibility. A checked new draft can be staged
only in the existing ordinary single-LEFT marking lane, in one transaction.
Historical role-only marks are never rebound to a newly observed owner.
"""
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field, replace
from hashlib import sha256
import json

from .cabinet_types.policy import canonical_family_name
from .manufacturing_equivalence import ManufacturingParameters, manufacturing_equivalence_payload
from .sheetmetal_drawing import DrawingScene

from .operator_manual_marking import (
    first_sheet_manual_marking_supported, is_manual_mark,
)
from .operator_manual_marking_batch import _has_saved_manual_intent
from .operator_physical_sheet_marking_preview import (
    _validate_selected_marks,
    create_selected_physical_mark,
    validate_selected_physical_marks,
    open_selected_physical_marking_preview,
    project_selected_physical_marking_preview,
)
from .operator_scoped_base_plate_marks import (
    require_scoped_base_plate_export_held,
)
from .workspace_state import resolve_workspace_physical_root_owner


@dataclass(frozen=True)
class SelectedPhysicalMarkingReceipt:
    part_key: str
    owner_id: str | None
    source: object
    output_capability: str
    source_sha256: str
    _normal_draft: object = field(default=None, repr=False)

    @property
    def allowed_tools(self):
        if self.output_capability in {"existing_normal", "verified_normal"}:
            from .operator_physical_sheet_marking import _ORDINARY_TOOLS
            return _ORDINARY_TOOLS
        return ("line",)

    @property
    def context(self):
        from .physical_sheet_editor_context import resolve_physical_sheet_editor_context
        return resolve_physical_sheet_editor_context(self.part_key, self.source._render)

    @property
    def modal_draft(self):
        return self._normal_draft

    def create(self, features, **stroke):
        return create_selected_physical_mark(self.source, features, **stroke)

    def validate(self, features):
        if self.output_capability == "existing_normal" and self._normal_draft is not None:
            from .operator_physical_sheet_marking import validate_physical_sheet_marking_draft
            result = validate_physical_sheet_marking_draft(self._normal_draft, features)
            if not all(is_manual_mark(row) for row in result):
                raise ValueError("ROOT_MARKING_STORE_MARKS_ONLY")
            return result
        if self.output_capability == "verified_normal":
            return _validate_selected_marks(self.source, features, allow_shapes=True)
        return validate_selected_physical_marks(self.source, features)

    def project(self, **stroke):
        return project_selected_physical_marking_preview(self.source, **stroke)


def _part_features(snapshot, key):
    nested = snapshot.get("workspace") or {}
    return tuple((snapshot.get("part_features", nested.get("part_features")) or {}).get(key, ()))


def _ordinary_normal_source(snapshot, key, render):
    if (canonical_family_name(snapshot) != "受電箱"
            or snapshot.get("active_mode", "set_bay") != "set_bay"
            or snapshot.get("receiving_quantity_box")
            or snapshot.get("v_miter_gui_check_corners")
            or snapshot.get("v_miter_endcap_live_check_sources")
            or not first_sheet_manual_marking_supported(key, render)):
        return False
    if snapshot.get("receiving_layout") is not None:
        from .receiving_layout import normalize_receiving_layout
        layout = normalize_receiving_layout(snapshot["receiving_layout"])
        if len(layout["sets"]) != 1 or len(layout["sets"][0]["bays"]) != 1:
            return False
    require_scoped_base_plate_export_held(snapshot, {key: True})
    return True


def _source_sha256(snapshot, selected):
    render = selected._render
    # Store only physical stock/hole/bend authority, no UI annotations,
    # preview ink, output eligibility flag or transient WKB ring ordering.
    records = DrawingScene([p for p in render.scene.primitives
                            if p.layer in {"CUTTING", "BEND", "BLIND_HOLE"}])
    payload = manufacturing_equivalence_payload(
        replace(render, scene=records),
        ManufacturingParameters("physical_marking_stock_v1", snapshot["t"], None),
    )
    topology = render.unfolded_topology
    physical = json.dumps({
        "family": canonical_family_name(snapshot),
        "part_key": selected.selected_key,
        "material": payload,
        "topology": asdict(topology) if topology is not None else None,
        "fold_guides": sorted(
            (row.axis, row.position, row.span_start, row.span_end)
            for row in selected.fold_guides
        ),
    }, sort_keys=True, separators=(",", ":"))
    return sha256(physical.encode("utf-8")).hexdigest()


def _existing_normal_marking_draft(snapshot, key, render):
    from .physical_sheet_editor_context import resolve_physical_sheet_editor_context
    from .operator_physical_sheet_marking import open_physical_sheet_marking

    if not _ordinary_normal_source(snapshot, key, render):
        return None
    if _has_saved_manual_intent(render) or any(is_manual_mark(f) for f in _part_features(snapshot, key)):
        raise ValueError("PHYSICAL_MARKING_LEGACY_ROLE_MARKS_UNBOUND")
    return open_physical_sheet_marking(
        key, context=resolve_physical_sheet_editor_context(key, render),
    )


def open_selected_owner_receipt(snapshot, geometry, key):
    if not isinstance(snapshot, Mapping):
        raise ValueError("PHYSICAL_MARKING_PROJECT_REQUIRED")
    owner = resolve_workspace_physical_root_owner(snapshot, key)
    if owner is None:
        raise ValueError("PHYSICAL_MARKING_DURABLE_OWNER_REQUIRED")
    selected = open_selected_physical_marking_preview(geometry, key)
    normal = _existing_normal_marking_draft(snapshot, key, selected._render)
    return SelectedPhysicalMarkingReceipt(
        key, owner, selected, "existing_normal" if normal else "check_only",
        _source_sha256(snapshot, selected), normal,
    )


def prepare_confirmed_selected_marking(receipt, marks, read_current):
    """Return canonical render + atomic guard for the existing verified sink."""
    from .operator_physical_sheet_marking import commit_physical_sheet_marking
    from .physical_sheet_features import with_physical_sheet_features

    if (not isinstance(receipt, SelectedPhysicalMarkingReceipt)
            or receipt.output_capability != "existing_normal" or receipt._normal_draft is None):
        raise ValueError("PHYSICAL_MARKING_NORMAL_OUTPUT_UNSUPPORTED")
    if not callable(read_current):
        raise TypeError("PHYSICAL_MARKING_CURRENT_SOURCE_REQUIRED")

    def current_receipt():
        snapshot, geometry = read_current()
        # Fail for replaced owner before evaluating the new material or marks.
        if resolve_workspace_physical_root_owner(snapshot, receipt.part_key) != receipt.owner_id:
            raise ValueError("PHYSICAL_MARKING_OWNER_STALE")
        current = open_selected_owner_receipt(snapshot, geometry, receipt.part_key)
        if (current.output_capability != "existing_normal"
                or current.source != receipt.source):
            raise ValueError("PHYSICAL_MARKING_SOURCE_STALE")
        return current

    current = current_receipt()
    accepted = commit_physical_sheet_marking(current._normal_draft, receipt._normal_draft, marks)
    if not accepted.features or not all(is_manual_mark(f) for f in accepted.features):
        raise ValueError("PHYSICAL_MARKING_CONFIRMED_MARKS_REQUIRED")
    features = current.validate(accepted.features)
    result = with_physical_sheet_features(
        receipt.part_key, current.source._render, features,
    )
    return result, current_receipt


def open_selected_ordinary_marking_modal_source(snapshot, geometry, key):
    """The same authorized unmarked stock gate used by the persisted writer."""
    from .operator_persisted_marking_candidate import require_ordinary_selected_marking_stock, _verify_original
    from .workspace_state import _ordinary_explicit_root_key

    if not _ordinary_explicit_root_key(key, snapshot):
        raise ValueError("PHYSICAL_MARKING_NORMAL_OUTPUT_UNSUPPORTED")
    selected = require_ordinary_selected_marking_stock(snapshot, geometry, key)
    normal = _existing_normal_marking_draft(snapshot, key, selected._render)
    if normal is None:
        # Exact existing ordinary proof, never a nominal/palette grant.
        _verify_original(selected._render)
    return SelectedPhysicalMarkingReceipt(
        key, resolve_workspace_physical_root_owner(snapshot, key), selected,
        "existing_normal" if normal is not None else "verified_normal",
        _source_sha256(snapshot, selected), normal,
    )


def selected_normal_marking_inventory(part_key, render):
    """Adapt the original selected single-part canonical renderer, not a new solver."""
    from .contracts import ResolvedManufacturingGeometry, ResolvedManufacturingPart
    # This is inventory transport only. The standard receipt below still owns
    # source, material, process, owner and existing-normal capability checks.
    return ResolvedManufacturingGeometry((ResolvedManufacturingPart(part_key, render),))
