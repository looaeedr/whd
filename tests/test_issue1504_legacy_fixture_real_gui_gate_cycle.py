# -*- coding: utf-8 -*-
"""#1504 partial real Tk UAT: one ORIGINAL legacy receiving project.

This test opens the committed 2026-era .p6fold through WHD's real GUI,
drives the existing Receiving/NFB operator dialog, verifies unavailable
source cannot submit or copy, then saves/reopens and audits authority.
It is deliberately NOT a substitute for the user's second Library file
or full two-project Windows 2D/3D/MARKING/DXF operator signoff.
"""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, ttk

import gui
import fold_designer_bridge as bridge

from ae_engine.receiving_nfb_persistence import contains_submitted_nfb
from phase6_project_file import read_project, PROJECT_SCHEMA_V2


FIXTURE = Path(__file__).parent / "fixtures" / (
    "issue1503_legacy_receiving_without_nfb_base.p6fold"
)


def _find_buttons(root):
    out = {}
    pending = [root]
    while pending:
        w = pending.pop()
        if isinstance(w, ttk.Button):
            out[str(w.cget("text"))] = w
        pending.extend(w.winfo_children())
    return out


def test_real_legacy_fixture_gui_unconfigured_nfb_gates_cancel_save_reopen(
    tmp_path, monkeypatch,
):
    source_bytes = FIXTURE.read_bytes()
    source_hash = sha256(source_bytes).hexdigest()
    on_disk = json.loads(source_bytes)
    assert on_disk["schema"] == "phase6-fold-project-v1"
    old = read_project(FIXTURE)
    assert old["schema"] == PROJECT_SCHEMA_V2
    assert old["snapshot"]["model"] == "受電箱"
    assert (old["snapshot"]["w"], old["snapshot"]["h"],
            old["snapshot"]["d"], old["snapshot"]["t"]) == (800,1600,350,2)
    assert not contains_submitted_nfb(old["snapshot"])

    root = tk.Tk()
    root.withdraw()
    window = None
    audit = []
    try:
        main = gui.BoxCalculatorGUI(root)
        main.baseline_var.set("受電箱")
        root.update()
        app = main.open_original_fold_designer()
        monkeypatch.setattr(
            filedialog, "askopenfilename", lambda **_kw: str(FIXTURE),
        )
        assert app.load_project_file() == str(FIXTURE)
        root.update()
        app = main.fold_designer_app
        # Workspace data is a part/feature DTO, not the full Receiving
        # input; project authority lives in the existing input snapshot.
        before = dict(app._phase6_input_snapshot)
        assert before["model"] == "受電箱"
        assert not contains_submitted_nfb(before)
        audit.append("OPEN_REAL_LEGACY_UNCONFIGURED_PASS")

        # REAL dialog + REAL transaction ports from the loaded Bay, not
        # the mock ports used in #1500's independent GUI widget tests.
        window = bridge._phase6_open_receiving_multi_settings(app)
        root.update()
        assert window.winfo_exists()
        assert window._receiving_multi_apply(0)
        listing = window._receiving_multi_setting_list
        listing.selection_clear(0, tk.END)
        listing.selection_set(1)
        listing.event_generate("<<ListboxSelect>>")
        root.update()
        buttons = _find_buttons(window._receiving_multi_settings_host)
        for title in (
            "確認套用 NFB", "複製至其他連",
            "還原為未配置", "復原上次 NFB 操作",
        ):
            assert title in buttons, f"operator button missing: {title}"
            assert buttons[title].instate(("disabled",)), (
                title, "no independent NFB source/datum was ever verified"
            )
        assert "解除本連連動" not in buttons
        audit.append("REAL_NFB_NO_SOURCE_BUTTONS_DISABLED_PASS")
        window._receiving_multi_close()
        window = None
        root.update()
        assert not contains_submitted_nfb(
            app._phase6_input_snapshot
        )
        audit.append("REAL_MODAL_CANCEL_NO_NFB_LEAK_PASS")

        destination = tmp_path / "old-reopened.p6fold"
        monkeypatch.setattr(
            filedialog, "asksaveasfilename", lambda **_kw: str(destination),
        )
        assert app.save_project_file_as()
        assert destination.is_file()
        saved = read_project(destination)
        assert saved["schema"] == PROJECT_SCHEMA_V2
        assert not contains_submitted_nfb(saved["snapshot"])
        # Legacy V1 projects may gain new, EMPTY part keys on migration.
        # Preserve every old feature owner byte-for-byte in content, and
        # forbid accidentally creating a nonempty/new manufactured feature.
        original_features = old["snapshot"].get("part_features") or {}
        saved_features = saved["snapshot"].get("part_features") or {}
        for owner, features in original_features.items():
            # V1 may store explicitly empty legacy feature owners. Saving
            # canonically omits an empty owner; this is not a lost hole.
            # Every NONEMPTY old feature is still required without changes.
            assert (saved_features.get(owner) or []) == (features or []), owner
        assert all(not features for owner, features in saved_features.items()
                   if owner not in original_features), "unapproved migrated hole"
        for key in ("door_layout_columns", "inner_doors", "part_profiles"):
            assert saved["snapshot"].get(key) == old["snapshot"].get(key), key
        audit.append("REAL_SAVE_PRESERVES_OLD_FEATURES_PASS")

        monkeypatch.setattr(
            filedialog, "askopenfilename", lambda **_kw: str(destination),
        )
        assert app.load_project_file() == str(destination)
        root.update()
        reloaded = dict(app._phase6_input_snapshot)
        assert not contains_submitted_nfb(reloaded)
        assert (reloaded["w"],reloaded["h"],reloaded["d"]) == (800,1600,350)
        assert sha256(FIXTURE.read_bytes()).hexdigest() == source_hash
        audit.append("REAL_REOPEN_NO_DORMANT_NFB_PASS")
        print("ISSUE1504_LEGACY_GUI_SOURCE_RECEIPT=" + json.dumps({
            "source": str(FIXTURE.relative_to(Path(__file__).parents[1])),
            "source_sha256": source_hash,
            "saved_schema": saved["schema"],
            "steps": audit,
            "scope": "ONE_REPO_LEGACY_FIXTURE_ONLY_NOT_17_AC_UAT",
            "second_library_project_executed": False,
            "2d_3d_marking_dxf_executed": False,
        }, ensure_ascii=False, sort_keys=True), flush=True)
    finally:
        if window is not None and window.winfo_exists():
            window.destroy()
        root.destroy()
