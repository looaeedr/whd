"""Phase 5 Fold Designer Settings application sequencing boundary.

This module owns only application-level Settings sequencing ports and coordinator
identity. Canonical Settings semantics stay in the existing transaction owners;
geometry/manufacturing, workspace identity, presentation, and scheduling remain
owned by their established modules.
"""
from __future__ import annotations

from dataclasses import dataclass, fields
from enum import Enum
from types import MappingProxyType
from typing import Any, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from phase6_settings_transaction_controller import Phase6SettingsTransactionController


PortCallable = Callable[..., Any]


class Phase6SettingsApplicationPortRole(str, Enum):
    READ = "read"
    MUTATION = "mutation"
    EFFECT = "effect"


@dataclass(frozen=True)
class Phase6SettingsApplicationPortSpec:
    role: Phase6SettingsApplicationPortRole
    canonical_owner: str
    callback_direction: str
    bootstrap_required: bool = False
    compatibility_only: bool = False

    def __post_init__(self) -> None:
        role = (
            self.role
            if isinstance(self.role, Phase6SettingsApplicationPortRole)
            else Phase6SettingsApplicationPortRole(str(self.role))
        )
        owner = str(self.canonical_owner or "").strip()
        direction = str(self.callback_direction or "").strip()
        if not owner:
            raise ValueError("canonical_owner must be non-empty")
        if direction not in {"owner_to_coordinator", "coordinator_to_owner"}:
            raise ValueError(
                "callback_direction must be owner_to_coordinator or coordinator_to_owner"
            )
        object.__setattr__(self, "role", role)
        object.__setattr__(self, "canonical_owner", owner)
        object.__setattr__(self, "callback_direction", direction)
        object.__setattr__(self, "bootstrap_required", bool(self.bootstrap_required))
        object.__setattr__(self, "compatibility_only", bool(self.compatibility_only))


SETTINGS_APPLICATION_PORT_SPECS = MappingProxyType(
    {
        "read_settings_snapshot": Phase6SettingsApplicationPortSpec(
            role=Phase6SettingsApplicationPortRole.READ,
            canonical_owner="Phase6SettingsTransactionController",
            callback_direction="owner_to_coordinator",
        ),
        "read_profile_snapshot": Phase6SettingsApplicationPortSpec(
            role=Phase6SettingsApplicationPortRole.READ,
            canonical_owner="Phase6DesignerWorkspace",
            callback_direction="owner_to_coordinator",
        ),
        "save_current_part": Phase6SettingsApplicationPortSpec(
            role=Phase6SettingsApplicationPortRole.EFFECT,
            canonical_owner="#448 Part Editor compatibility",
            callback_direction="coordinator_to_owner",
            compatibility_only=True,
        ),
        "apply_profile_plan": Phase6SettingsApplicationPortSpec(
            role=Phase6SettingsApplicationPortRole.MUTATION,
            canonical_owner="Phase6WorkspaceNavigationController",
            callback_direction="coordinator_to_owner",
        ),
        "sync_derived_parts": Phase6SettingsApplicationPortSpec(
            role=Phase6SettingsApplicationPortRole.MUTATION,
            canonical_owner="Phase6WorkspaceNavigationController",
            callback_direction="coordinator_to_owner",
        ),
        "project_ui_values": Phase6SettingsApplicationPortSpec(
            role=Phase6SettingsApplicationPortRole.EFFECT,
            canonical_owner="Fold Designer presentation",
            callback_direction="coordinator_to_owner",
        ),
        "render_bending": Phase6SettingsApplicationPortSpec(
            role=Phase6SettingsApplicationPortRole.EFFECT,
            canonical_owner="BendingUI",
            callback_direction="coordinator_to_owner",
        ),
        "refresh_settings_panel": Phase6SettingsApplicationPortSpec(
            role=Phase6SettingsApplicationPortRole.EFFECT,
            canonical_owner="Phase6SettingsPanel",
            callback_direction="coordinator_to_owner",
        ),
        "refresh_topology": Phase6SettingsApplicationPortSpec(
            role=Phase6SettingsApplicationPortRole.EFFECT,
            canonical_owner="Fold Designer application composition",
            callback_direction="coordinator_to_owner",
        ),
        "refresh_persistent_controls": Phase6SettingsApplicationPortSpec(
            role=Phase6SettingsApplicationPortRole.EFFECT,
            canonical_owner="Fold Designer application composition",
            callback_direction="coordinator_to_owner",
        ),
        "submit_update_intent": Phase6SettingsApplicationPortSpec(
            role=Phase6SettingsApplicationPortRole.EFFECT,
            canonical_owner="gui_modules.application.command_router",
            callback_direction="coordinator_to_owner",
        ),
        "publish_live_state": Phase6SettingsApplicationPortSpec(
            role=Phase6SettingsApplicationPortRole.EFFECT,
            canonical_owner="Fold Designer live-sync effect layer",
            callback_direction="coordinator_to_owner",
        ),
        "project_status": Phase6SettingsApplicationPortSpec(
            role=Phase6SettingsApplicationPortRole.EFFECT,
            canonical_owner="Fold Designer presentation",
            callback_direction="coordinator_to_owner",
        ),
    }
)


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

    def __init__(
        self,
        *,
        transactions: "Phase6SettingsTransactionController",
        ports: Phase6SettingsApplicationPorts,
    ):
        if not isinstance(ports, Phase6SettingsApplicationPorts):
            raise TypeError("ports must be Phase6SettingsApplicationPorts")
        self._transactions = transactions
        self._ports = ports

    def apply_updates(
        self,
        updates,
        *,
        notify: bool = True,
        external_apply_guard: bool = False,
    ) -> dict[str, Any]:
        """Apply one Settings commit while owning only application effect order."""
        clean = dict(
            self._transactions.normalize_updates(
                updates,
                external_apply_guard=bool(external_apply_guard),
            )
            or {}
        )
        if not clean:
            return {}

        if "w" in clean:
            snapshot = self._ports.read_settings_snapshot()
            box_whd = getattr(snapshot, "box_whd", {}) or {}
            previous_w = float(box_whd.get("w", clean["w"]))
            try:
                self._transactions.commit_reconciled_width_structure(clean["w"])
            except Exception as exc:
                clean.pop("w", None)
                self._transactions.restore_setting("w", previous_w)
                self._ports.project_ui_values(
                    {"w": previous_w},
                    rejected_key="w",
                    error=str(exc),
                )
                if not clean:
                    return {}

        try:
            self._ports.save_current_part()
        except Exception:
            # Compatibility owner historically treats editor-save failure as
            # non-fatal for Settings application.
            pass

        committed = dict(self._transactions.commit_settings(clean) or {})
        if not committed:
            return {}

        self._ports.apply_profile_plan(committed)
        self._ports.project_ui_values(committed)
        self._ports.submit_update_intent(committed)
        if notify:
            self._ports.publish_live_state(committed)
        return committed

    @property
    def transactions(self) -> "Phase6SettingsTransactionController":
        return self._transactions

    @property
    def ports(self) -> Phase6SettingsApplicationPorts:
        return self._ports


__all__ = [
    "Phase6SettingsApplicationPortRole",
    "Phase6SettingsApplicationPortSpec",
    "SETTINGS_APPLICATION_PORT_SPECS",
    "Phase6SettingsApplicationPorts",
    "Phase6FoldDesignerSettingsCoordinator",
]
