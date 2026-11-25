"""Persisted normal single-selected marking authority, never a second writer.

Read canonical saved ink, prove original ordinary stock through the existing
verified writer, then witness one guarded ordinary stage if explicitly selected.
"""
from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from tempfile import TemporaryDirectory

from .operator_manual_marking_batch import _has_saved_manual_intent
from .operator_root_marking_store import open_workspace_owner_marking_draft
from .operator_physical_sheet_marking_preview import project_selected_physical_marking_features
from .sheetmetal_drawing import DrawingScene


@dataclass(frozen=True)
class VerifiedOwnerMarkingCandidate:
    part_key: str
    owner_id: str
    source_sha256: str
    ink: tuple
    legacy_normal_marking_allowed: bool


def _vault_single_quantity(snapshot):
    from .receiving_quantity_versions import QuantityModel

    try:
        quantity = QuantityModel.from_payload(snapshot.get("quantity"))
    except ValueError as exc:
        raise ValueError("OWNER_MARKING_SINGLE_NORMAL_SCOPE_REQUIRED") from exc
    if quantity.version_count != 1:
        raise ValueError("OWNER_MARKING_SINGLE_NORMAL_SCOPE_REQUIRED")
    return quantity.selected_version_id, quantity.selected_piece_count


def require_ordinary_selected_marking_stock(snapshot, geometry, part_key):
    """Pure stock/source/owner/ink checks before any single marked stage."""
    from . import manufacturing_api as api
    from .cabinet_types.policy import canonical_family_name
    from .manufacturing_export import resolved_physical_render_parts
    from .operator_scoped_base_plate_marks import require_scoped_base_plate_export_held
    from .receiving_layout import normalize_receiving_layout

    if (not isinstance(snapshot, Mapping)
            or snapshot.get("receiving_quantity_box")
            or snapshot.get("v_miter_gui_check_corners")
            or snapshot.get("v_miter_endcap_live_check_sources")):
        raise ValueError("OWNER_MARKING_SINGLE_NORMAL_SCOPE_REQUIRED")
    mode = snapshot.get("active_mode", "set_bay")
    if mode == "quantity" and canonical_family_name(snapshot) == "金庫型":
        _vault_single_quantity(snapshot)
    elif mode != "set_bay":
        raise ValueError("OWNER_MARKING_SINGLE_NORMAL_SCOPE_REQUIRED")
    if snapshot.get("receiving_layout") is not None:
        layout = normalize_receiving_layout(snapshot["receiving_layout"])
        if len(layout["sets"]) != 1 or len(layout["sets"][0]["bays"]) != 1:
            raise ValueError("OWNER_MARKING_SINGLE_NORMAL_SCOPE_REQUIRED")
    require_scoped_base_plate_export_held(snapshot, {part_key: True})

    selected = api.open_selected_physical_marking_preview(geometry, part_key)
    render = selected._render
    normal_rows = [row for key, row in resolved_physical_render_parts(geometry)
                   if key == part_key]
    if len(normal_rows) != 1 or normal_rows[0] is not render:
        raise ValueError("OWNER_MARKING_ORDINARY_PHYSICAL_SOURCE_REQUIRED")
    if _has_saved_manual_intent(render):
        raise ValueError("OWNER_MARKING_UNMARKED_BASELINE_REQUIRED")
    api.require_verified_operator_baseline_sources(canonical_family_name(snapshot))
    api._require_single_part_dxf_source(render)
    return selected


def _read_current(snapshot, geometry, part_key):
    from . import manufacturing_api as api
    require_ordinary_selected_marking_stock(snapshot, geometry, part_key)
    receipt = api.open_physical_sheet_marking(part_key, snapshot=snapshot, geometry=geometry)
    if receipt.output_capability == "check_only":
        # Here the ordinary selected stock gate above has already passed;
        # publication still additionally requires _verify_original.
        receipt = replace(receipt, output_capability="verified_normal")
    draft = open_workspace_owner_marking_draft(snapshot, receipt)
    if not draft.saved_marks:
        raise ValueError("OWNER_MARKING_PERSISTED_RECORD_REQUIRED")

    # Resolve the audited typed intent through the existing physical feature
    # path. Nothing here changes the source scene, material, folds or inventory.
    if receipt.output_capability == "existing_normal":
        from .physical_sheet_features import with_physical_sheet_features
        original = tuple(receipt.source._render.scene.primitives)
        marked = with_physical_sheet_features(part_key, receipt.source._render, draft.saved_marks)
        if tuple(marked.scene.primitives[:len(original)]) != original:
            raise ValueError("OWNER_MARKING_SELECTED_INK_CHANGED")
        ink = tuple(marked.scene.primitives[len(original):])
    else:
        ink = project_selected_physical_marking_features(
            receipt.source, draft.saved_marks, _allow_shapes=True,
        )
    return receipt, draft, VerifiedOwnerMarkingCandidate(
        part_key, receipt.owner_id, receipt.source_sha256, ink,
        receipt.output_capability == "existing_normal",
    )


def _verify_original(source):
    from . import manufacturing_api as api
    # This runs the established ordinary staged writer/acceptance before any
    # marked output. Scratch is internal and disappears with the receipt.
    with TemporaryDirectory(prefix="whd-ordinary-stock-proof-") as folder:
        try:
            api.save_part_render_data_dxf(
                source, Path(folder) / "ordinary-source.dxf", verify_reopen=True,
            )
        except ValueError as exc:
            raise ValueError("OWNER_MARKING_ORDINARY_READBACK_FAILED: " + str(exc)) from exc


def read_verified_owner_marking_candidate(snapshot, geometry, part_key):
    """Read existing ordinary physical authority and validated persisted ink."""
    receipt, _draft, evidence = _read_current(snapshot, geometry, part_key)
    _verify_original(receipt.source._render)
    return evidence


class _SingleSelectedOwnerMarkingWitness:
    """Single existing verified-writer invocation; never batch authorization."""

    def __init__(self, receipt, draft, evidence, read_current):
        self._evidence = evidence
        self._read = read_current
        self._marks = draft.saved_marks
        source = receipt.source._render
        self._untouched = tuple(source.scene.primitives)
        self._physical_stock = (source.material.wkb, tuple(source.fold_guides), source.unfolded_topology)
        self.selected = (evidence.owner_id,)
        self.render = replace(
            source, scene=DrawingScene([*self._untouched, *evidence.ink]),
        )

    def assert_render(self, render):
        if (render is not self.render
                or tuple(render.scene.primitives) != self._untouched + self._evidence.ink
                or (render.material.wkb, tuple(render.fold_guides), render.unfolded_topology) != self._physical_stock):
            raise ValueError("OWNER_MARKING_SELECTED_INK_CHANGED")

    def assert_verified_rows(self, rows):
        if len(rows) != 1 or rows[0][0] != self._evidence.owner_id:
            raise ValueError("OWNER_MARKING_SINGLE_NORMAL_SCOPE_REQUIRED")
        self.assert_render(rows[0][2])

    def assert_current(self, current_source=None):
        from .workspace_state import resolve_workspace_physical_root_owner
        snapshot, geometry = self._read() if current_source is None else current_source
        if resolve_workspace_physical_root_owner(snapshot, self._evidence.part_key) != self._evidence.owner_id:
            raise ValueError("ROOT_MARKING_OWNER_STALE")
        receipt, draft, candidate = _read_current(snapshot, geometry, self._evidence.part_key)
        if (candidate != self._evidence or draft.saved_marks != self._marks
                or tuple(receipt.source._render.scene.primitives) != self._untouched):
            raise ValueError("ROOT_MARKING_SOURCE_STALE")
        self.assert_render(self.render)


def _prepare_single_selected_owner_marking(part_key, read_current):
    if not callable(read_current):
        raise TypeError("PHYSICAL_MARKING_CURRENT_SOURCE_REQUIRED")
    snapshot, geometry = read_current()
    receipt, draft, evidence = _read_current(snapshot, geometry, part_key)
    _verify_original(receipt.source._render)
    witness = _SingleSelectedOwnerMarkingWitness(receipt, draft, evidence, read_current)
    witness.assert_current()
    return witness

def _selected_render_signature(render):
    return (
        tuple(render.scene.primitives), render.material.wkb,
        tuple(render.fold_guides), render.unfolded_topology,
    )


class _SelectedOwnerMarkingBatchWitness:
    """The same per-owner witness for each marked row, one live batch source."""

    def __init__(self, selected, owner_rows, legacy, flags, read_current):
        self._ordinary = tuple((key, _selected_render_signature(render)) for key, render in selected)
        self._owners = dict(owner_rows)
        self.selected = tuple(self._owners)
        self._legacy = legacy
        self._flags = dict(flags)
        self._read = read_current

    def owner_row(self, key):
        return self._owners.get(key)

    def assert_verified_rows(self, rows):
        if tuple(str(row[0]) for row in rows) != tuple(key for key, _ in self._ordinary):
            raise ValueError("OWNER_MARKING_ORDINARY_BATCH_INVENTORY_CHANGED")
        for key, _, render in rows:
            witness = self.owner_row(key)
            if witness is not None:
                witness.assert_render(render)

    def assert_current(self, current_source=None):
        from .manufacturing_export import resolved_physical_render_parts
        from .manufacturing_export_selection import select_resolved_export_geometry
        from .operator_root_marking_store import selected_workspace_owner_marking_keys
        source = self._read() if current_source is None else current_source
        snapshot, geometry = source
        # Owner mismatch retains priority over physical signature drift.
        for witness in self._owners.values():
            witness.assert_current(source)
        if set(selected_workspace_owner_marking_keys(snapshot, self._flags)) != set(self._owners):
            raise ValueError("ROOT_MARKING_OWNER_SELECTION_STALE")
        rows = tuple((key, _selected_render_signature(render)) for key, render in
                     resolved_physical_render_parts(select_resolved_export_geometry(geometry, self._flags)))
        if rows != self._ordinary:
            raise ValueError("OWNER_MARKING_ORDINARY_BATCH_SOURCE_CHANGED")
        self._legacy.assert_current()


def _prepare_selected_ordinary_marking_batch(expected_snapshot, resolved, flags, owner_keys, read_current):
    """Read one live canonical snapshot and use the original per-sheet proof."""
    from .manufacturing_export import resolved_physical_render_parts
    from .manufacturing_export_selection import select_resolved_export_geometry
    from .operator_manual_marking_batch import witness_selected_manual_marking_rows
    from .operator_root_marking_store import read_workspace_marking_owner_record
    from .workspace_state import resolve_workspace_physical_root_owner

    if not callable(read_current):
        raise ValueError("PHYSICAL_MARKING_CURRENT_SOURCE_REQUIRED")
    snapshot, geometry = read_current()
    rows = tuple(resolved_physical_render_parts(select_resolved_export_geometry(resolved, flags)))
    owner_results = []
    for key in owner_keys:
        expected_owner = resolve_workspace_physical_root_owner(expected_snapshot, key)
        if resolve_workspace_physical_root_owner(snapshot, key) != expected_owner:
            raise ValueError("ROOT_MARKING_OWNER_STALE")
        if (read_workspace_marking_owner_record(expected_snapshot, expected_owner)
                != read_workspace_marking_owner_record(snapshot, expected_owner)):
            raise ValueError("ROOT_MARKING_SAVED_RECORD_STALE")
        receipt, draft, evidence = _read_current(snapshot, geometry, key)
        _verify_original(receipt.source._render)
        owner_results.append((key, _SingleSelectedOwnerMarkingWitness(receipt, draft, evidence, read_current)))
    if not owner_keys or not set(owner_keys).issubset({key for key, _ in rows}):
        raise ValueError("OWNER_MARKING_ORDINARY_BATCH_INVENTORY_CHANGED")
    if len({w._evidence.owner_id for _, w in owner_results}) != len(owner_results):
        raise ValueError("OWNER_MARKING_ORDINARY_BATCH_DUPLICATE_OWNER")
    legacy = witness_selected_manual_marking_rows((key, render) for key, render in rows if key not in owner_keys)
    witness = _SelectedOwnerMarkingBatchWitness(rows, owner_results, legacy, flags, read_current)
    witness.assert_current()
    return rows, witness


class _VaultQuantityOwnerWitness(_SelectedOwnerMarkingBatchWitness):
    """Bind every grouped flat, including unmarked companions, to the live batch."""

    def __init__(self, source_witness, rows, marked, read_current, version_scope):
        self._source = source_witness
        self._read = read_current
        self._version_scope = version_scope
        self._rows = tuple((key, filename, render, _selected_render_signature(render))
                           for key, filename, render in rows)
        self._by_render = {id(row[2]): row[3] for row in self._rows}
        self._marked = frozenset(id(render) for render in marked)
        self.selected = source_witness.selected

    def is_marked(self, render):
        return id(render) in self._marked

    def assert_render(self, render):
        if self._by_render.get(id(render)) != _selected_render_signature(render):
            raise ValueError("OWNER_MARKING_QUANTITY_FLAT_CHANGED")

    def assert_verified_rows(self, rows):
        if tuple((key, filename, id(render)) for key, filename, render in rows) != tuple(
                (key, filename, id(render)) for key, filename, render, _ in self._rows):
            raise ValueError("OWNER_MARKING_QUANTITY_INVENTORY_CHANGED")
        for _, _, render in rows:
            self.assert_render(render)

    def assert_current(self):
        current = self._read()
        if self._version_scope is not None and (
                current[0].get("active_mode") != "quantity"
                or _vault_single_quantity(current[0]) != self._version_scope):
            raise ValueError("OWNER_MARKING_QUANTITY_VERSION_SOURCE_MISMATCH")
        self._source.assert_current(current)
        for _, _, render, _ in self._rows:
            self.assert_render(render)


def _stage_vault_quantity_owner(
    batch, workspace, flags, directory, snapshot, owner_keys, read_current, sink,
):
    """Bind confirmed marks to their exact physical owners in one Vault version."""
    from . import manufacturing_api as api
    from .cabinet_types.policy import canonical_family_name
    from .drawing_annotation_layout import annotate_quantity_render_data
    from .dxf_serialization import verify_quantity_check_dxf
    from .manufacturing_export import _save_resolved_rows_atomic, save_part_render_data_dxf
    from .quantity_manufacturing_groups import quantity_manufacturing_groups
    from .receiving_nfb_quantity_partial import (
        QuantityOperatorStagedExport, plan_quantity_operator_export_selection,
    )

    if (canonical_family_name(snapshot) != "金庫型"
            or len(batch.requests) != 1 or not callable(read_current) or not callable(sink)):
        raise ValueError("OWNER_MARKING_QUANTITY_ORDINARY_SCOPE_REQUIRED")
    version_id, version_count, _request = batch.requests[0]
    version_scope = _vault_single_quantity(snapshot) if snapshot.get("active_mode") == "quantity" else None
    if version_scope is not None and version_scope != (version_id, version_count):
        raise ValueError("OWNER_MARKING_QUANTITY_VERSION_SOURCE_MISMATCH")
    selection = plan_quantity_operator_export_selection(batch, workspace, flags)
    rows = tuple(selection.selected_demands)
    owner_keys = tuple(owner_keys)
    if (selection.partial_selection is not None or not owner_keys
            or len(set(owner_keys)) != len(owner_keys)
            or any(row.version_id != version_id for row in rows)):
        raise ValueError("OWNER_MARKING_QUANTITY_ORDINARY_SCOPE_REQUIRED")
    _, geometry = read_current()
    source_rows, witness = _prepare_selected_ordinary_marking_batch(
        snapshot, geometry, flags, owner_keys, read_current,
    )
    stock = dict(source_rows)
    if (len(stock) != len(source_rows) or len(stock) != len(rows)
            or {row.physical_id for row in rows} != set(stock)
            or any(row.physical_id != row.source_part_id
                   or _selected_render_signature(row.render_data)
                   != _selected_render_signature(stock[row.physical_id]) for row in rows)):
        raise ValueError("OWNER_MARKING_QUANTITY_FLAT_SOURCE_MISMATCH")
    proofs = {key: witness.owner_row(key) for key in owner_keys}
    # One physical sheet per box is not the same as one box in this version.
    if {row.physical_id for row in rows if row.physical_id in proofs
            and row.per_box_count == 1 and row.piece_count == version_count} != set(proofs):
        raise ValueError("OWNER_MARKING_QUANTITY_SINGLE_OWNER_COUNT_REQUIRED")
    groups = quantity_manufacturing_groups(
        batch, demands=tuple(replace(row, render_data=proofs[row.physical_id].render)
                             if row.physical_id in proofs else row for row in rows),
    )
    if sum(group.quantity for group in groups) != sum(row.quantity for row in rows):
        raise ValueError("OWNER_MARKING_QUANTITY_PIECE_COUNT_CHANGED")
    staged_rows = []
    marked = {}
    for group in groups:
        annotated = annotate_quantity_render_data(group.render_data, group.quantity)
        owners = tuple(row.physical_id for row in group.members if row.physical_id in proofs)
        if owners:
            if len(group.members) != 1 or group.render_data is not proofs[owners[0]].render:
                raise ValueError("OWNER_MARKING_QUANTITY_OWNER_GROUP_AMBIGUOUS")
            marked[owners[0]] = annotated
        else:
            # Do not replace the ordinary per-part guard for companion stock.
            api._require_single_part_dxf_source(group.render_data)
        staged_rows.append((group.key, group.filename, annotated))
    if set(marked) != set(proofs):
        raise ValueError("OWNER_MARKING_QUANTITY_INVENTORY_CHANGED")
    quantity_witness = _VaultQuantityOwnerWitness(
        witness, staged_rows, marked.values(), read_current, version_scope,
    )
    seals = []

    def serialize(render, output, *, overwrite):
        api._require_single_part_dxf_source(
            render, selected_owner_witness=quantity_witness if quantity_witness.is_marked(render) else None,
        )
        quantity_witness.assert_render(render)
        saved = save_part_render_data_dxf(render.scene, output, serializer=api.save_scene_dxf,
                                          overwrite=overwrite)
        verify_quantity_check_dxf(render.scene, saved)
        return saved

    outputs = _save_resolved_rows_atomic(
        staged_rows, directory,
        save_part_render_data_dxf=serialize, overwrite=False, verify_all_staged=True,
        _selected_owner_witness=quantity_witness, _verified_byte_seals_sink=seals.extend,
    )
    sink(quantity_witness.assert_current, tuple(seals))
    return QuantityOperatorStagedExport(tuple(Path(p).name for p in outputs.values()))
