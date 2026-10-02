from __future__ import annotations

import ast
from pathlib import Path

from phase6_settings_contracts import SettingsStateSnapshot
from gui_modules.application.fold_designer_settings_coordinator import (
    Phase6FoldDesignerSettingsCoordinator,
    Phase6SettingsApplicationPorts,
)


BRIDGE = Path("fold_designer_bridge.py")


class FakeTransactions:
    def __init__(self, events, *, reject_width=False):
        self.events = events
        self.reject_width = reject_width

    def normalize_updates(self, updates, *, external_apply_guard=False):
        self.events.append(("normalize", dict(updates), bool(external_apply_guard)))
        return {str(k): v for k, v in dict(updates).items()}

    def commit_reconciled_width_structure(self, value):
        self.events.append(("reconcile_width", value))
        if self.reject_width:
            raise ValueError("illegal split")

    def restore_setting(self, key, value):
        self.events.append(("restore", key, value))

    def commit_settings(self, updates):
        self.events.append(("commit", dict(updates)))
        return dict(updates)


def _ports(events, *, previous_w=800.0):
    return Phase6SettingsApplicationPorts(
        read_settings_snapshot=lambda: SettingsStateSnapshot(
            settings_values={"w": previous_w},
            box_whd={"w": previous_w},
        ),
        read_profile_snapshot=lambda: {},
        save_current_part=lambda: events.append(("save_current_part",)),
        apply_profile_plan=lambda updates: events.append(
            ("apply_profile_plan", dict(updates))
        ),
        sync_derived_parts=lambda *args, **kwargs: events.append(
            ("sync_derived_parts", args, kwargs)
        ),
        project_ui_values=lambda updates, **kwargs: events.append(
            ("project_ui_values", dict(updates), dict(kwargs))
        ),
        render_bending=lambda: events.append(("render_bending",)),
        refresh_settings_panel=lambda: events.append(("refresh_settings_panel",)),
        refresh_topology=lambda: events.append(("refresh_topology",)),
        refresh_persistent_controls=lambda: events.append(
            ("refresh_persistent_controls",)
        ),
        submit_update_intent=lambda updates: events.append(
            ("submit_update_intent", dict(updates))
        ),
        publish_live_state=lambda updates: events.append(
            ("publish_live_state", dict(updates))
        ),
        project_status=lambda *args, **kwargs: events.append(
            ("project_status", args, kwargs)
        ),
    )


def test_issue499_coordinator_owns_normal_apply_update_ordering():
    events = []
    transactions = FakeTransactions(events)
    coordinator = Phase6FoldDesignerSettingsCoordinator(
        transactions=transactions,
        ports=_ports(events),
    )

    assert hasattr(coordinator, "apply_updates"), (
        "RED: coordinator missing apply_updates sequencing owner"
    )
    result = coordinator.apply_updates(
        {"w": 900.0, "t": 2.0},
        notify=True,
        external_apply_guard=False,
    )

    assert result == {"w": 900.0, "t": 2.0}
    assert events == [
        ("normalize", {"w": 900.0, "t": 2.0}, False),
        ("reconcile_width", 900.0),
        ("save_current_part",),
        ("commit", {"w": 900.0, "t": 2.0}),
        ("apply_profile_plan", {"w": 900.0, "t": 2.0}),
        ("project_ui_values", {"w": 900.0, "t": 2.0}, {}),
        ("submit_update_intent", {"w": 900.0, "t": 2.0}),
        ("publish_live_state", {"w": 900.0, "t": 2.0}),
    ]


def test_issue499_width_reject_restores_and_continues_other_updates():
    events = []
    transactions = FakeTransactions(events, reject_width=True)
    coordinator = Phase6FoldDesignerSettingsCoordinator(
        transactions=transactions,
        ports=_ports(events, previous_w=800.0),
    )

    assert hasattr(coordinator, "apply_updates"), (
        "RED: coordinator missing apply_updates sequencing owner"
    )
    result = coordinator.apply_updates(
        {"w": 120.0, "h": 1800.0},
        notify=False,
        external_apply_guard=True,
    )

    assert result == {"h": 1800.0}
    assert events[0:4] == [
        ("normalize", {"w": 120.0, "h": 1800.0}, True),
        ("reconcile_width", 120.0),
        ("restore", "w", 800.0),
        (
            "project_ui_values",
            {"w": 800.0},
            {"error": "illegal split", "rejected_key": "w"},
        ),
    ]
    assert ("commit", {"h": 1800.0}) in events
    assert ("apply_profile_plan", {"h": 1800.0}) in events
    assert ("project_ui_values", {"h": 1800.0}, {}) in events
    assert ("submit_update_intent", {"h": 1800.0}) in events
    assert not any(event[0] == "publish_live_state" for event in events)


def test_issue499_empty_normalization_has_no_effects():
    events = []

    class EmptyTransactions(FakeTransactions):
        def normalize_updates(self, updates, *, external_apply_guard=False):
            self.events.append(("normalize", dict(updates), bool(external_apply_guard)))
            return {}

    coordinator = Phase6FoldDesignerSettingsCoordinator(
        transactions=EmptyTransactions(events),
        ports=_ports(events),
    )
    assert hasattr(coordinator, "apply_updates"), (
        "RED: coordinator missing apply_updates sequencing owner"
    )
    assert coordinator.apply_updates({}, notify=True) == {}
    assert events == [("normalize", {}, False)]


def _function(tree: ast.Module, name: str):
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"missing {name}")


def test_issue499_bridge_apply_function_is_narrow_coordinator_delegate():
    tree = ast.parse(BRIDGE.read_text(encoding="utf-8"), filename=str(BRIDGE))
    fn = _function(tree, "_phase6_apply_setting_updates")
    source = ast.get_source_segment(BRIDGE.read_text(encoding="utf-8"), fn) or ""

    forbidden = (
        "normalize_updates",
        "commit_reconciled_width_structure",
        "restore_setting",
        "commit_settings",
        "_save_current_part",
        "_phase6_refresh_profiles_from_settings",
        "after_cancel",
        "do_update",
        "_settings_change_callback",
        "_phase6_settings_guard",
    )
    remaining = [token for token in forbidden if token in source]
    assert remaining == [], (
        "RED: bridge still owns deep apply/update sequencing: "
        f"{remaining}"
    )
    assert "apply_updates" in source
