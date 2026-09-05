# -*- coding: utf-8 -*-
"""Phase6 主 GUI committed workspace 的單一所有權模組。"""
from __future__ import annotations

from copy import deepcopy
from typing import Mapping

from phase6_workspace_state import PART_ORDER, SharedWorkspaceState, normalize_existing_parts


DEFAULT_EXISTING_PARTS = {"box_body", "head", "tail", "door", "base_plate"}


class Phase6WorkspaceController:
    """保存 Main committed workspace lifecycle；共同 invariant 委派 shared core。"""

    def __init__(self, *, default_existing_parts=None) -> None:
        defaults = DEFAULT_EXISTING_PARTS if default_existing_parts is None else default_existing_parts
        self._fallback_existing_parts = set(normalize_existing_parts(defaults))
        self._authoritative = False
        self._shared_state = SharedWorkspaceState(existing_parts=self._fallback_existing_parts, active_repair="first")
        self._box_body_profile: list | None = None
        self._assembly_placements: dict[str, dict[str, object]] = {}

    @staticmethod
    def _clone(value):
        return deepcopy(value)

    @staticmethod
    def _ordered(existing) -> list[str]:
        return list(normalize_existing_parts(existing))

    @classmethod
    def _normalize_existing(cls, existing) -> list[str]:
        return cls._ordered(existing)

    @property
    def has_authoritative_workspace(self) -> bool:
        return self._authoritative

    @property
    def active_part(self) -> str | None:
        return self._shared_state.active_part

    def raw_existing_parts(self) -> set[str]:
        if self._authoritative:
            return set(self._shared_state.existing_parts)
        return set(self._fallback_existing_parts)

    def current_existing_parts(self, *, indicator_box_enabled: bool = False) -> set[str]:
        if self._authoritative:
            existing = set(self._shared_state.existing_parts)
        else:
            existing = set(self._fallback_existing_parts)
            if indicator_box_enabled:
                existing.update({"indicator_box", "indicator_door"})
            else:
                existing.discard("indicator_box")
                existing.discard("indicator_door")
        existing.add("box_body")
        return existing

    def _sync_fallback_into_shared(self) -> None:
        self._shared_state.set_existing_parts(self._fallback_existing_parts, active_repair="first")

    def replace_legacy_existing_parts(self, existing_parts) -> set[str]:
        normalized = set(normalize_existing_parts(existing_parts))
        if self._authoritative:
            self._shared_state.set_existing_parts(normalized, active_repair="first")
        else:
            self._fallback_existing_parts = normalized
            self._sync_fallback_into_shared()
        return self.raw_existing_parts()

    def apply_authoritative_existing_parts(self, existing_parts) -> set[str]:
        """Replace exact physical presence without touching profile stash."""
        self._shared_state.set_existing_parts(existing_parts, active_repair="first")
        self._authoritative = True
        return set(self._shared_state.existing_parts)

    def set_part_presence(self, key: str, present: bool) -> set[str]:
        if self._authoritative:
            self._shared_state.set_part_presence(key, present, active_repair="first")
            return set(self._shared_state.existing_parts)
        candidate = str(key or "").strip()
        if not candidate:
            raise ValueError("板件名稱不得為空")
        if present:
            self._fallback_existing_parts.add(candidate)
        elif candidate != "box_body":
            self._fallback_existing_parts.discard(candidate)
        self._fallback_existing_parts.add("box_body")
        self._sync_fallback_into_shared()
        return set(self._fallback_existing_parts)

    def _repair_active_part(self) -> None:
        existing = self._shared_state.existing_parts if self._authoritative else tuple(normalize_existing_parts(self._fallback_existing_parts))
        self._shared_state.set_existing_parts(existing, active_repair="first")

    def set_active_part(self, key: str | None) -> str | None:
        # Existing committed-owner compatibility: invalid explicit hints do not
        # escape presence and repair to the first canonical part.
        return self._shared_state.set_active_part(key, invalid="first")

    def set_box_body_profile(self, profile) -> list | None:
        self._box_body_profile = None if profile is None else self._clone(list(profile))
        return self.box_body_profile()

    def box_body_profile(self) -> list | None:
        return self._clone(self._box_body_profile)

    def set_box_body_structure_state(self, state) -> dict:
        return self._shared_state.set_box_body_structure_state(state)

    def box_body_structure_state(self) -> dict:
        return self._shared_state.box_body_structure_state()

    def part_profiles_snapshot(self) -> dict:
        return self._shared_state.part_profiles_snapshot()

    def profile_for(self, key: str):
        return self._shared_state.profile_for(key)

    def commit_workspace(self, workspace: Mapping[str, object]) -> dict:
        raw = dict(workspace or {})
        existing = raw.get("existing_parts") if "existing_parts" in raw else (
            self._shared_state.existing_parts if self._authoritative else self._fallback_existing_parts
        )
        profiles = raw.get("part_profiles") if "part_profiles" in raw else self._shared_state.part_profiles_snapshot()
        structure = raw.get("box_body_structure") if "box_body_structure" in raw else self._shared_state.box_body_structure_state()
        requested_active = raw.get("active_part")
        self._shared_state.replace(
            existing_parts=existing,
            active_part=requested_active,
            part_profiles=profiles,
            box_body_structure=structure,
            active_repair="first",
        )
        self._authoritative = True
        if "box_body_profile" in raw:
            profile = raw.get("box_body_profile")
            self._box_body_profile = None if profile is None else self._clone(list(profile))
        if "assembly_placements" in raw:
            self._assembly_placements = self._clone(dict(raw.get("assembly_placements") or {}))
        return self.workspace_snapshot()

    def clear_authoritative_workspace(self) -> None:
        self._authoritative = False
        self._shared_state = SharedWorkspaceState(existing_parts=self._fallback_existing_parts, active_repair="first")
        self._box_body_profile = None
        self._assembly_placements = {}

    def assembly_placements_snapshot(self) -> dict[str, dict[str, object]]:
        return self._clone(getattr(self, "_assembly_placements", {}))

    def replace_assembly_placements(self, value: Mapping[str, object] | None) -> dict[str, dict[str, object]]:
        self._assembly_placements = self._clone(dict(value or {}))
        return self.assembly_placements_snapshot()

    def workspace_snapshot(self) -> dict:
        if not self._authoritative:
            self._sync_fallback_into_shared()
        result = self._shared_state.snapshot()
        result["box_body_profile"] = self.box_body_profile() or []
        snapshot = {
            "box_body_profile": result["box_body_profile"],
            "box_body_structure": result["box_body_structure"],
            "existing_parts": result["existing_parts"],
            "active_part": result["active_part"],
            "part_profiles": result["part_profiles"],
        }
        if getattr(self, "_assembly_placements", None):
            snapshot["assembly_placements"] = self._clone(self._assembly_placements)
        return snapshot

    def legacy_bundle(self) -> dict | None:
        if not self._authoritative:
            return None
        snapshot = self.workspace_snapshot()
        return {
            "existing_parts": snapshot["existing_parts"],
            "active_part": snapshot["active_part"],
            "part_profiles": snapshot["part_profiles"],
        }

    def load_legacy_bundle(self, bundle) -> dict | None:
        if bundle is None:
            self.clear_authoritative_workspace()
            return None
        raw = dict(bundle or {})
        return self.commit_workspace({
            "existing_parts": raw.get("existing_parts", self.raw_existing_parts()),
            "active_part": raw.get("active_part"),
            "part_profiles": raw.get("part_profiles", {}),
            **({"box_body_profile": raw["box_body_profile"]} if "box_body_profile" in raw else {}),
        })
