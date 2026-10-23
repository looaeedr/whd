# -*- coding: utf-8 -*-
"""#1504 NFB-AC-47: execute the real UI-1A close callback for dirty/discard cases.

The original user-approved Confirm All and legacy DXF remain outside this
transient close action. These are automated GUI-callback seams, NOT a claim
to have run both original Windows projects end to end.
"""
import ast
from copy import deepcopy
from pathlib import Path
import textwrap
import tkinter as tk


ROOT = Path(__file__).resolve().parents[1]
EDITOR = ROOT / "gui_modules/application/fold_designer_composition_receiving.py"


class _Var:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class _Modal:
    def __init__(self):
        self.destroyed = False
        self.cancelled = []
        self.released = False

    def winfo_toplevel(self):
        return self

    def grab_current(self):
        return self

    def grab_release(self):
        self.released = True

    def destroy(self):
        self.destroyed = True

    def after_cancel(self, token):
        self.cancelled.append(token)


class _MessageBox:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def askyesno(self, title, prompt, *, parent):
        self.calls.append((title, prompt, parent))
        return self.response


class _EmbeddedParent:
    def __init__(self):
        self.callbacks = []

    def winfo_exists(self):
        return True

    def after_idle(self, callback):
        self.callbacks.append(callback)
        callback()


def _close_editor_function():
    source = EDITOR.read_text(encoding="utf-8")
    tree = ast.parse(source)
    candidates = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "close_editor"
    ]
    assert len(candidates) == 1
    node = candidates[0]
    lines = source.splitlines(keepends=True)
    body = textwrap.dedent("".join(lines[node.lineno - 1: node.end_lineno]))
    assert body.startswith("def close_editor(")
    return node, body


def _setup(*, response=False, embedded=False):
    node, body = _close_editor_function()
    modal = _Modal()
    msg = _MessageBox(response)
    base_draft = {"layer_count": 1, "models": [["model:old"], []]}
    embed_parent = _EmbeddedParent() if embedded else None
    returned = []
    data = {
        "embed_parent": embed_parent,
        "draft_state": {"draft": deepcopy(base_draft)},
        "initial_nfb_draft": deepcopy(base_draft),
        "layers": _Var(1),
        "initial": {
            "layers": 1, "models": [["model:old"], ""],
            "layer_heights_mm": [550.0, 800.0],
        },
        "chosen": [["model:old"], []],
        "layer_height_vars": (_Var("550"), _Var("800")),
        "nfb_source_viewed": {"value": False},
        "switch_filenames_in_layer": lambda row: [row] if isinstance(row, str) and row else list(row),
        "messagebox": msg,
        "modal": modal,
        "poll_job": {"id": "source-preview-job"},
        "parent_modal": None,
        "after_closed": lambda: returned.append("back-to-main"),
        "tk": tk,
    }
    exec(compile(body, str(EDITOR), "exec"), data)
    return data, node, msg, modal, returned


def test_ac47_unsaved_slot_reject_discard_keeps_full_draft_and_editor(tmp_path):
    # The existing legacy DXF is a read-only control: closing a UI-1A draft
    # must not enter the manufacturing write route.
    legacy = tmp_path / "existing_legacy.dxf"
    legacy.write_bytes(b"ORIGINAL LEGACY DXF BYTES")
    data, _node, msg, modal, returned = _setup(response=False)
    data["draft_state"]["draft"]["models"][0].append("model:new")
    before = deepcopy(data["draft_state"]["draft"])
    data["close_editor"]()
    assert msg.calls and "捨棄" in msg.calls[0][0]
    assert not modal.destroyed and not modal.cancelled
    assert data["draft_state"]["draft"] == before
    assert returned == []
    assert legacy.read_bytes() == b"ORIGINAL LEGACY DXF BYTES"


def test_ac47_operator_confirms_discard_without_any_authority_write(tmp_path):
    legacy = tmp_path / "legacy.dxf"
    legacy.write_bytes(b"UNTOUCHED")
    data, node, msg, modal, returned = _setup(response=True)
    data["draft_state"]["draft"]["models"][0].append("model:new")
    old = deepcopy(data["initial_nfb_draft"])
    data["close_editor"]()
    assert len(msg.calls) == 1
    assert modal.destroyed and modal.released
    assert modal.cancelled == ["source-preview-job"]
    assert data["initial_nfb_draft"] == old
    assert legacy.read_bytes() == b"UNTOUCHED"
    assert returned == []
    called = {n.func.id for n in ast.walk(node)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert called.isdisjoint({"persist_inner", "stage_in_editor", "write_project", "write_dxf"})


def test_ac47_preview_only_has_no_phantom_unsaved_change_prompt():
    data, _node, msg, modal, _ = _setup(response=False)
    data["nfb_source_viewed"]["value"] = True  # only looked at source DXF
    data["close_editor"]()
    assert not msg.calls
    assert modal.destroyed


def test_ac47_uncommitted_height_and_model_choices_require_discard_confirmation():
    for mutate in (
        lambda state: state["layer_height_vars"][0].set("333"),
        lambda state: state["chosen"][0].append("model:another"),
        lambda state: state["layers"].set(2),
    ):
        data, _node, msg, modal, _ = _setup(response=False)
        mutate(data)
        data["close_editor"]()
        assert len(msg.calls) == 1
        assert not modal.destroyed


def test_ac47_embedded_cancel_returns_main_without_a_second_close_prompt():
    # The original Hole Editor Confirm All / Cancel All remains authority.
    data, _node, msg, modal, returned = _setup(response=False, embedded=True)
    data["draft_state"]["draft"]["models"][0].append("unsaved")
    data["close_editor"]()
    assert not msg.calls
    assert modal.destroyed
    assert returned == ["back-to-main"]


def test_ac47_confirmed_save_skips_discard_prompt_and_ui1a_wm_close_is_wired():
    data, _node, msg, modal, _ = _setup(response=False)
    data["draft_state"]["draft"]["models"][0].append("saved")
    data["close_editor"](saved=True)
    assert modal.destroyed and not msg.calls
    text = EDITOR.read_text(encoding="utf-8")
    assert 'modal.protocol("WM_DELETE_WINDOW", close_editor)' in text
    assert 'modal.bind("<Escape>",lambda _event:close_editor())' in text
    assert 'widget.configure(command=close_editor)' in text
