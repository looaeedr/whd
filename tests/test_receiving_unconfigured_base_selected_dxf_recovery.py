# -*- coding: utf-8 -*-
"""Real selected-DXF GUI dispatch must not turn an unconfigured Receiving
base-plate preview into manufactured DXF, or silently discard selected parts.

This module isolates the operator's confirmation/atomic commit behavior.
Actual geometry/DXF guards are exercised by the existing manufacturing tests.
"""
from pathlib import Path
from types import SimpleNamespace

import pytest

from gui_modules.project import export_actions


_MISSING_PATTERN = (
    "canonical resolved export: "
    "RECEIVING_BASE_PLATE_PATTERN_REQUIRED_FOR_MANUFACTURING: base_plate"
)
_KEYS = ("box_body", "head", "tail", "door", "base_plate",
         "indicator_box", "indicator_door")


def _run(monkeypatch, tmp_path, selected, *, confirm=True, failure=_MISSING_PATTERN, omit_base_key=False):
    calls = []
    questions = []
    errors = []
    successes = []
    flags = {key: key in selected for key in _KEYS}
    if omit_base_key:
        flags.pop("base_plate")

    host = SimpleNamespace(
        _flush_phase6_authoritative_state=lambda: None,
        _phase6_current_existing_parts=lambda: ("base_plate", "head", "door"),
        _has_any_indicator_box=lambda: False,
        get_float_values=lambda: {"w": 800., "h": 1600., "t": 2.},
        draw_stock_var=SimpleNamespace(get=lambda: False),
    )
    monkeypatch.setattr(
        export_actions, "_selected_export_flags",
        lambda *_: dict(flags),
    )
    monkeypatch.setattr(
        export_actions, "_validate_selected_indicator_exports",
        lambda *_: None,
    )
    monkeypatch.setattr(
        export_actions.filedialog, "askdirectory",
        lambda **_: str(tmp_path),
    )
    monkeypatch.setattr(
        export_actions.messagebox, "askyesno",
        lambda title, message, **kwargs:
            questions.append((title, message, kwargs)) or confirm,
    )
    monkeypatch.setattr(
        export_actions.messagebox, "showerror",
        lambda title, message: errors.append((title, message)),
    )
    monkeypatch.setattr(
        export_actions.messagebox, "showinfo",
        lambda title, message: successes.append((title, message)),
    )

    def fake_mfg(_self, stage_folder, _val, requested, _stock):
        calls.append(dict(requested))
        if requested.get("base_plate", False):
            return [], [failure]
        # Only a stand-in for the downstream writer in the GUI dispatch test.
        # Manufacturing geometry and DXF serialization have separate tests.
        Path(stage_folder, "end_cap_head.dxf").write_bytes(b"TEST_UI_ONLY")
        return ["end_cap_head.dxf"], []

    monkeypatch.setattr(export_actions, "_export_selected_parts", fake_mfg)
    export_actions.export_selected_dxf(host)
    return calls, questions, errors, successes


def test_confirmed_skip_only_excludes_unconfigured_base_and_commits_other_selected(tmp_path, monkeypatch):
    calls, questions, errors, successes = _run(
        monkeypatch, tmp_path, ("head", "base_plate"),
    )
    assert len(calls) == 2
    assert calls[0]["head"] and calls[0]["base_plate"]
    assert calls[1]["head"] and not calls[1]["base_plate"]
    assert len(questions) == 1
    assert "底板" in questions[0][1] and "不是整箱" in questions[0][1]
    assert questions[0][2]["default"] == "no"
    assert not errors
    assert len(successes) == 1
    assert "部分" in successes[0][0]
    assert "底板" in successes[0][1]
    assert (tmp_path / "end_cap_head.dxf").read_bytes() == b"TEST_UI_ONLY"


def test_decline_keeps_destination_untouched(tmp_path, monkeypatch):
    calls, questions, errors, successes = _run(
        monkeypatch, tmp_path, ("head", "base_plate"), confirm=False,
    )
    assert len(calls) == 1
    assert len(questions) == 1
    assert errors == []
    assert successes == []
    assert not list(tmp_path.glob("*.dxf"))


def test_only_unconfigured_base_cannot_be_exported_or_silently_skipped(tmp_path, monkeypatch):
    calls, questions, errors, successes = _run(
        monkeypatch, tmp_path, ("base_plate",),
    )
    assert len(calls) == 1
    assert questions == []
    assert len(errors) == 1
    assert "底板" in errors[0][1] and "設定" in errors[0][1]
    assert successes == []
    assert not list(tmp_path.glob("*.dxf"))


def test_unrelated_manufacturing_failure_must_remain_blocked(tmp_path, monkeypatch):
    calls, questions, errors, successes = _run(
        monkeypatch, tmp_path, ("head", "base_plate"),
        failure="canonical resolved export: UNVERIFIED_NFB_HOLE",
    )
    assert len(calls) == 1
    assert questions == []
    assert len(errors) == 1 and "UNVERIFIED_NFB_HOLE" in errors[0][1]
    assert successes == []
    assert not list(tmp_path.glob("*.dxf"))


def test_unselected_base_never_invokes_partial_fallback(tmp_path, monkeypatch):
    calls, questions, errors, successes = _run(
        monkeypatch, tmp_path, ("head",),
    )
    assert len(calls) == 1
    assert calls[0]["base_plate"] is False
    assert not questions
    assert not errors
    assert successes
    assert (tmp_path / "end_cap_head.dxf").is_file()

def test_legacy_partial_flags_without_base_plate_key_keep_normal_export(tmp_path, monkeypatch):
    calls, questions, errors, successes = _run(
        monkeypatch, tmp_path, ("head",), omit_base_key=True,
    )
    assert len(calls) == 1
    assert "base_plate" not in calls[0]
    assert not questions
    assert not errors
    assert successes
    assert (tmp_path / "end_cap_head.dxf").is_file()
