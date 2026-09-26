# -*- coding: utf-8 -*-
"""Issue #619 / B4 UI-R3 atomic family live-switch acceptance."""
from __future__ import annotations

import hashlib
import json
import os

import pytest


pytestmark = pytest.mark.skipif(
    not (os.name == "nt" or os.environ.get("DISPLAY")),
    reason="#619 UI-R3 requires a real Tk/Xvfb display",
)


def _pump(root, count=3):
    for _ in range(count):
        root.update_idletasks()
        root.update()


def _inventory_fingerprint(designer) -> str:
    inventory = tuple(
        sorted(
            str(part_key)
            for part_key in tuple(
                getattr(designer.designer_workspace, "available_parts", ()) or ()
            )
        )
    )
    payload = json.dumps(
        inventory,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def test_ui_r3_vault_to_receiving_has_one_authoritative_visible_commit_after_finalize():
    import tkinter as tk
    import gui

    root = tk.Tk()
    root.withdraw()
    app = gui.BoxCalculatorGUI(root)
    designer = None
    try:
        app.baseline_var.set("金庫型")
        _pump(root)
        designer = app.open_original_fold_designer()
        designer.root.deiconify()
        designer.root.geometry("1120x720+0+0")
        _pump(root)

        canvas = designer.renderer.canvas.get_tk_widget()
        assert canvas.winfo_manager(), "UI-R3 requires the 3D canvas to be visible"
        assert canvas.winfo_width() > 1 and canvas.winfo_height() > 1

        designer.baseline_model_var.set("受電箱")
        _pump(root, 6)

        records = [
            dict(row)
            for row in tuple(
                getattr(designer, "_phase6_visible_scene_commit_records", ()) or ()
            )
        ]
        assert len(records) == 1, (
            "UI-R3 atomic switch requires exactly one authoritative visible scene "
            f"commit after finalize; got {records!r}"
        )
        final = records[0]
        assert int(final["sequence"]) == 1
        assert str(final["cabinet_family"]) == "受電箱"
        assert str(final["transition_stage"]) == "finalize"
        assert not bool(final.get("invalid_visible_commit", False))
        assert str(final["physical_inventory_fingerprint"]) == _inventory_fingerprint(
            designer
        )

        box_children = {
            str(key)
            for key in designer.designer_workspace.available_parts
            if str(key).startswith("box_body:")
        }
        assert {
            "box_body:left_side",
            "box_body:back",
            "box_body:right_side",
        } <= box_children
    finally:
        if designer is not None:
            try:
                designer.root.destroy()
            except Exception:
                pass
        try:
            root.destroy()
        except Exception:
            pass
