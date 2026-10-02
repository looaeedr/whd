"""Phase6 3D Designer 草稿工作區的純狀態 owner。"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from phase6_box_body_structure import normalize_box_body_structure_state, legacy_box_body_structure_locked
from phase6_workspace_state import MANDATORY_PART, SharedWorkspaceState


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
    ) -> None:
        self._shared_state = shared_state or SharedWorkspaceState(active_repair="none")
        self._selected_part = selected_part
        self._part_features = deepcopy(dict(part_features or {}))
        self._part_face_features = deepcopy(dict(part_face_features or {}))
        self._assembly_placements = deepcopy(dict(assembly_placements or {}))
        self._dirty = bool(dirty)
        self._switching = bool(switching)

    @classmethod
    def from_snapshot(cls, snapshot: Mapping[str, object] | None) -> "Phase6DesignerWorkspace":
        source = dict(snapshot or {})
        raw_structure = (
            (source.get("workspace") or {}).get("box_body_structure", source.get("box_body_structure"))
            if isinstance(source.get("workspace"), Mapping) else source.get("box_body_structure")
        )
        structure = normalize_box_body_structure_state(
            raw_structure,
            legacy_locked=legacy_box_body_structure_locked(source.get("model")),
        )
        ws_source = source.get("workspace") if isinstance(source.get("workspace"), Mapping) else {}
        shared = SharedWorkspaceState(
            existing_parts=source.get("existing_parts") or ws_source.get("existing_parts") or (MANDATORY_PART,),
            active_part=source.get("active_part") or ws_source.get("active_part"),
            part_profiles=source.get("part_profiles") or ws_source.get("part_profiles"),
            box_body_structure=structure,
            active_repair="none",
        )
        return cls(
            shared_state=shared,
            selected_part=None,
            part_features=source.get("part_features") or ws_source.get("part_features"),
            part_face_features=source.get("part_face_features") or ws_source.get("part_face_features"),
            assembly_placements=source.get("assembly_placements") or ws_source.get("assembly_placements"),
            dirty=False,
            switching=False,
        )

    @property
    def available_parts(self) -> tuple[str, ...]:
        return self._shared_state.existing_parts

    def replace_available_parts(self, values) -> tuple[str, ...]:
        parts = self._shared_state.set_existing_parts(values, active_repair="none")
        if self._selected_part not in parts:
            self._selected_part = None
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

    def add_part(
        self,
        key: str,
        *,
        default_profiles: Mapping[str, object] | None = None,
        default_features=(),
        default_face_features: Mapping[str, object] | None = None,
    ) -> bool:
        key = str(key or "").strip()
        if not key:
            raise ValueError("板件名稱不得為空")
        if key in self.available_parts:
            return False
        self._shared_state.set_part_presence(key, True, active_repair="none")
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
        self._shared_state.set_part_presence(key, False, active_repair="none")
        if self._selected_part == key:
            self._selected_part = None
        self._assembly_placements.pop(key, None)
        self._dirty = True
        return True

    def stash_profiles(self, key: str, profiles: Mapping[str, object]) -> None:
        if self._shared_state.stash_profiles(key, profiles):
            self._dirty = True

    def profiles_for(self, key: str, default=None):
        return self._shared_state.profile_for(key, default)

    def stash_features(self, key: str, features) -> None:
        key = str(key or "")
        copied = deepcopy(list(features or ()))
        if self._part_features.get(key) != copied:
            self._part_features[key] = copied
            self._dirty = True

    def features_for(self, key: str) -> list[Any]:
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
        return deepcopy(self._part_features)

    def replace_part_features(self, value: Mapping[str, object] | None) -> dict[str, list[Any]]:
        self._part_features = deepcopy(dict(value or {}))
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
            try:
                placement = resolver(snapshot, key)
            except ValueError:
                continue
            result[key] = placement.to_dict() if hasattr(placement, "to_dict") else deepcopy(dict(placement))
        self._assembly_placements = deepcopy(result)
        return self.assembly_placements_snapshot()

    def _prune_assembly_placements(self, available_parts) -> None:
        allowed = set(available_parts)

        def _is_allowed(key, val):
            if key in allowed:
                return True
            parent = (
                val.get("parent_assembly_node")
                if isinstance(val, dict)
                else getattr(val, "parent_assembly_node", None)
            )
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
        active = result.get("active_part")
        if active and active != MANDATORY_PART and live_active_profiles is not None:
            profiles = deepcopy(result["part_profiles"])
            profiles[str(active)] = deepcopy(dict(live_active_profiles or {}))
            result["part_profiles"] = profiles
        return result

    def snapshot(self) -> dict[str, object]:
        """Return the complete workspace payload used by save/reload adapters."""
        result = self._shared_state.snapshot()
        result.update({
            "part_features": deepcopy(self._part_features),
            "part_face_features": deepcopy(self._part_face_features),
            "assembly_placements": self.assembly_placements_snapshot(),
        })
        return result
