"""Narrow application capability owners for DM8-B1 (#1386).

Only the composition bootstrap observes the host.  Runtime owners retain
explicit ports, never an application/bridge/service bag; they do not own
geometry, project schema, persisted navigation, or Settings semantics.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, fields
from typing import Any


ReadPort = Callable[[], Any]
WritePort = Callable[[Any], None]


def _validate_ports(ports: object) -> None:
    for field in fields(ports):
        if not callable(getattr(ports, field.name)):
            raise TypeError(f"Capability port {field.name!r} must be callable")


@dataclass(frozen=True, slots=True)
class ProjectCapabilityPorts:
    export_callback: ReadPort
    flush_pending_settings: ReadPort
    route_export: Callable[..., Any]

    def __post_init__(self) -> None:
        _validate_ports(self)


class ProjectCapabilityOwner:
    def __init__(self, ports: ProjectCapabilityPorts):
        self._ports = ports

    def export_selected_dxf(self):
        return self._ports.route_export(
            self._ports.export_callback(),
            self._ports.flush_pending_settings,
        )


@dataclass(frozen=True, slots=True)
class SettingsCapabilityPorts:
    settings_values: ReadPort
    input_snapshot: ReadPort
    box_whd: ReadPort
    pending_settings: ReadPort
    service_factory: Callable[..., Any]

    def __post_init__(self) -> None:
        _validate_ports(self)


class SettingsCapabilityOwner:
    def __init__(self, ports: SettingsCapabilityPorts):
        self._ports = ports
        self._service = None

    def service(self):
        if self._service is None:
            ports = self._ports
            self._service = ports.service_factory(
                settings_values=ports.settings_values(),
                input_snapshot=ports.input_snapshot(),
                box_whd=ports.box_whd(),
                pending_settings=ports.pending_settings(),
            )
        return self._service


@dataclass(frozen=True, slots=True)
class WorkspaceCapabilityPorts:
    workspace: ReadPort
    current_controller: ReadPort
    remembered_child: ReadPort
    publish_controller: WritePort
    controller_type: Callable[..., Any]

    def __post_init__(self) -> None:
        _validate_ports(self)


class WorkspaceCapabilityOwner:
    def __init__(self, ports: WorkspaceCapabilityPorts):
        self._ports = ports
        self._controller = None

    def navigation(self):
        workspace = self._ports.workspace()
        controller = self._controller
        if controller is None or controller.workspace is not workspace:
            existing = self._ports.current_controller()
            if (
                isinstance(existing, self._ports.controller_type)
                and existing.workspace is workspace
            ):
                controller = existing
            else:
                controller = self._ports.controller_type(
                    workspace, remembered_box_body_child=self._ports.remembered_child()
                )
            self._controller = controller
            self._ports.publish_controller(controller)
        return controller


@dataclass(frozen=True, slots=True)
class RegistryCapabilityPorts:
    current_controller: ReadPort
    diagnostics_seed: ReadPort
    publish_controller: WritePort
    controller_type: Callable[..., Any]

    def __post_init__(self) -> None:
        _validate_ports(self)


class RegistryCapabilityOwner:
    def __init__(self, ports: RegistryCapabilityPorts):
        self._ports = ports
        self._controller = None

    def diagnostics(self):
        if self._controller is None:
            existing = self._ports.current_controller()
            if isinstance(existing, self._ports.controller_type):
                self._controller = existing
            else:
                seed = dict(self._ports.diagnostics_seed())
                self._controller = self._ports.controller_type(**seed)
            self._ports.publish_controller(self._controller)
        return self._controller


@dataclass(frozen=True, slots=True)
class ReceivingCapabilityPorts:
    input_snapshot: ReadPort
    current_adapter: ReadPort
    publish_adapter: WritePort
    canonical_family_name: Callable[..., str]

    def __post_init__(self) -> None:
        _validate_ports(self)


class ReceivingCapabilityOwner:
    def __init__(self, ports: ReceivingCapabilityPorts):
        self._ports = ports

    def applicable(self):
        return (
            self._ports.canonical_family_name(
                self._ports.input_snapshot() or {}
            ) == "受電箱"
        )

    def adapter(
        self, *, reset: bool, ensure_layout, stable_ids, adapter_type,
        confirm_destructive,
    ):
        if not self.applicable():
            return None
        snapshot = ensure_layout(self._ports.input_snapshot() or {})
        layout = snapshot.get("receiving_layout")
        if not isinstance(layout, Mapping):
            return None
        adapter = None if reset else self._ports.current_adapter()
        if adapter is None:
            adapter = adapter_type(
                layout,
                persisted_ids=stable_ids(layout),
                confirm_destructive=confirm_destructive,
            )
            self._ports.publish_adapter(adapter)
        return adapter


@dataclass(frozen=True, slots=True)
class AssemblyCornerCapabilityPorts:
    display_mode: ReadPort
    submit_update_intent: ReadPort

    def __post_init__(self) -> None:
        _validate_ports(self)


class AssemblyCornerCapabilityOwner:
    def __init__(self, ports: AssemblyCornerCapabilityPorts):
        self._ports = ports

    def refresh_if_assembly(self):
        if str(self._ports.display_mode() or "single") != "assembly":
            return False
        submit = self._ports.submit_update_intent()
        if callable(submit):
            submit("display", commit=True)
            return True
        return False


@dataclass(frozen=True, slots=True)
class FoldDesignerCapabilityOwners:
    project: ProjectCapabilityOwner
    settings: SettingsCapabilityOwner
    workspace: WorkspaceCapabilityOwner
    registry: RegistryCapabilityOwner
    receiving: ReceivingCapabilityOwner
    assembly_corner: AssemblyCornerCapabilityOwner


def build_capability_owners(app) -> FoldDesignerCapabilityOwners:
    """One-time wiring at the existing composition root; owners never store app."""
    from ae_engine.cabinet_types import policy as cabinet_family_policy
    from phase6_project_controller import Phase6ProjectController
    from phase6_registry_diagnostics_controller import Phase6RegistryDiagnosticsController
    from phase6_settings_service import Phase6SettingsTransactionService
    from phase6_workspace_navigation_controller import Phase6WorkspaceNavigationController

    return FoldDesignerCapabilityOwners(
        project=ProjectCapabilityOwner(ProjectCapabilityPorts(
            export_callback=lambda: getattr(app, "_phase6_export_selected_dxf_callback", None),
            flush_pending_settings=lambda: getattr(app, "flush_pending_settings")(),
            route_export=Phase6ProjectController.route_selected_dxf_export,
        )),
        settings=SettingsCapabilityOwner(SettingsCapabilityPorts(
            settings_values=lambda: getattr(app, "_settings_values", {}),
            input_snapshot=lambda: getattr(app, "_phase6_input_snapshot", {}),
            box_whd=lambda: getattr(app, "_phase6_box_whd", {}),
            pending_settings=lambda: getattr(app, "_phase6_pending_settings", {}),
            service_factory=Phase6SettingsTransactionService,
        )),
        workspace=WorkspaceCapabilityOwner(WorkspaceCapabilityPorts(
            workspace=lambda: getattr(app, "designer_workspace", None),
            current_controller=lambda: getattr(
                app, "_phase6_workspace_navigation_controller", None
            ),
            remembered_child=lambda: getattr(app, "__dict__", {}).get(
                "_phase6_box_body_active_piece_key"
            ),
            publish_controller=lambda controller: setattr(
                app, "_phase6_workspace_navigation_controller", controller
            ),
            controller_type=Phase6WorkspaceNavigationController,
        )),
        registry=RegistryCapabilityOwner(RegistryCapabilityPorts(
            current_controller=lambda: getattr(
                app, "_phase6_registry_diagnostics_controller", None
            ),
            diagnostics_seed=lambda: {
                "candidate_id": getattr(app, "_phase6_registry_candidate_id", ""),
                "candidate_record": getattr(app, "_phase6_registry_candidate_record", {}),
                "regression_evidence": getattr(
                    app, "_phase6_registry_regression_evidence", {}
                ),
                "rule_records": getattr(app, "_phase6_registry_rule_records", {}),
                "promotion_candidates": getattr(
                    app, "_phase6_last_relief_promotion_candidates", {}
                ),
            },
            publish_controller=lambda controller: setattr(
                app, "_phase6_registry_diagnostics_controller", controller
            ),
            controller_type=Phase6RegistryDiagnosticsController,
        )),
        receiving=ReceivingCapabilityOwner(ReceivingCapabilityPorts(
            input_snapshot=lambda: getattr(app, "_phase6_input_snapshot", {}),
            current_adapter=lambda: getattr(
                app, "_phase6_receiving_set_bay_adapter", None
            ),
            publish_adapter=lambda adapter: setattr(
                app, "_phase6_receiving_set_bay_adapter", adapter
            ),
            canonical_family_name=cabinet_family_policy.canonical_family_name,
        )),
        assembly_corner=AssemblyCornerCapabilityOwner(
            AssemblyCornerCapabilityPorts(
                display_mode=lambda: getattr(app, "_phase6_3d_display_mode", "single"),
                submit_update_intent=lambda: getattr(app, "submit_update_intent", None),
            )
        ),
    )
