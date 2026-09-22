"""Phase 5 Fold Designer Settings application sequencing boundary.

This module owns only application-level Settings sequencing ports and coordinator
identity. Canonical Settings semantics stay in the existing transaction owners;
geometry/manufacturing, workspace identity, presentation, and scheduling remain
owned by their established modules.
"""
from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Any, Callable


PortCallable = Callable[..., Any]


@dataclass(frozen=True)
class Phase6SettingsApplicationPorts:
    """Bounded application effects/read ports used by the Settings coordinator."""

    read_settings_snapshot: PortCallable
    read_profile_snapshot: PortCallable
    save_current_part: PortCallable
    apply_profile_plan: PortCallable
    sync_derived_parts: PortCallable
    project_ui_values: PortCallable
    render_bending: PortCallable
    refresh_settings_panel: PortCallable
    refresh_topology: PortCallable
    refresh_persistent_controls: PortCallable
    submit_update_intent: PortCallable
    publish_live_state: PortCallable
    project_status: PortCallable

    def __post_init__(self) -> None:
        for field in fields(self):
            value = getattr(self, field.name)
            if not callable(value):
                raise TypeError(
                    f"Settings application port {field.name!r} must be callable"
                )


class Phase6FoldDesignerSettingsCoordinator:
    """Application sequencing owner for Fold Designer Settings effects.

    T1 establishes the boundary only. Later Phase 5 tasks move sequencing into
    this owner without moving Settings semantics or domain calculations.
    """

    __slots__ = ("_transactions", "_ports")

    def __init__(self, *, transactions: Any, ports: Phase6SettingsApplicationPorts):
        if not isinstance(ports, Phase6SettingsApplicationPorts):
            raise TypeError("ports must be Phase6SettingsApplicationPorts")
        self._transactions = transactions
        self._ports = ports

    @property
    def transactions(self) -> Any:
        return self._transactions

    @property
    def ports(self) -> Phase6SettingsApplicationPorts:
        return self._ports


__all__ = [
    "Phase6SettingsApplicationPorts",
    "Phase6FoldDesignerSettingsCoordinator",
]
