# -*- coding: utf-8 -*-
from types import SimpleNamespace

import pytest

import fold_designer_bridge as bridge


def test_registry_form_opens_rules_and_joints_tabs_with_wrap_relation():
    tk = bridge.original.tk
    root = tk.Tk()
    root.withdraw()
    app = SimpleNamespace(
        root=root,
        _phase6_input_snapshot={
            "model": "金庫型",
            "assembly_type": "INSERT_OVERLAY",
            "existing_parts": ["box_body", "head", "tail"],
        },
    )
    try:
        win = bridge._phase6_open_relief_registry_form(app)
        root.update_idletasks()
        assert win.winfo_exists()
        tabs = [app.relief_registry_notebook.tab(tab, "text") for tab in app.relief_registry_notebook.tabs()]
        assert "截角公式" in tabs
        assert "組合接合" in tabs
        assert "WRAP" in app.relief_joint_relation_choices
        assert app.relief_joint_topology_var.get() in {"1", "2"}
        assert app.relief_registry_topology_var.get() in {"1", "2"}
        assert hasattr(app, "relief_registry_save_candidate_button")
        assert hasattr(app, "relief_registry_promote_button")
    finally:
        try:
            win.destroy()
        except Exception:
            pass
        root.destroy()


def test_project_toolbar_has_registry_entry_button():
    tk = bridge.original.tk
    root = tk.Tk(); root.withdraw()
    frame = bridge.original.ttk.Frame(root); frame.pack()
    app = SimpleNamespace(
        root=root,
        left=frame,
        load_project_file=lambda: None,
        save_project_file=lambda: None,
        save_project_file_as=lambda: None,
    )
    try:
        bridge._phase6_build_project_toolbar(app, frame)
        root.update_idletasks()
        assert app.relief_registry_button.cget("text") == "截角資料庫"
    finally:
        root.destroy()


def test_saved_candidate_record_must_match_current_form_before_reusing_evidence(monkeypatch):
    app = SimpleNamespace(
        _phase6_registry_candidate_id="candidate-1",
        _phase6_registry_candidate_record={"rule_id": "R", "formula": {"primary_u": "FW"}},
    )
    monkeypatch.setattr(
        bridge, "_phase6_registry_collect_rule_form",
        lambda _self: {"rule_id": "R", "formula": {"primary_u": "FW + T"}},
    )
    assert bridge._phase6_registry_candidate_form_is_current(app) is False


def test_candidate_3d_preview_records_evidence_for_exact_saved_candidate(monkeypatch):
    class Status:
        def __init__(self): self.value = ""
        def set(self, value): self.value = value

    record = {"rule_id": "R", "formula": {"primary_u": "FW"}}
    app = SimpleNamespace(
        _phase6_registry_candidate_id="candidate-1",
        _phase6_registry_candidate_record=record,
        _phase6_registry_regression_evidence={"matrix_passed": True, "cases": 9, "candidate_id": "candidate-1"},
        relief_registry_status_var=Status(),
    )
    monkeypatch.setattr(bridge, "_phase6_registry_collect_rule_form", lambda _self: dict(record))
    monkeypatch.setattr(
        bridge, "_phase6_registry_validate_candidate_3d",
        lambda _self, candidate, *, candidate_id: {
            "candidate_specific": True,
            "candidate_id": candidate_id,
            "zero_penetration": True,
            "validated_parts": ["head", "tail"],
            "solutions": {},
        },
    )
    assert bridge._phase6_registry_preview_assembly_3d(app) is True
    evidence = app._phase6_registry_regression_evidence
    assert evidence["candidate_specific"] is True
    assert evidence["candidate_id"] == "candidate-1"
    assert evidence["matrix_passed"] is True
