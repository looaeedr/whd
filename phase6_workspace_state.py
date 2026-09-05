# -*- coding: utf-8 -*-
"""Phase6 committed/draft 共用的純 workspace state contract。

本模組只擁有 presence / active / profile stash / box-body structure 的共同
資料形狀與 invariant。它不知道 Main/Designer 生命週期，也不保存跨 owner
共享的 mutable singleton。
"""
from __future__ import annotations

from copy import deepcopy
from typing import Mapping

from phase6_box_body_structure import normalize_box_body_structure_state


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
    """Four-field state contract instantiated independently by each lifecycle owner."""

    def __init__(
        self,
        *,
        existing_parts=None,
        active_part=None,
        part_profiles: Mapping[str, object] | None = None,
        box_body_structure=None,
        active_repair: str = "first",
    ) -> None:
        self._existing_parts = list(normalize_existing_parts(existing_parts or (MANDATORY_PART,)))
        self._active_part = _repair_active(active_part, self._existing_parts, active_repair)
        self._part_profiles = deepcopy(dict(part_profiles or {}))
        self._box_body_structure = normalize_box_body_structure_state(box_body_structure)

    @property
    def existing_parts(self) -> tuple[str, ...]:
        return tuple(self._existing_parts)

    @property
    def active_part(self) -> str | None:
        return self._active_part

    def set_existing_parts(self, values, *, active_repair: str) -> tuple[str, ...]:
        self._existing_parts = list(normalize_existing_parts(values))
        self._active_part = _repair_active(self._active_part, self._existing_parts, active_repair)
        return self.existing_parts

    def set_part_presence(self, key: str, present: bool, *, active_repair: str) -> tuple[str, ...]:
        candidate = str(key or "").strip()
        if not candidate:
            raise ValueError("板件名稱不得為空")
        values = list(self._existing_parts)
        if present:
            if candidate not in values:
                values.append(candidate)
        elif candidate != MANDATORY_PART:
            values = [item for item in values if item != candidate]
        return self.set_existing_parts(values, active_repair=active_repair)

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
        active_repair: str,
    ) -> dict:
        self._existing_parts = list(normalize_existing_parts(existing_parts))
        self._active_part = _repair_active(active_part, self._existing_parts, active_repair)
        self._part_profiles = deepcopy(dict(part_profiles or {}))
        self._box_body_structure = normalize_box_body_structure_state(box_body_structure)
        return self.snapshot()

    def snapshot(self) -> dict:
        return {
            "existing_parts": list(self._existing_parts),
            "active_part": self._active_part,
            "part_profiles": self.part_profiles_snapshot(),
            "box_body_structure": self.box_body_structure_state(),
        }
