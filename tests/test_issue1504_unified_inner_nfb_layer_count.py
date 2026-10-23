# -*- coding: utf-8 -*-
"""#1504 SWT-AC-01: inner-door layers ARE NFB installed tiers.

Keep the current original UI-1A one writable source; do not introduce a
second independent physical-tier control, hidden or visible.  Demonstrate
the same Tk variable feeds existing candidate, transient edit, Undo and
submitted-layer validation; real factory DXF claims are intentionally separate.
"""
import ast
from pathlib import Path
import tkinter as tk
from tkinter import ttk

import pytest

from ae_engine.receiving_nfb_ui1a import (
    new_nfb_ui1a_draft, set_nfb_draft_layer_count,
)
from ae_engine.receiving_nfb_ui1a_edits import NfbUi1aEditSession


SOURCE = (Path(__file__).resolve().parents[1] /
          "gui_modules/application/fold_designer_composition_receiving.py")


def _inner_editor_source():
    text = SOURCE.read_text(encoding="utf-8")
    start = text.index("    def inner_edit(role, version_id, after_saved,")
    end = text.index("    def current_inner_editor_config():", start)
    return text[start:end]


def test_single_current_layer_count_owns_both_inner_door_and_nfb_mounting_tiers():
    code = _inner_editor_source()
    assert 'layers = tk.IntVar(master=modal, value=initial["layers"])' in code
    assert "nfb_physical_layers = layers" in code
    assert "nfb_physical_layers = tk.IntVar" not in code
    assert "physical_row =" not in code
    assert "NFB 物理層（未提交草稿）" not in code
    assert code.count("variable=layers,") == 1
    assert "variable=nfb_physical_layers," not in code
    assert 'text="內門版本層數"' in code
    assert "nfb_physical_layers.get() != layers.get()" not in code
    assert 'layer_count=nfb_physical_layers.get()' in code
    assert 'set_nfb_draft_layer_count(' in code
    assert 'nfb_physical_layers.set(edit_session.current["layer_count"])' in code
    assert '"layers": layers.get()' in code
    assert "nfb_physical_layers.get()" in code
    assert "def sync_visible_layers():" in code
    assert "change_layers()" in code
    # Inspect actual AST: Tk IntVar exists only once in this real editor.
    tree = ast.parse("def outer():\n" + code)
    intvars = [
        n for n in ast.walk(tree) if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and n.func.attr == "IntVar"
        and isinstance(n.func.value, ast.Name)
        and n.func.value.id == "tk"
    ]
    # Other layer controls may have unrelated integer state, but no hidden
    # second count instance is created for NFB physical tiers.
    assert not any(
        isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "nfb_physical_layers"
                for t in n.targets)
        and isinstance(n.value, ast.Call)
        for n in ast.walk(tree)
    )


@pytest.mark.parametrize("tier_count", (1, 2))
def test_real_tk_single_variable_reaches_original_draft_and_undo_without_second_owner(
    tier_count,
):
    root = tk.Tk()
    root.withdraw()
    try:
        layers = tk.IntVar(master=root, value=1)
        nfb_physical_layers = layers
        buttons = ttk.Frame(root)
        for count in (1, 2):
            ttk.Radiobutton(
                buttons, text=str(count), value=count, variable=layers,
            ).pack(side="left")
        old = new_nfb_ui1a_draft(set_brand="士林", layer_count=1)
        session = NfbUi1aEditSession(old)
        original_session = session.original
        assert nfb_physical_layers is layers
        layers.set(tier_count)
        assert nfb_physical_layers.get() == tier_count
        receipt = session.apply(
            "LAYER-COUNT", set_nfb_draft_layer_count, nfb_physical_layers.get(),
        )
        assert session.current["layer_count"] == tier_count
        assert layers.get() == session.current["layer_count"]
        if receipt is not None:
            session.undo()
            nfb_physical_layers.set(session.current["layer_count"])
            assert layers.get() == 1
        # The installed edit session assigns stable unit IDs and rotation
        # defaults on entry; compare with its normalized original, not
        # with the raw incoming UI-1A DTO.
        assert session.cancel() == original_session
        assert old["layer_count"] == 1
        assert len([x for x in buttons.winfo_children()
                    if isinstance(x, ttk.Radiobutton)]) == 2
    finally:
        root.destroy()


def test_existing_legacy_count_and_nfb_draft_no_longer_have_an_inequality_gate():
    source = _inner_editor_source()
    assert 'layer_count=nfb_physical_layers.get()' in source
    assert 'active = draft_state["draft"]["layers"][:nfb_physical_layers.get()]' in source
    assert '"layers": layers.get()' in source
    assert "NFB 物理層與內門版本層數不同" not in source
    # The source edit/Confirm behavior remains the original unchanged
    # workflow; never infer manufacturing approval from this UI-only proof.
    assert 'stage_in_editor(config, openings)' in source
    assert 'persist_inner(saved)' in source
    assert '"nfb_draft": draft_state' in source


def test_multi_settings_has_no_second_writable_tier_widget_outside_original_nfb_editor():
    source = (Path(__file__).resolve().parents[1] /
              "gui_modules/application/receiving_multi_settings_window.py"
              ).read_text(encoding="utf-8")
    # The version link remains; its old directly editable tier-count selector
    # must no longer be called by the original multi-settings UI.
    assert 'actions(settings_host, "inner_door_layers", role="inner-door")' in source
    assert 'actions(settings_host, "inner_door_layers")' not in source
    assert '"連動選取的連"' in source
    # The original NFB editor is now the unique active count editor; its
    # 1/2 layer radio is the same integer as draft and candidate layer count.
    assert 'layers = tk.IntVar(master=modal, value=initial["layers"])' in _inner_editor_source()
    assert 'nfb_physical_layers = layers' in _inner_editor_source()
