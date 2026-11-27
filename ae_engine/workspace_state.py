# -*- coding: utf-8 -*-
"""Engine-owned physical Workspace state shared by Main and Designer clients.

The module owns only presence / active / profile stash / box-body structure
shape and invariants. It knows no Main/Designer lifecycle or Tk state; no
mutable singleton is shared between clients.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Mapping
from re import fullmatch
from uuid import uuid4

from .cabinet_types.policy import canonical_family_name
from .cabinet_types.registry import resolve_cabinet_type

from .custom_part_catalog import CustomPartCatalog, is_custom_part
from .box_body_structure_state import normalize_box_body_structure_state


MANDATORY_PART = "box_body"
PART_ORDER = (
    "box_body",
    "head",
    "tail",
    "door",
    "base_plate",
    "indicator_box",
    "indicator_door",
)
ACTIVE_REPAIR_POLICIES = frozenset({"first", "none", "raise"})
ROOT_PHYSICAL_OCCUPANCY_KEY = "physical_root_occupancy"
# Authorized explicit roots only. Box Body is mandatory logical assembly;
# its derived sheet IDs and CustomPart catalog already have dedicated owners.
_EXPLICIT_ROOTS = frozenset(PART_ORDER) - {MANDATORY_PART}


def _registered_root_family(model):
    try:
        return resolve_cabinet_type(canonical_family_name(model)).canonical_name
    except KeyError:
        return ""


def normalize_workspace_root_occupancy(raw, *, existing_parts, model=None):
    """Read detached current occupancy. Never mint on projection or legacy load."""
    if raw is None:
        return {}
    if not isinstance(raw, Mapping):
        raise ValueError("PHYSICAL_ROOT_OCCUPANCY_INVALID")
    known = set(existing_parts)
    family = _registered_root_family(model)
    result, ids = {}, set()
    for key, entry in raw.items():
        if (key not in _EXPLICIT_ROOTS or not isinstance(entry, Mapping)
                or set(entry) != {"owner_id", "family"}):
            raise ValueError("PHYSICAL_ROOT_OCCUPANCY_INVALID")
        owner_id, recorded = entry["owner_id"], entry["family"]
        if (type(owner_id) is not str or not fullmatch(r"root-owner:[a-f0-9]{32}", owner_id)
                or owner_id in ids or type(recorded) is not str or not recorded
                or _registered_root_family(recorded) != recorded):
            raise ValueError("PHYSICAL_ROOT_OCCUPANCY_INVALID")
        ids.add(owner_id)
        if key in known and (model is None or recorded == family):
            result[key] = {"owner_id": owner_id, "family": recorded}
    return result


def _ordinary_explicit_root_key(key, source):
    if key not in _EXPLICIT_ROOTS:
        return False
    if key == "door" and isinstance(source, Mapping):
        # Door is also the historical selected-cell alias. The registered
        # route already distinguishes that alias from a single root.
        from .physical_part_identity import project_operator_hole_editor_route
        return project_operator_hole_editor_route(
            key, model=source.get("model"),
            multi_door_enabled=source.get("multi_door_enabled", False),
        ).kind == "simple_part"
    return True


def resolve_workspace_physical_root_owner(snapshot, part_key):
    """Read a current explicit root, not scoped/derived assignment or eligibility."""
    if not isinstance(snapshot, Mapping) or not _ordinary_explicit_root_key(part_key, snapshot):
        return None
    family = _registered_root_family(snapshot.get("model"))
    if not family:
        return None
    nested = snapshot.get("workspace")
    nested = nested if isinstance(nested, Mapping) else {}
    presence = snapshot.get("existing_parts", nested.get("existing_parts", ()))
    raw = snapshot.get(ROOT_PHYSICAL_OCCUPANCY_KEY, nested.get(ROOT_PHYSICAL_OCCUPANCY_KEY))
    resolved = normalize_workspace_root_occupancy(raw, existing_parts=presence or (), model=family)
    return resolved.get(part_key, {}).get("owner_id")



def normalize_existing_parts(values) -> tuple[str, ...]:
    """Normalize presence once, preserving a deterministic stable order."""
    raw: list[str] = []
    seen: set[str] = set()
    for item in values or ():
        key = str(item or "").strip()
        if key and key not in seen:
            seen.add(key)
            raw.append(key)
    if MANDATORY_PART not in seen:
        raw.insert(0, MANDATORY_PART)
        seen.add(MANDATORY_PART)
    ordered = [key for key in PART_ORDER if key in seen]
    ordered.extend(key for key in raw if key not in PART_ORDER)
    return tuple(ordered)


@dataclass(frozen=True)
class OperatorWorkspaceSnapshotPresence:
    """Detached physical presence/active part written to Fold Designer projects."""

    existing_parts: tuple[str, ...]
    active_part: str | None


def project_operator_fold_designer_workspace_presence(
    current_existing_parts: object,
    workspace_existing_parts: object,
    active_part: object,
) -> OperatorWorkspaceSnapshotPresence:
    """Resolve persisted physical part identity without GUI-owned ordering.

    The current controller owns *present* parts, while the committed Workspace
    owns dynamic part order.  The canonical Engine PART_ORDER precedes custom
    parts exactly as the historical Fold Designer projection did.  Invalid
    selections fall back to the first genuinely present physical part.
    """
    def rows(value: object, label: str) -> tuple[str, ...]:
        if value is None or isinstance(value, (str, bytes, Mapping)):
            raise ValueError(f"{label} must be physical part keys")
        try:
            result = tuple(value)
        except TypeError as exc:
            raise ValueError(f"{label} must be physical part keys") from exc
        if any(not isinstance(key, str) or not key.strip() for key in result):
            raise ValueError(f"{label} contains invalid physical part keys")
        return result

    present = set(normalize_existing_parts(
        rows(current_existing_parts, "current_existing_parts")
    ))
    workspace_order = normalize_existing_parts(
        rows(workspace_existing_parts, "workspace_existing_parts")
    )
    canonical = tuple(key for key in PART_ORDER if key in present)
    dynamic = tuple(
        key for key in workspace_order
        if key in present and key not in PART_ORDER
    )
    ordered = canonical + dynamic
    if not ordered:
        raise ValueError("physical Workspace snapshot has no existing parts")
    candidate = str(active_part or "").strip()
    # Historical Save→Reload uses the first physical part when no selection
    # was made, unlike the independent WorkspaceState(None) edit mode.
    repaired = _repair_active(candidate or ordered[0], ordered, "first")
    return OperatorWorkspaceSnapshotPresence(ordered, repaired)


def _repair_active(active_part, existing_parts, policy: str) -> str | None:
    policy = str(policy or "").strip().lower()
    if policy not in ACTIVE_REPAIR_POLICIES:
        raise ValueError(f"unknown active repair policy: {policy!r}")
    active = str(active_part or "").strip() or None
    existing = tuple(existing_parts)
    if active is None or active in existing:
        return active
    if policy == "none":
        return None
    if policy == "first":
        return existing[0] if existing else MANDATORY_PART
    raise ValueError(f"active_part 不存在於 existing_parts: {active}")


class SharedWorkspaceState:
    """Shared state contract instantiated independently by each lifecycle owner."""

    def __init__(
        self,
        *,
        existing_parts=None,
        active_part=None,
        part_profiles: Mapping[str, object] | None = None,
        box_body_structure=None,
        custom_parts=None,
        root_occupancy=None,
        root_marking_store=None,
        active_repair: str = "first",
    ) -> None:
        self._existing_parts = list(normalize_existing_parts(existing_parts or (MANDATORY_PART,)))
        self._active_part = _repair_active(active_part, self._existing_parts, active_repair)
        self._part_profiles = deepcopy(dict(part_profiles or {}))
        self._box_body_structure = normalize_box_body_structure_state(box_body_structure)
        self._custom_parts = CustomPartCatalog(custom_parts)
        self._root_occupancy = normalize_workspace_root_occupancy(
            root_occupancy, existing_parts=self._existing_parts,
        )
        from .operator_root_marking_store import normalize_workspace_root_marking_store
        self._root_marking_store = normalize_workspace_root_marking_store(root_marking_store)
        custom_keys = {key for key in self._existing_parts if is_custom_part(key)}
        if custom_keys != set(self._custom_parts.snapshot()["items"]):
            raise ValueError("自訂板件 presence 與 metadata 不一致")

    def custom_parts_snapshot(self):
        return self._custom_parts.snapshot()

    def custom_part(self, key):
        return self._custom_parts.get(key)

    def add_custom_part(self, **values):
        key = self._custom_parts.add(**values)
        self.set_part_presence(key, True, active_repair="none")
        return key

    def update_custom_part(self, key, **values):
        return self._custom_parts.update(key, **values)

    @property
    def existing_parts(self) -> tuple[str, ...]:
        return tuple(self._existing_parts)

    @property
    def active_part(self) -> str | None:
        return self._active_part

    def set_existing_parts(self, values, *, active_repair: str, explicit_root_source=None) -> tuple[str, ...]:
        normalized = list(normalize_existing_parts(values))
        for key in normalized:
            if is_custom_part(key) and self._custom_parts.get(key) is None:
                raise ValueError("自訂板件缺少 metadata")
        active = _repair_active(self._active_part, normalized, active_repair)
        occupancy = normalize_workspace_root_occupancy(
            self._root_occupancy, existing_parts=normalized,
        )
        family = _registered_root_family(explicit_root_source)
        if family:
            for key in normalized:
                if key not in self._existing_parts and _ordinary_explicit_root_key(key, explicit_root_source):
                    occupancy[key] = {"owner_id": f"root-owner:{uuid4().hex}", "family": family}
        for key in self._custom_parts.snapshot()["items"]:
            if key not in normalized:
                self._custom_parts.remove(key)
                self._part_profiles.pop(key, None)
        self._existing_parts = normalized
        self._active_part = active
        self._root_occupancy = occupancy
        return self.existing_parts

    def reconcile_root_occupancy_family(self, model):
        """Retire a different Family's roots at genuine Family replacement."""
        self._root_occupancy = normalize_workspace_root_occupancy(
            self._root_occupancy, existing_parts=self._existing_parts, model=model,
        )

    def _propose_marked_legacy_root(self, key, model):
        """The mark-confirm API has already validated the physical draft."""
        family = _registered_root_family(model)
        if not family or key not in _EXPLICIT_ROOTS or key not in self._existing_parts:
            raise ValueError("PHYSICAL_ROOT_MARK_CONFIRM_SOURCE_REQUIRED")
        occupancy = normalize_workspace_root_occupancy(
            self._root_occupancy, existing_parts=self._existing_parts, model=family,
        )
        if key not in occupancy:
            occupancy[key] = {"owner_id": f"root-owner:{uuid4().hex}", "family": family}
        return occupancy

    def set_part_presence(self, key: str, present: bool, *, active_repair: str, explicit_root_source=None) -> tuple[str, ...]:
        candidate = str(key or "").strip()
        if not candidate:
            raise ValueError("板件名稱不得為空")
        values = list(self._existing_parts)
        if present:
            if candidate not in values:
                values.append(candidate)
        elif candidate != MANDATORY_PART:
            values = [item for item in values if item != candidate]
        return self.set_existing_parts(values, active_repair=active_repair, explicit_root_source=explicit_root_source)

    def set_active_part(self, value: str | None, *, invalid: str) -> str | None:
        if value is None or value == "":
            self._active_part = None
            return None
        candidate = str(value).strip()
        if candidate in self._existing_parts:
            self._active_part = candidate
            return candidate
        if invalid == "first":
            self._active_part = self._existing_parts[0] if self._existing_parts else MANDATORY_PART
            return self._active_part
        if invalid == "none":
            self._active_part = None
            return None
        if invalid == "raise":
            raise ValueError(f"active_part 不存在於 existing_parts: {candidate}")
        raise ValueError(f"unknown active repair policy: {invalid!r}")

    def replace_part_profiles(self, profiles: Mapping[str, object] | None) -> dict:
        self._part_profiles = deepcopy(dict(profiles or {}))
        return self.part_profiles_snapshot()

    def has_profile(self, key: str) -> bool:
        return str(key or "") in self._part_profiles

    def stash_profiles(self, key: str, profiles: Mapping[str, object]) -> bool:
        candidate = str(key or "")
        copied = deepcopy(dict(profiles or {}))
        changed = self._part_profiles.get(candidate) != copied
        if changed:
            self._part_profiles[candidate] = copied
        return changed

    def profile_for(self, key: str, default=None):
        candidate = str(key or "")
        if candidate not in self._part_profiles:
            return deepcopy(default)
        return deepcopy(self._part_profiles[candidate])

    def part_profiles_snapshot(self) -> dict:
        return deepcopy(self._part_profiles)

    def set_box_body_structure_state(self, state) -> dict:
        self._box_body_structure = normalize_box_body_structure_state(state)
        return self.box_body_structure_state()

    def box_body_structure_state(self) -> dict:
        return deepcopy(self._box_body_structure)

    def replace(
        self,
        *,
        existing_parts,
        active_part,
        part_profiles,
        box_body_structure,
        custom_parts=None,
        root_occupancy=None,
        root_marking_store=None,
        active_repair: str,
    ) -> dict:
        candidate = SharedWorkspaceState(
            existing_parts=existing_parts, active_part=active_part,
            part_profiles=part_profiles, box_body_structure=box_body_structure,
            custom_parts=custom_parts, root_occupancy=root_occupancy,
            root_marking_store=root_marking_store, active_repair=active_repair,
        )
        self._existing_parts = list(candidate.existing_parts)
        self._active_part = candidate.active_part
        self._part_profiles = candidate.part_profiles_snapshot()
        self._box_body_structure = candidate.box_body_structure_state()
        self._custom_parts = candidate._custom_parts
        self._root_occupancy = candidate._root_occupancy
        self._root_marking_store = candidate._root_marking_store
        return self.snapshot()

    def commit_owner_marking_update(self, update, *, model, read_current_receipt, read_proposed_receipt=None):
        from .operator_root_marking_store import (
            WorkspaceInitialOwnerMarkingUpdate, apply_initial_workspace_owner_marking_commit,
            apply_workspace_owner_marking_commit,
        )
        if not callable(read_current_receipt):
            raise TypeError("ROOT_MARKING_CURRENT_SOURCE_REQUIRED")
        if isinstance(update, WorkspaceInitialOwnerMarkingUpdate):
            if resolve_workspace_physical_root_owner({"model": model, **self.snapshot()}, update.part_key) is not None:
                raise ValueError("ROOT_MARKING_OWNER_STALE")
            receipt = read_current_receipt()
            proposed = read_proposed_receipt() if read_proposed_receipt is not None else None
            occupancy, accepted = apply_initial_workspace_owner_marking_commit(
                self, {"model": model, **self.snapshot()}, update, receipt, proposed,
            )
            self._root_occupancy, self._root_marking_store = occupancy, accepted
            return True
        # Reject a removed owner before evaluating the replacement's geometry.
        if resolve_workspace_physical_root_owner({"model": model, **self.snapshot()}, update.part_key) != update.owner_id:
            raise ValueError("ROOT_MARKING_OWNER_STALE")
        receipt = read_current_receipt()
        proposed = read_proposed_receipt() if read_proposed_receipt is not None else None
        accepted = apply_workspace_owner_marking_commit({"model": model, **self.snapshot()}, update, receipt, proposed)
        changed = accepted != self._root_marking_store
        self._root_marking_store = accepted
        return changed

    def commit_box_body_piece_marking(self, opened, marks, *, read_current):
        from .operator_box_body_piece_marking import _read, prepare_box_body_piece_marking_commit
        from .operator_root_marking_store import ROOT_MARKING_STORE_KEY
        if not callable(read_current):
            raise TypeError("ROOT_MARKING_CURRENT_SOURCE_REQUIRED")
        authority, geometry = read_current()
        authority = deepcopy(authority)
        workspace = self.snapshot()
        current = {**authority, **workspace}
        # Workspace is the commit authority even if a pre-edit receipt was
        # opened from an earlier external view of it.
        current.pop(ROOT_MARKING_STORE_KEY, None)
        current.pop(ROOT_PHYSICAL_OCCUPANCY_KEY, None)
        current.pop("workspace", None)
        current.update(workspace)
        structure, ledger = prepare_box_body_piece_marking_commit(
            current, geometry, opened, marks,
        )
        fresh, fresh_geometry = read_current()
        if (fresh != authority or self.snapshot() != workspace
                or _read(current, fresh_geometry, opened.part_key)[0] != opened):
            raise ValueError("ROOT_MARKING_WORKSPACE_STALE")
        changed = (structure != self._box_body_structure or ledger != self._root_marking_store)
        self._box_body_structure, self._root_marking_store = structure, ledger
        return changed

    def commit_quantity_owner_marking(self, snapshot, receipt, marks, *, version_id, geometry):
        from dataclasses import replace
        from .operator_quantity_marking_owner import (
            _update_quantity_marking_ledger, _validate_quantity_marking_update,
        )
        from .operator_root_marking_store import _root_store
        if _root_store(snapshot) != self._root_marking_store:
            raise ValueError("ROOT_MARKING_WORKSPACE_STALE")
        current = {**snapshot, **self.snapshot()}
        owner, stock, marks = _validate_quantity_marking_update(
            current, receipt, marks, version_id=version_id, geometry=geometry,
        )
        occupancy = self._root_occupancy
        if owner.root_owner_id is None:
            if not marks:
                return False
            occupancy = self._propose_marked_legacy_root(owner.physical_id, current["model"])
            owner = replace(owner, root_owner_id=occupancy[owner.physical_id]["owner_id"])
        accepted = _update_quantity_marking_ledger(current, owner, stock, marks)
        changed = accepted != self._root_marking_store
        self._root_occupancy, self._root_marking_store = occupancy, accepted
        return changed

    def commit_quantity_marking_and_common_holes(self, snapshot, opened, context, holes, marks,
                                                 *, build_batch, read_current):
        from .operator_quantity_marking_owner import propose_quantity_marking_and_common_holes
        from .operator_root_marking_store import _root_store
        if _root_store(snapshot) != self._root_marking_store:
            raise ValueError("ROOT_MARKING_WORKSPACE_STALE")
        accepted, ledger = propose_quantity_marking_and_common_holes(
            snapshot, opened, context, holes, marks, build_batch=build_batch,
        )
        if read_current() != snapshot or _root_store(snapshot) != self._root_marking_store:
            raise ValueError("ROOT_MARKING_DRAFT_STALE")
        self._root_marking_store = ledger
        return accepted

    def commit_transferred_quantity_marking(self, snapshot, geometry, part_key, opened, *, version_id):
        from .operator_quantity_marking_owner import with_transferred_quantity_marking
        from .operator_root_marking_store import _root_store
        if _root_store(snapshot) != self._root_marking_store:
            raise ValueError("ROOT_MARKING_WORKSPACE_STALE")
        accepted = with_transferred_quantity_marking(
            {**snapshot, **self.snapshot()}, geometry, part_key, opened, version_id=version_id,
        )
        self._root_marking_store = accepted
        return True

    def snapshot(self) -> dict:
        result = {
            "existing_parts": list(self._existing_parts),
            "active_part": self._active_part,
            "part_profiles": self.part_profiles_snapshot(),
            "box_body_structure": self.box_body_structure_state(),
        }
        if self._root_marking_store["records"]:
            from .operator_root_marking_store import ROOT_MARKING_STORE_KEY
            result[ROOT_MARKING_STORE_KEY] = deepcopy(self._root_marking_store)
        if self._root_occupancy:
            result[ROOT_PHYSICAL_OCCUPANCY_KEY] = deepcopy(self._root_occupancy)
        if self._custom_parts.has_history:
            result["custom_parts"] = self.custom_parts_snapshot()
        return result
