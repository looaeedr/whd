# -*- coding: utf-8 -*-
"""#339 T6 — Corner Data presentation must fail closed without changing raw authority."""
from __future__ import annotations

import logging
import os
from pathlib import Path
import tkinter as tk

import pytest


ROOT = Path(__file__).resolve().parents[1]
FALLBACK = "未定義項目（代碼已記錄）"


def _source() -> str:
    return (ROOT / "fold_designer_bridge.py").read_text(encoding="utf-8")


def test_t6_source_contract_has_strict_registry_presentation_adapter():
    source = _source()
    required = (
        "def _phase6_registry_present_token",
        "def _phase6_registry_formula_display",
        "def _phase6_registry_source_display",
        FALLBACK,
        "presentation_field=",
        "raw_value=",
        "source_adapter=",
    )
    missing = [token for token in required if token not in source]
    assert not missing, (
        "#339 EXPECTED RED: Corner Data still lacks a fail-closed presentation "
        f"adapter/diagnostic contract; missing={missing!r}"
    )


def test_unknown_token_fails_closed_and_logs_raw_without_mutation(caplog):
    import fold_designer_bridge as bridge

    raw = "FUTURE_TRUST_LEVEL_X"
    record = {"trust_level": raw, "rule_id": "INTERNAL_RULE_X"}
    before = dict(record)
    with caplog.at_level(logging.WARNING):
        visible = bridge._phase6_registry_present_token(
            raw,
            presentation_field="trust_level",
            source_adapter="test_unknown_token",
        )
    assert visible == FALLBACK
    assert raw not in visible
    assert record == before
    messages = "\n".join(item.getMessage() for item in caplog.records)
    assert "presentation_field=trust_level" in messages
    assert f"raw_value={raw}" in messages
    assert "source_adapter=test_unknown_token" in messages


def test_known_tokens_still_map_to_chinese_and_raw_values_round_trip():
    import fold_designer_bridge as bridge

    assert bridge._phase6_registry_present_token(
        "CERTIFIED", presentation_field="trust_level", source_adapter="test_known"
    ) == "已認證"
    assert bridge._phase6_registry_present_token(
        "USER_ADDED", presentation_field="source", source_adapter="test_known"
    ) == "使用者新增"

    formula_raw = "side_fold + FW"
    visible_formula = bridge._phase6_registry_formula_display(
        formula_raw, presentation_field="primary_u"
    )
    assert not any("A" <= ch <= "Z" or "a" <= ch <= "z" for ch in visible_formula)
    assert bridge._phase6_formula_raw(visible_formula) == formula_raw


def test_unknown_formula_and_source_fail_closed():
    import fold_designer_bridge as bridge

    assert bridge._phase6_registry_formula_display(
        "future_symbol + T", presentation_field="primary_u"
    ) == FALLBACK
    assert bridge._phase6_registry_source_display(
        "future-source-token", presentation_field="source"
    ) == FALLBACK


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="requires real Tk/Xvfb")
def test_unknown_choice_projects_fallback_but_preserves_raw_var():
    import gui

    root = tk.Tk()
    root.geometry("1400x900+0+0")
    root.update_idletasks()
    app = gui.Phase6PrimaryApplication(root)
    designer = app.fold_designer_app
    try:
        designer.relief_registry_button.invoke()
        for _ in range(4):
            root.update_idletasks(); root.update()

        raw_var = designer.relief_registry_family_var
        target = None
        stack = [designer.relief_registry_window]
        while stack:
            widget = stack.pop()
            if getattr(widget, "_phase6_raw_var", None) is raw_var:
                target = widget
                break
            stack.extend(widget.winfo_children())
        assert target is not None

        raw_var.set("FUTURE_FAMILY_X")
        for _ in range(2):
            root.update_idletasks(); root.update()

        assert raw_var.get() == "FUTURE_FAMILY_X"
        assert target._phase6_display_var.get() == FALLBACK
        assert "FUTURE_FAMILY_X" not in target._phase6_display_var.get()
    finally:
        root.destroy()


def test_joint_diagnostic_menu_source_does_not_expose_raw_joint_ids():
    source = (ROOT / "phase6_registry_diagnostics_panel.py").read_text(encoding="utf-8")
    start = source.index("    def refresh_joint_diagnostic_menu")
    end = source.find("\n    def ", start + 5)
    body = source[start:] if end < 0 else source[start:end]
    assert 'label=joint_id' not in body
    assert 'current or "Joint"' not in body
    assert "接合 " in body
