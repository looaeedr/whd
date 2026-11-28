"""Phase6 3D Designer 草稿工作區的純狀態 owner。"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from phase6_box_body_structure import normalize_box_body_structure_state, legacy_box_body_structure_locked
from ae_engine.manufacturing_api import (
    ROOT_PHYSICAL_OCCUPANCY_KEY, normalize_workspace_root_occupancy,
    ROOT_MARKING_STORE_KEY, normalize_workspace_root_marking_store, resolve_custom_part_catalog,
    custom_saved_part_inputs,
)
from phase6_workspace_state import MANDATORY_PART, SharedWorkspaceState
from phase6_quantity_model import QuantityModel, normalize_quantity_snapshot


class Phase6DesignerWorkspace:
    def __init__(
        self,
        *,
        shared_state: SharedWorkspaceState | None = None,
        selected_part: str | None = None,
        part_features: Mapping[str, object] | None = None,
        part_face_features: Mapping[str, object] | None = None,
        assembly_placements: Mapping[str, object] | None = None,
        dirty: bool = False,
        switching: bool = False,
        active_mode: str = "quantity",
        quantity: Mapping[str, object] | None = None,
        receiving_quantity_box: Mapping[str, object] | None = None,
    ) -> None:
        self._shared_state = shared_state or SharedWorkspaceState(active_repair="none")
        self._selected_part = selected_part
        self._part_features = deepcopy(dict(part_features or {}))
        self._part_face_features = deepcopy(dict(part_face_features or {}))
        self._assembly_placements = deepcopy(dict(assembly_placements or {}))
        self._dirty = bool(dirty)
        self._switching = bool(switching)
        self._active_mode = active_mode
        self._receiving_quantity_box = deepcopy(receiving_quantity_box)
        self._quantity_model = None
        if active_mode == "quantity":
            self._quantity_model = (
                QuantityModel.from_payload(quantity, on_change=self.mark_dirty)
                if quantity is not None else
                QuantityModel(head_features=self._part_features.get("head", ()),
                              tail_features=self._part_features.get("tail", ()),
                              on_change=self.mark_dirty)
            )

    @classmethod
    def from_snapshot(cls, snapshot: Mapping[str, object] | None) -> "Phase6DesignerWorkspace":
        source = normalize_quantity_snapshot(snapshot)
        raw_structure = (
            (source.get("workspace") or {}).get("box_body_structure", source.get("box_body_structure"))
            if isinstance(source.get("workspace"), Mapping) else source.get("box_body_structure")
        )
        structure = normalize_box_body_structure_state(
            raw_structure,
            legacy_locked=legacy_box_body_structure_locked(source.get("model")),
        )
        ws_source = source.get("workspace") if isinstance(source.get("workspace"), Mapping) else {}
        existing = source.get("existing_parts") or ws_source.get("existing_parts") or (MANDATORY_PART,)
        catalog = resolve_custom_part_catalog(source).snapshot()
        profiles = dict(source.get("part_profiles") or ws_source.get("part_profiles") or {})
        features = dict(source.get("part_features") or ws_source.get("part_features") or {})
        for key in catalog["items"]:
            profile, role_features = custom_saved_part_inputs(source, key)
            if profile is not None:
                profiles[key] = profile
            features[key] = list(role_features)
        shared = SharedWorkspaceState(
            existing_parts=existing,
            root_marking_store=source.get(ROOT_MARKING_STORE_KEY, ws_source.get(ROOT_MARKING_STORE_KEY)),
            root_occupancy=normalize_workspace_root_occupancy(
                source.get(ROOT_PHYSICAL_OCCUPANCY_KEY, ws_source.get(ROOT_PHYSICAL_OCCUPANCY_KEY)),
                existing_parts=existing, model=source.get("model"),
            ),
            active_part=source.get("active_part") or ws_source.get("active_part"),
            part_profiles=profiles,
            box_body_structure=structure,
            custom_parts=catalog,
            active_repair="none",
        )
        return cls(
            shared_state=shared,
            selected_part=None,
            part_features=features,
            part_face_features=source.get("part_face_features") or ws_source.get("part_face_features"),
            assembly_placements=source.get("assembly_placements") or ws_source.get("assembly_placements"),
            dirty=False,
            switching=False,
            active_mode=source["active_mode"],
            quantity=source.get("quantity"),
            receiving_quantity_box=source.get("receiving_quantity_box"),
        )

    def replace_receiving_snapshot(self, snapshot):
        """Replace state in place so existing navigation ports keep their owner."""
        candidate = type(self).from_snapshot(snapshot)
        self.__dict__.update(candidate.__dict__)
        if self._quantity_model is not None:
            self._quantity_model._on_change = self.mark_dirty
        self.mark_dirty()

    def commit_owner_marking_update(
        self, update, *, model, read_current_receipt, read_proposed_receipt=None, pending_role_features=None,
        read_current_source=None,
    ):
        # Prepare all ordinary feature transport before the final Engine CAS.
        # The assignment after CAS has no modal callback or event re-entry.
        next_role = None if pending_role_features is None else deepcopy(list(pending_role_features))
        state = self._shared_state

        def read_current_role_features():
            if self._shared_state is not state:
                raise ValueError("ROOT_MARKING_WORKSPACE_STALE")
            return self.features_for(update.part_key)

        changed = state.commit_owner_marking_update(
            update, model=model, read_current_receipt=read_current_receipt,
            read_proposed_receipt=read_proposed_receipt,
            read_current_source=read_current_source,
            read_current_role_features=read_current_role_features,
            pending_role_features=next_role,
        )
        if next_role is not None and self._part_features.get(update.part_key) != next_role:
            self._part_features[update.part_key] = next_role
            changed = True
        if changed:
            self.mark_dirty()
        return changed

    def commit_saved_c_divider_marking(self, update, *, read_current):
        changed = self._shared_state.commit_saved_c_divider_marking(update, read_current=read_current)
        if changed:
            self.mark_dirty()
        return changed

    def commit_box_body_piece_marking(self, opened, marks, *, read_current):
        changed = self._shared_state.commit_box_body_piece_marking(
            opened, marks, read_current=read_current,
        )
        if changed:
            self.mark_dirty()
        return changed

    def commit_quantity_owner_marking(self, snapshot, receipt, marks, *, version_id, geometry):
        changed = self._shared_state.commit_quantity_owner_marking(
            {**snapshot, **self.snapshot()}, receipt, marks, version_id=version_id, geometry=geometry,
        )
        if changed:
            self.mark_dirty()
        return changed

    def commit_quantity_marking_and_common_holes(self, snapshot, opened, context, holes, marks,
                                                 *, build_batch, read_current):
        accepted = self._shared_state.commit_quantity_marking_and_common_holes(
            snapshot, opened, context, holes, marks, build_batch=build_batch, read_current=read_current,
        )
        self._part_features[opened.owner.physical_id] = list(accepted)
        self.mark_dirty()

    def commit_transferred_quantity_marking(self, snapshot, geometry, part_key, opened, *, version_id):
        result = self._shared_state.commit_transferred_quantity_marking(
            {**snapshot, **self.snapshot()}, geometry, part_key, opened, version_id=version_id,
        )
        if result:
            self.mark_dirty()
        return result

    def reconcile_root_occupancy_family(self, model):
        self._shared_state.reconcile_root_occupancy_family(model)

    def set_receiving_common_box(self, box):
        if self._quantity_model is None:
            raise ValueError("共用箱體設定僅適用於數量模式")
        candidate = normalize_quantity_snapshot({
            "model": "受電箱", "active_mode": self._active_mode,
            "quantity": self._quantity_model.snapshot(), "receiving_quantity_box": box,
        })["receiving_quantity_box"]
        if candidate != self._receiving_quantity_box:
            self._receiving_quantity_box = candidate
            self.mark_dirty()

    @property
    def active_mode(self) -> str:
        """O(1) read of the authoritative Receiving mode, no workspace copy."""
        return str(self._active_mode)

    @property
    def quantity_model(self) -> QuantityModel | None:
        return self._quantity_model

    @property
    def available_parts(self) -> tuple[str, ...]:
        return self._shared_state.existing_parts

    def replace_available_parts(self, values) -> tuple[str, ...]:
        previous = set(self.available_parts)
        parts = self._shared_state.set_existing_parts(values, active_repair="none")
        if self._selected_part not in parts:
            self._selected_part = None
        self._drop_assembly_placements_for_removed_parts(previous.difference(parts))
        self._prune_assembly_placements(parts)
        return parts

    @property
    def active_part(self) -> str | None:
        return self._shared_state.active_part

    @active_part.setter
    def active_part(self, value: str | None) -> None:
        try:
            self._shared_state.set_active_part(value, invalid="raise")
        except ValueError as exc:
            raise ValueError(f"板件不存在: {str(value)}") from exc

    @property
    def selected_part(self) -> str | None:
        return self._selected_part

    @selected_part.setter
    def selected_part(self, value: str | None) -> None:
        if value is None or value == "":
            self._selected_part = None
            return
        key = str(value)
        if key not in self.available_parts:
            raise ValueError(f"板件不存在: {key}")
        self._selected_part = key

    @property
    def dirty(self) -> bool:
        return self._dirty

    @dirty.setter
    def dirty(self, value: bool) -> None:
        self._dirty = bool(value)

    @property
    def switching(self) -> bool:
        return self._switching

    @switching.setter
    def switching(self, value: bool) -> None:
        self._switching = bool(value)

    def select_part(self, key: str) -> bool:
        key = str(key or "")
        if key not in self.available_parts:
            return False
        self._selected_part = key
        return True

    def begin_switch(self, key: str) -> None:
        key = str(key or "")
        if key not in self.available_parts:
            raise ValueError(f"板件不存在: {key}")
        self._switching = True
        self._selected_part = key
        self._shared_state.set_active_part(key, invalid="raise")

    def finish_switch(self) -> None:
        self._switching = False

    def show_home(self) -> None:
        self._shared_state.set_active_part(None, invalid="none")
        self._selected_part = None
        self._switching = False

    def custom_part(self, key):
        return self._shared_state.custom_part(key)

    def add_custom_part(self, **values):
        key = self._shared_state.add_custom_part(**values)
        self._part_features[key] = []
        self._dirty = True
        return key

    def update_custom_part(self, key, **values):
        changed = self._shared_state.update_custom_part(key, **values)
        if changed:
            self._dirty = True
        return changed

    def add_part(
        self,
        key: str,
        *,
        default_profiles: Mapping[str, object] | None = None,
        default_features=(),
        default_face_features: Mapping[str, object] | None = None,
        explicit_root_source=None,
    ) -> bool:
        key = str(key or "").strip()
        if not key:
            raise ValueError("板件名稱不得為空")
        if key in self.available_parts:
            return False
        self._shared_state.set_part_presence(
            key, True, active_repair="none", explicit_root_source=explicit_root_source,
        )
        if not self._shared_state.has_profile(key) and default_profiles is not None:
            self._shared_state.stash_profiles(key, default_profiles)
        if key not in self._part_features:
            self._part_features[key] = deepcopy(list(default_features or ()))
        if key not in self._part_face_features and default_face_features is not None:
            self._part_face_features[key] = deepcopy(dict(default_face_features))
        self._dirty = True
        return True

    def remove_part(self, key: str) -> bool:
        key = str(key or "")
        if key == MANDATORY_PART:
            raise ValueError("箱身是折法主資料，不能刪除")
        if key not in self.available_parts:
            return False
        custom = self.custom_part(key) is not None
        self._shared_state.set_part_presence(key, False, active_repair="none")
        if custom:
            self._part_features.pop(key, None)
            self._part_face_features.pop(key, None)
        if self._selected_part == key:
            self._selected_part = None
        # A surviving physical part may still be placed relative to the
        # deleted parent. Drop its stale datum and all dependent placements.
        self._drop_assembly_placements_for_removed_parts((key,))
        self._prune_assembly_placements(self.available_parts)
        self._dirty = True
        return True

    def stash_profiles(self, key: str, profiles: Mapping[str, object]) -> None:
        if self._shared_state.stash_profiles(key, profiles):
            self._dirty = True

    def profiles_for(self, key: str, default=None):
        return self._shared_state.profile_for(key, default)

    def stash_features(self, key: str, features) -> None:
        key = str(key or "")
        if self._quantity_model is not None and key in {"head", "tail"}:
            self._quantity_model.set_features(key, features or ())
            return
        copied = deepcopy(list(features or ()))
        if self._part_features.get(key) != copied:
            self._part_features[key] = copied
            self._dirty = True

    def features_for(self, key: str) -> list[Any]:
        if self._quantity_model is not None and key in {"head", "tail"}:
            return self._quantity_model.features_for(key)
        return deepcopy(list(self._part_features.get(str(key or ""), ())))

    def stash_face_features(self, key: str, face_features: Mapping[str, object]) -> None:
        key = str(key or "")
        copied = deepcopy(dict(face_features or {}))
        if self._part_face_features.get(key) != copied:
            self._part_face_features[key] = copied
            self._dirty = True

    def face_features_for(self, key: str) -> dict[str, list[Any]]:
        return deepcopy(dict(self._part_face_features.get(str(key or ""), {})))

    def part_profiles_snapshot(self) -> dict[str, dict[str, Any]]:
        return self._shared_state.part_profiles_snapshot()

    def replace_part_profiles(self, value: Mapping[str, object] | None) -> dict[str, dict[str, Any]]:
        return self._shared_state.replace_part_profiles(value)

    def part_features_snapshot(self) -> dict[str, list[Any]]:
        result = deepcopy(self._part_features)
        if self._quantity_model is not None:
            for part in ("head", "tail"):
                result[part] = self._quantity_model.features_for(part)
        return result

    def replace_part_features(self, value: Mapping[str, object] | None) -> dict[str, list[Any]]:
        self._part_features = deepcopy(dict(value or {}))
        if self._quantity_model is not None:
            for part in ("head", "tail"):
                self._quantity_model.set_features(part, self._part_features.get(part, ()))
        return self.part_features_snapshot()

    def part_face_features_snapshot(self) -> dict[str, dict[str, list[Any]]]:
        return deepcopy(self._part_face_features)

    def replace_part_face_features(self, value: Mapping[str, object] | None) -> dict[str, list[Any]]:
        self._part_face_features = deepcopy(dict(value or {}))
        return self.part_face_features_snapshot()

    def box_body_structure_state(self) -> dict[str, object]:
        return self._shared_state.box_body_structure_state()

    def set_box_body_structure_state(self, state) -> dict[str, object]:
        normalized = normalize_box_body_structure_state(state)
        if self._shared_state.box_body_structure_state() != normalized:
            self._shared_state.set_box_body_structure_state(normalized)
            self._dirty = True
        return self.box_body_structure_state()

    def sync_derived_parts(self, *, namespace: str, part_profiles: Mapping[str, object]) -> tuple[str, ...]:
        """Replace one derived-part namespace without importing domain/manufacturing code."""
        prefix = str(namespace or "").strip()
        if not prefix:
            raise ValueError("derived part namespace must be non-empty")
        desired_profiles = {str(key): deepcopy(value) for key, value in dict(part_profiles or {}).items()}
        desired = set(desired_profiles)
        current = {key for key in self.available_parts if str(key).startswith(prefix)}
        for key in tuple(current - desired):
            self.remove_part(key)
        for key, profiles in desired_profiles.items():
            if key in self.available_parts:
                self.stash_profiles(key, profiles)
            else:
                self.add_part(key, default_profiles=profiles)
        return tuple(key for key in self.available_parts if key in desired)

    def set_assembly_placement(self, placement) -> dict[str, object]:
        """Store a resolved placement contract keyed by its stable physical id."""
        stable_id = str(getattr(placement, "stable_id", "") or "").strip()
        if not stable_id:
            raise ValueError("assembly placement stable_id must not be empty")
        if stable_id not in self.available_parts:
            raise ValueError(f"assembly placement part does not exist: {stable_id}")
        payload = placement.to_dict() if hasattr(placement, "to_dict") else deepcopy(dict(placement))
        if self._assembly_placements.get(stable_id) != payload:
            self._assembly_placements[stable_id] = deepcopy(payload)
            self._dirty = True
        return deepcopy(payload)

    def assembly_placement_for(self, stable_id: str, *, snapshot: Mapping[str, object] | None = None, resolver=None):
        key = str(stable_id or "").strip()
        cached = self._assembly_placements.get(key)
        if cached is not None:
            return deepcopy(cached)
        if snapshot is None or resolver is None:
            return None
        placement = resolver(snapshot, key)
        return placement.to_dict() if hasattr(placement, "to_dict") else deepcopy(dict(placement))

    def replace_assembly_placements(self, value: Mapping[str, object] | None) -> dict[str, dict[str, object]]:
        self._assembly_placements = deepcopy(dict(value or {}))
        self._prune_assembly_placements(self.available_parts)
        return self.assembly_placements_snapshot()

    def assembly_placements_snapshot(self) -> dict[str, dict[str, object]]:
        return deepcopy(self._assembly_placements)

    def resolve_and_store_assembly_placements(self, snapshot: Mapping[str, object], *, resolver=None) -> dict[str, dict[str, object]]:
        """Resolve every part supported by the authoritative placement owner.

        Unsupported base parts remain untouched; Door/inner-door/divider parts
        are not filtered here by UI naming rules, so the resolver remains the
        one authority as new physical derived parts are added.
        """
        result = self.assembly_placements_snapshot()
        if resolver is None:
            return result
        for stable_id in self.available_parts:
            key = str(stable_id)
            if self.custom_part(key) is not None:
                continue
            try:
                placement = resolver(snapshot, key)
            except ValueError:
                continue
            result[key] = placement.to_dict() if hasattr(placement, "to_dict") else deepcopy(dict(placement))
        self._assembly_placements = deepcopy(result)
        return self.assembly_placements_snapshot()

    def _drop_assembly_placements_for_removed_parts(self, removed_parts) -> None:
        """Discard placement descendants of a deleted physical parent.

        A child part's existence does not validate a world placement whose
        explicit parent is gone. Unrelated placements remain untouched.
        """
        removed_nodes = {str(key) for key in removed_parts}
        if not removed_nodes:
            return
        discarded = set()
        while True:
            newly_discarded = set()
            for key, value in self._assembly_placements.items():
                if key in discarded:
                    continue
                parent = (
                    value.get("parent_assembly_node")
                    if isinstance(value, dict)
                    else getattr(value, "parent_assembly_node", None)
                )
                # Saved placement parents are string node IDs. A malformed
                # list/dict/bool cannot be used for graph membership; drop the
                # bad placement and all descendants without interrupting removal.
                if (key in removed_nodes
                        or (parent is not None and not isinstance(parent, str))
                        or parent in removed_nodes):
                    newly_discarded.add(key)
            if not newly_discarded:
                break
            discarded.update(newly_discarded)
            removed_nodes.update(newly_discarded)
        for key in discarded:
            self._assembly_placements.pop(key, None)

    def _prune_assembly_placements(self, available_parts) -> None:
        allowed = set(available_parts)

        def _is_allowed(key, val):
            parent = (
                val.get("parent_assembly_node")
                if isinstance(val, dict)
                else getattr(val, "parent_assembly_node", None)
            )
            # Reject corrupt parent types even for otherwise available parts.
            # Legitimate virtual parents are strings handled by existing rules.
            if parent is not None and not isinstance(parent, str):
                return False
            if key in allowed:
                return True
            if parent and parent in allowed:
                return True
            prefix = str(key).split(":")[0]
            if prefix in allowed:
                return True
            if prefix == "inner_door" and "door" in allowed:
                return True
            return False

        self._assembly_placements = {
            key: value for key, value in self._assembly_placements.items()
            if _is_allowed(key, value)
        }

    def mark_dirty(self) -> None:
        self._dirty = True

    def mark_clean(self) -> None:
        self._dirty = False

    def shared_snapshot(self) -> dict[str, object]:
        """Return the shared workspace state without exposing mutable backing data."""
        return self._shared_state.snapshot()

    def export_shared_snapshot(self, *, live_active_profiles: Mapping[str, object] | None = None) -> dict[str, object]:
        """Project the shared owner once, with an optional live editor overlay."""
        result = self._shared_state.snapshot()
        # Complete live publication distinguishes clearing a retired owner map
        # from an unrelated partial Main workspace patch.
        result.setdefault(ROOT_PHYSICAL_OCCUPANCY_KEY, {})
        result.setdefault(ROOT_MARKING_STORE_KEY, normalize_workspace_root_marking_store(None))
        active = result.get("active_part")
        if active and active != MANDATORY_PART and live_active_profiles is not None:
            profiles = deepcopy(result["part_profiles"])
            profiles[str(active)] = deepcopy(dict(live_active_profiles or {}))
            result["part_profiles"] = profiles
        result["active_mode"] = self._active_mode
        if self._quantity_model is not None:
            result["quantity"] = self._quantity_model.snapshot()
        if self._receiving_quantity_box is not None:
            result["receiving_quantity_box"] = deepcopy(self._receiving_quantity_box)
        return result

    def snapshot(self) -> dict[str, object]:
        """Return the complete workspace payload used by save/reload adapters."""
        result = self._shared_state.snapshot()
        result.update({
            "part_features": self.part_features_snapshot(),
            "part_face_features": deepcopy(self._part_face_features),
            "assembly_placements": self.assembly_placements_snapshot(),
            "active_mode": self._active_mode,
        })
        if self._quantity_model is not None:
            result["quantity"] = self._quantity_model.snapshot()
        if self._receiving_quantity_box is not None:
            result["receiving_quantity_box"] = deepcopy(self._receiving_quantity_box)
        return result
