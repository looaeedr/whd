from __future__ import annotations

import ast
from pathlib import Path


def _state():
    return (
        {"w": 500.0, "h": 600.0, "ui_text_size": "small", "flag": False},
        {"w": 500.0, "h": 600.0, "ui_text_size": "small", "flag": False},
        {"w": 500.0, "h": 600.0, "d": 200.0},
        {},
    )


def test_t2a_stage_is_immediate_and_debounce_decision_is_pure():
    from phase6_settings_transaction_controller import Phase6SettingsTransactionController

    settings, snapshot, box, pending = _state()
    owner = Phase6SettingsTransactionController(
        settings_values=settings,
        input_snapshot=snapshot,
        box_whd=box,
        pending_settings=pending,
        debounce_job="old-job",
    )

    plan = owner.stage_setting_update("w", 640.0)

    assert plan.changed is True
    assert plan.cancel_job == "old-job"
    assert plan.schedule_after_ms == 150
    assert settings["w"] == 640.0
    assert snapshot["w"] == 640.0
    assert pending == {"w": 640.0}


def test_t2a_equivalent_stage_does_not_schedule_or_write():
    from phase6_settings_transaction_controller import Phase6SettingsTransactionController

    settings, snapshot, box, pending = _state()
    owner = Phase6SettingsTransactionController(
        settings_values=settings,
        input_snapshot=snapshot,
        box_whd=box,
        pending_settings=pending,
        debounce_job="old-job",
    )
    before = (dict(settings), dict(snapshot), dict(pending))

    plan = owner.stage_setting_update("w", 500.0)

    assert plan.changed is False
    assert plan.cancel_job is None
    assert plan.schedule_after_ms is None
    assert (settings, snapshot, pending) == before


def test_t2a_flush_drains_once_and_returns_owned_cancel_token():
    from phase6_settings_transaction_controller import Phase6SettingsTransactionController

    settings, snapshot, box, pending = _state()
    owner = Phase6SettingsTransactionController(
        settings_values=settings,
        input_snapshot=snapshot,
        box_whd=box,
        pending_settings=pending,
    )
    owner.stage_setting_update("w", 640.0)
    owner.install_debounce_job("job-1")

    first = owner.drain_pending()
    second = owner.drain_pending()

    assert first.cancel_job == "job-1"
    assert first.pending == {"w": 640.0}
    assert pending == {}
    assert second.cancel_job is None
    assert second.pending == {}


def test_t2a_normalize_and_commit_preserve_setting_types_and_box_projection():
    from phase6_settings_transaction_controller import Phase6SettingsTransactionController

    settings, snapshot, box, pending = _state()
    owner = Phase6SettingsTransactionController(
        settings_values=settings,
        input_snapshot=snapshot,
        box_whd=box,
        pending_settings=pending,
    )

    clean = owner.normalize_updates({
        "w": "640",
        "flag": 1,
        "ui_text_size": "大",
        "unknown": 99,
    })
    assert clean == {"w": 640.0, "flag": True, "ui_text_size": "large"}

    committed = owner.commit_settings(clean)
    assert committed == clean
    assert settings["w"] == 640.0
    assert snapshot["flag"] is True
    assert settings["ui_text_size"] == "large"
    assert box["w"] == 640


def test_t2a_controller_has_no_tk_bridge_or_manufacturing_dependency():
    source = Path("phase6_settings_transaction_controller.py").read_text(encoding="utf-8")
    forbidden = (
        "tkinter",
        "fold_designer_bridge",
        "phase6_manufacturing_service",
        "phase6_manufacturing_geometry",
    )
    assert not [item for item in forbidden if item in source]


def test_t2a_bridge_stage_and_flush_keep_timer_effect_only():
    tree = ast.parse(Path("fold_designer_bridge.py").read_text(encoding="utf-8"))
    funcs = {
        node.name: node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
    }
    stage = funcs["_phase6_stage_setting_update"]
    flush = funcs["_phase6_flush_pending_settings"]

    stage_source = ast.unparse(stage)
    flush_source = ast.unparse(flush)

    assert "stage_setting_update" in stage_source
    assert "root.after" in stage_source
    assert "install_debounce_job" in stage_source
    assert "_settings_values[" not in stage_source
    assert "_phase6_input_snapshot[" not in stage_source
    assert "_phase6_pending_settings[" not in stage_source

    assert "drain_pending" in flush_source
    assert "root.after_cancel" in flush_source
    assert "_phase6_pending_settings = {}" not in flush_source
    assert "_phase6_apply_setting_updates" in flush_source
