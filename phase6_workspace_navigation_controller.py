# -*- coding: utf-8 -*-
"""Phase 3 application-level workspace/navigation command owner.

This module coordinates state transitions over Phase6DesignerWorkspace and the
pure DM7 navigation resolver. It deliberately owns no Tk widget, renderer,
manufacturing solver, project I/O, or bridge callback.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from phase6_part_navigation import (
    NavigationIntent,
    NavigationMemory,
    NavigationRequest,
    is_box_body_physical_piece_key,
    resolve_navigation,
)
from phase6_derived_part_projection import (
    DerivedPartSyncPlan,
    materialize_features as _materialize_derived_features,
    materialize_namespace as _materialize_derived_namespace,
    materialize_profiles as _materialize_derived_profiles,
)


@dataclass(frozen=True)
class WorkspaceActivationPlan:
    requested_key: str
    resolved_key: str | None
    previous_active: str | None
    accepted: bool
    save_outgoing: bool
    noop: bool
    reason: str


@dataclass(frozen=True)
class WorkspaceMutationResult:
    key: str
    changed: bool
    was_active: bool = False
    fallback_key: str | None = None


class Phase6WorkspaceNavigationController:
    """Own application-level workspace/navigation transition decisions."""

    def __init__(self, workspace, *, remembered_box_body_child: str | None = None) -> None:
        self._workspace = workspace
        self._memory = NavigationMemory(
            str(remembered_box_body_child) if remembered_box_body_child else None
        )

    @property
    def workspace(self):
        return self._workspace

    @property
    def available_parts(self) -> tuple[str, ...]:
        return tuple(getattr(self._workspace, "available_parts", ()) or ())

    @property
    def active_part(self) -> str | None:
        return getattr(self._workspace, "active_part", None)

    @property
    def selected_part(self) -> str | None:
        return getattr(self._workspace, "selected_part", None)

    @property
    def switching(self) -> bool:
        return bool(getattr(self._workspace, "switching", False))

    @property
    def remembered_box_body_child(self) -> str | None:
        return self._memory.remembered_box_body_child

    @remembered_box_body_child.setter
    def remembered_box_body_child(self, value: str | None) -> None:
        self._memory = NavigationMemory(str(value) if value else None)

    @property
    def supports_derived_sync(self) -> bool:
        return callable(getattr(self._workspace, "sync_derived_parts", None))

    def has_part(self, key: str | None) -> bool:
        return str(key or "") in self.available_parts

    def resolve_operator_part(self, key: str | None) -> str | None:
        projection = resolve_navigation(
            self.available_parts,
            NavigationRequest(
                str(key or "") or None,
                NavigationIntent.EXPLICIT_SELECT,
            ),
            self._memory,
        )
        self._memory = projection.memory
        return projection.resolved_key

    def select_part(self, key: str) -> bool:
        selected = bool(self._workspace.select_part(str(key or "")))
        if selected and is_box_body_physical_piece_key(key):
            self.remembered_box_body_child = str(key)
        return selected

    def clear_selection(self) -> None:
        self._workspace.selected_part = None

    def plan_activation(
        self,
        key: str,
        *,
        initial: bool,
        leaving_non_single_view: bool,
    ) -> WorkspaceActivationPlan:
        requested = str(key or "")
        previous = self.active_part
        if requested not in self.available_parts:
            return WorkspaceActivationPlan(
                requested_key=requested,
                resolved_key=None,
                previous_active=previous,
                accepted=False,
                save_outgoing=False,
                noop=False,
                reason="PART_NOT_PRESENT",
            )
        noop = (
            requested == previous
            and not initial
            and not bool(leaving_non_single_view)
        )
        return WorkspaceActivationPlan(
            requested_key=requested,
            resolved_key=requested,
            previous_active=previous,
            accepted=True,
            save_outgoing=(not initial and previous is not None and not noop),
            noop=noop,
            reason="NOOP" if noop else "OK",
        )

    def begin_activation(self, plan: WorkspaceActivationPlan) -> bool:
        if not plan.accepted or plan.noop or not plan.resolved_key:
            return False
        self._workspace.begin_switch(plan.resolved_key)
        if is_box_body_physical_piece_key(plan.resolved_key):
            self.remembered_box_body_child = plan.resolved_key
        return True

    def finish_activation(self) -> None:
        self._workspace.finish_switch()

    def add_part(
        self,
        key: str,
        *,
        default_profiles: Mapping[str, object] | None = None,
        default_features=(),
        default_face_features: Mapping[str, object] | None = None,
    ) -> WorkspaceMutationResult:
        candidate = str(key or "")
        changed = bool(self._workspace.add_part(
            candidate,
            default_profiles=default_profiles,
            default_features=default_features,
            default_face_features=default_face_features,
        ))
        return WorkspaceMutationResult(key=candidate, changed=changed)

    def remove_part(self, key: str) -> WorkspaceMutationResult:
        candidate = str(key or "")
        was_active = self.active_part == candidate
        changed = bool(self._workspace.remove_part(candidate))
        if self.remembered_box_body_child == candidate:
            self.remembered_box_body_child = None
        return WorkspaceMutationResult(
            key=candidate,
            changed=changed,
            was_active=was_active,
            fallback_key="box_body" if changed and was_active else None,
        )

    def set_switching(self, value: bool) -> None:
        self._workspace.switching = bool(value)

    def set_active_part(self, value: str | None) -> None:
        self._workspace.active_part = value
        if is_box_body_physical_piece_key(value):
            self.remembered_box_body_child = str(value)

    def set_selected_part(self, value: str | None) -> None:
        self._workspace.selected_part = value
        if is_box_body_physical_piece_key(value):
            self.remembered_box_body_child = str(value)

    def stash_profiles(self, key: str, profiles: Mapping[str, object]) -> None:
        self._workspace.stash_profiles(str(key), profiles)

    def stash_features(self, key: str, features) -> None:
        self._workspace.stash_features(str(key), features)

    def stash_face_features(self, key: str, features: Mapping[str, object]) -> None:
        self._workspace.stash_face_features(str(key), features)

    def sync_derived_parts(
        self,
        *,
        namespace: str,
        part_profiles: Mapping[str, object],
    ) -> tuple[str, ...]:
        sync = getattr(self._workspace, "sync_derived_parts", None)
        if not callable(sync):
            return ()
        return tuple(sync(namespace=namespace, part_profiles=part_profiles))

    def apply_derived_sync_plan(self, plan: DerivedPartSyncPlan) -> None:
        """Apply an already-derived immutable topology plan through the sole mutation owner."""
        if not isinstance(plan, DerivedPartSyncPlan):
            raise TypeError("plan must be DerivedPartSyncPlan")

        for key in plan.remove_part_keys:
            self.remove_part(key)
        for projection in plan.namespaces:
            self.sync_derived_parts(
                namespace=projection.namespace,
                part_profiles=_materialize_derived_namespace(projection),
            )
        for projection in plan.stash_features:
            self.stash_features(
                projection.part_key,
                _materialize_derived_features(projection),
            )
        for projection in plan.add_parts:
            self.add_part(
                projection.part_key,
                default_profiles=_materialize_derived_profiles(projection),
            )
        for projection in plan.stash_profiles:
            self.stash_profiles(
                projection.part_key,
                _materialize_derived_profiles(projection),
            )
        if plan.active_part_repair is not None:
            self.set_active_part(plan.active_part_repair)
        if plan.selected_part_repair is not None:
            self.set_selected_part(plan.selected_part_repair)

    def mark_dirty(self) -> None:
        marker = getattr(self._workspace, "mark_dirty", None)
        if callable(marker):
            marker()

    def mark_clean(self) -> None:
        marker = getattr(self._workspace, "mark_clean", None)
        if callable(marker):
            marker()
