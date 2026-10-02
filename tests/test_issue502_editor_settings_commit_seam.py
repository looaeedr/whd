from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

from gui_modules.application.fold_designer_settings_coordinator import (
    Phase6FoldDesignerSettingsCoordinator,
    Phase6SettingsApplicationPorts,
)
from phase6_settings_contracts import SettingsStateSnapshot


BRIDGE = Path("fold_designer_bridge.py")
COORDINATOR = Path("gui_modules/application/fold_designer_settings_coordinator.py")
PART_EDITOR_SESSION = Path("phase6_part_editor_session.py")


def _function_source(path: Path, name: str) -> str:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    node = next(
        item
        for item in tree.body
        if isinstance(item, ast.FunctionDef) and item.name == name
    )
    return ast.get_source_segment(source, node) or ""


def _coordinator_method_source(name: str) -> str:
    source = COORDINATOR.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(COORDINATOR))
    cls = next(
        item
        for item in tree.body
        if isinstance(item, ast.ClassDef)
        and item.name == "Phase6FoldDesignerSettingsCoordinator"
    )
    node = next(
        item
        for item in cls.body
        if isinstance(item, ast.FunctionDef) and item.name == name
    )
    return ast.get_source_segment(source, node) or ""


def test_issue502_coordinator_owns_editor_value_settings_commit_sequence():
    source = COORDINATOR.read_text(encoding="utf-8")
    assert "def commit_editor_values(" in source, (
        "RED R5: Settings coordinator does not own editor-value commit sequencing"
    )
    method = _coordinator_method_source("commit_editor_values")
    assert "normalize_updates(" in method
    assert "commit_settings(" in method
    assert "project_ui_values(" in method
    assert "apply_profile_plan(" in method
    assert "publish_live_state(" in method


def test_issue502_bridge_store_editor_values_is_narrow_coordinator_delegate():
    source = _function_source(BRIDGE, "_phase6_store_editor_values")
    assert "_phase6_settings_coordinator(self).commit_editor_values" in source
    forbidden = (
        "normalize_ui_text_size(",
        "commit_box_fw(",
        "self._phase6_input_snapshot.update(",
        "self._settings_values[",
        "self._phase6_box_whd[",
        "_phase6_recalculate_part_dimensions(",
        "_phase6_refresh_linked_part_profiles(",
        "self._settings_change_callback(",
    )
    assert [token for token in forbidden if token in source] == []


def test_issue502_coordinator_noop_does_not_notify_and_changed_commit_is_partial():
    events = []
    state = {"w": 400.0, "h": 600.0, "fw": 25.0}

    class Transactions:
        def normalize_updates(self, values, *, external_apply_guard=False):
            result = {}
            for key, value in dict(values or {}).items():
                if key in state:
                    result[key] = float(value)
            return result

        def commit_settings(self, values):
            state.update(dict(values or {}))
            events.append(("commit", dict(values or {})))
            return dict(values or {})

    def noop(*args, **kwargs):
        events.append(("noop", args, kwargs))

    ports = Phase6SettingsApplicationPorts(
        read_settings_snapshot=lambda: SettingsStateSnapshot(
            settings_values=state,
            input_snapshot=state,
            box_whd={"w": state["w"], "h": state["h"]},
        ),
        read_profile_snapshot=lambda: {},
        save_current_part=noop,
        apply_profile_plan=lambda values, **kwargs: events.append(
            ("profile", dict(values), dict(kwargs))
        ),
        sync_derived_parts=noop,
        project_ui_values=lambda values, **kwargs: events.append(
            ("ui", dict(values), dict(kwargs))
        ),
        render_bending=noop,
        refresh_settings_panel=noop,
        refresh_topology=noop,
        refresh_persistent_controls=noop,
        submit_update_intent=noop,
        publish_live_state=lambda values, **kwargs: events.append(
            ("publish", dict(values), dict(kwargs))
        ),
        project_status=noop,
    )
    owner = Phase6FoldDesignerSettingsCoordinator(
        transactions=Transactions(),
        ports=ports,
    )

    changed = owner.commit_editor_values({"w": 400.0}, notify=True)
    assert changed == {}
    assert not [event for event in events if event[0] == "publish"]

    events.clear()
    changed = owner.commit_editor_values(
        {"w": 420.0, "h": 600.0},
        notify=True,
    )
    assert changed == {"w": 420.0}
    publishes = [event for event in events if event[0] == "publish"]
    assert publishes == [("publish", {"w": 420.0}, {"partial": True})]


def test_issue502_editor_commit_uses_existing_effect_ports_for_fw_and_linked_refresh():
    method = _coordinator_method_source("commit_editor_values")
    assert "editor_changed_keys=" in method
    assert "editor_commit=True" in method
    assert "partial=True" in method
    assert "commit_box_fw" not in method
    assert "_phase6_refresh_linked_part_profiles" not in method


def test_issue502_part_editor_and_linked_endcap_keep_decisions_do_not_move():
    assert not PART_EDITOR_SESSION.exists()
    bridge = BRIDGE.read_text(encoding="utf-8")
    assert "def _fix11_save_current_part(" in bridge
    assert "def _fix11_activate_part(" in bridge
    linked = _function_source(BRIDGE, "_phase6_rebuild_linked_endcaps")
    assert "build_linked_endcap_xy_profiles" in linked
    assert "designer_workspace.stash_profiles" in linked
