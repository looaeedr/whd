# -*- coding: utf-8 -*-
"""#1504 partial real Tk UAT: one ORIGINAL legacy receiving project.

This test opens the committed 2026-era .p6fold through WHD's real GUI,
drives the existing Receiving/NFB operator dialog, verifies unavailable
source cannot submit or copy, then saves/reopens and audits authority.
It proves only this sanitized repository fixture's native Tk behavior and
does not claim actual user Windows UAT, physical 2D/3D, marking or DXF output.
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
        for key in ("door_layout_columns", "inner_doors"):
            assert saved["snapshot"].get(key) == old["snapshot"].get(key), key
        # V1 cached Fold profiles are DERIVED from old geometry and may be
        # migrated to the CURRENT fold rule. Don't freeze stale old cache
        # values as manufacturing authority: preserve every original part
        # owner and require valid positive folded segments after rebuild.
        before_profiles = old["snapshot"].get("part_profiles") or {}
        saved_profiles = saved["snapshot"].get("part_profiles") or {}
        assert set(before_profiles).issubset(saved_profiles)
        for owner in before_profiles:
            axes = saved_profiles[owner]
            assert all(axis in axes and axes[axis] for axis in ("X", "Y")), owner
            assert all(float(segment["len"]) > 0 for axis in ("X", "Y")
                       for segment in axes[axis]), owner
        audit.append("REAL_SAVE_PRESERVES_OLD_FEATURES_AND_VALID_PROFILES_PASS")

        monkeypatch.setattr(
            filedialog, "askopenfilename", lambda **_kw: str(destination),
        )
        assert app.load_project_file() == str(destination)
        root.update()
        reloaded = dict(app._phase6_input_snapshot)
        assert not contains_submitted_nfb(reloaded)
        assert (reloaded["w"],reloaded["h"],reloaded["d"]) == (800,1600,350)
        # One more native GUI save after opening the upgraded project must
        # be idempotent: genuine unexpected profile loss/drift stays RED.
        resaved_path = tmp_path / "old-reopened-again.p6fold"
        monkeypatch.setattr(
            filedialog, "asksaveasfilename",
            lambda **_kw: str(resaved_path),
        )
        assert app.save_project_file_as()
        resaved = read_project(resaved_path)
        assert resaved["snapshot"].get("part_profiles") == saved_profiles
        assert resaved["snapshot"].get("part_features") == saved_features
        assert not contains_submitted_nfb(resaved["snapshot"])
        assert sha256(FIXTURE.read_bytes()).hexdigest() == source_hash
        audit.append("REAL_REOPEN_NO_DORMANT_NFB_AND_STABLE_PROFILES_PASS")
        print("ISSUE1504_LEGACY_GUI_SOURCE_RECEIPT=" + json.dumps({
            "source": str(FIXTURE.relative_to(Path(__file__).parents[1])),
            "source_sha256": source_hash,
            "saved_schema": saved["schema"],
            "steps": audit,
            "scope": "ONE_REPO_LEGACY_FIXTURE_ONLY_NOT_17_AC_UAT",
            "sanitized_repository_fixture_only": True,
            "human_windows_uat_claimed": False,
            "2d_3d_marking_dxf_executed": False,
        }, ensure_ascii=False, sort_keys=True), flush=True)
    finally:
        if window is not None and window.winfo_exists():
            window.destroy()
        root.destroy()


def test_ac46_saved_submitted_nfb_is_never_silently_legacy_after_gui_reload(
    tmp_path, monkeypatch,
):
    """Actual saved project + native Phase6 GUI must retain fail-closed export.

    The input is the existing sanitized old .p6fold with one explicit
    *test* submission, not an original customer manufacturing approval.
    Reopening has no transient MFG-1 capability receipt; a stored NFB cannot
    be treated as legacy merely because runtime proof has not been staged.
    """
    import pytest
    from copy import deepcopy
    from ae_engine.receiving_layout import (
        new_receiving_layout, resize_receiving_bays, update_receiving_bay,
    )
    from ae_engine.receiving_nfb_persistence import contains_submitted_nfb
    from gui_modules.project.export_actions import (
        _has_submitted_nfb_in_current_snapshot,
        _assert_legacy_nfb_export_scope_safe,
        _export_selected_parts,
    )
    from phase6_project_file import write_project, read_project, PROJECT_SCHEMA_V3
    from tests.test_issue1499_nfb_persistence import _config

    old = read_project(FIXTURE)["snapshot"]
    assert not contains_submitted_nfb(old)
    layout = resize_receiving_bays(
        new_receiving_layout(width=800, height=1600, depth=350),
        set_index=0, bay_count=2,
    )
    submitted = update_receiving_bay(
        layout, set_index=0, bay_index=0,
        nfb_config_submitted=True, nfb_config=_config(x=0),
    )
    assert submitted["sets"][0]["bays"][0]["nfb_config_submitted"] is True
    assert "nfb_config" not in submitted["sets"][0]["bays"][1]
    original_features = deepcopy(old.get("part_features") or {})
    candidate = deepcopy(old)
    candidate["active_mode"] = "set_bay"
    candidate["receiving_layout"] = submitted
    source = write_project(tmp_path / "ac46_submitted_legacy_origin.p6fold", {
        "schema": "phase6-fold-project-v1", "snapshot": candidate,
    })
    assert source.exists()
    saved = read_project(source)
    assert saved["schema"] == PROJECT_SCHEMA_V3
    assert _has_submitted_nfb_in_current_snapshot(saved["snapshot"])
    assert saved["snapshot"]["receiving_layout"]["sets"][0]["bays"][0][
        "nfb_config"
    ]["holes"][0]["manual_x_mm"] == 0

    # There is deliberately no staged MFG-1 proof after restarting WHD.
    # The original GUI still has to read the persisted committed fact.
    root = tk.Tk()
    root.withdraw()
    try:
        main = gui.BoxCalculatorGUI(root)
        app = main.load_phase6_project(source, open_designer=True)
        root.update()
        assert app._phase6_input_snapshot["model"] == "受電箱"
        current = app._phase6_input_snapshot
        assert _has_submitted_nfb_in_current_snapshot(current)
        assert current["receiving_layout"]["sets"][0]["bays"][0][
            "nfb_config_submitted"
        ] is True
        assert (current.get("part_features") or {}).get("head", []) == (
            original_features.get("head", [])
        )

        # A disabled capability or absent GUI source cannot erase the
        # persistence authority, even through the REAL operator dialog.
        window = bridge._phase6_open_receiving_multi_settings(app)
        try:
            root.update()
            assert window._receiving_multi_apply(0)
            listing = window._receiving_multi_setting_list
            listing.selection_clear(0, tk.END)
            listing.selection_set(1)
            listing.event_generate("<<ListboxSelect>>")
            root.update()
            buttons = _find_buttons(window._receiving_multi_settings_host)
            assert buttons["確認套用 NFB"].instate(("disabled",))
            assert buttons["複製至其他連"].instate(("disabled",))
            assert buttons["還原為未配置"].instate(("!disabled",))
        finally:
            if window.winfo_exists():
                window._receiving_multi_close()
            root.update()

        # Directly call production guard using the REAL reopened GUI owner.
        affected = (
            {"door": True}, {"base_plate": True}, {"box_body": True},
        )
        for choice in affected:
            with pytest.raises(ValueError, match="不得忽略 NFB"):
                _assert_legacy_nfb_export_scope_safe(main, choice)
        for choice in ({"head": True}, {"tail": True}):
            _assert_legacy_nfb_export_scope_safe(main, choice)

        # The ordinary original DXF action must not emit unverified NFB-
        # dependent BOX BODY/SIDE sheets after reload. Outer DOOR is genuinely
        # independent in the current multi-Bay exporter and may be exported
        # separately; do not turn that legitimate partial path into a false RED.
        flags = {
            "box_body": True, "head": False, "tail": False,
            "door": False, "base_plate": False,
            "indicator_box": False, "indicator_door": False,
        }
        target = tmp_path / "blocked_old_full_export"
        target.mkdir()
        files, issues = _export_selected_parts(
            main, str(target), {}, flags, False,
        )
        assert not files, (files, issues)
        assert issues and any(
            "NFB" in issue or "來源" in issue
            or "SUBMITTED_CSV_NOT_CURRENT" in issue
            for issue in issues
        ), issues
        assert not list(target.rglob("*.dxf"))
        assert _has_submitted_nfb_in_current_snapshot(
            app._phase6_input_snapshot
        )

        # Even a subsequent real GUI project save/reopen cannot convert
        # already-submitted NFB into old unconfigured manufacturing.
        persisted = tmp_path / "ac46_gui_resaved.p6fold"
        monkeypatch.setattr(
            filedialog, "asksaveasfilename", lambda **_: str(persisted),
        )
        assert app.save_project_file_as()
        reopened = read_project(persisted)
        assert reopened["schema"] == PROJECT_SCHEMA_V3
        assert _has_submitted_nfb_in_current_snapshot(reopened["snapshot"])
        assert reopened["snapshot"]["receiving_layout"]["sets"][0]["bays"][0][
            "nfb_config_submitted"
        ] is True
        assert (reopened["snapshot"].get("part_features") or {}).get(
            "head", []
        ) == original_features.get("head", [])
    finally:
        root.destroy()


def test_ac16_same_original_legacy_gui_cancel_save_reload_geometry_and_dxfs(tmp_path, monkeypatch):
    """Original V1 legacy file: native Tk cancel/save/reopen, current 2D/3D and DXF parity.

    Scoped sanitized on-disk legacy evidence only: no Windows operator UAT,
    no declaration that a factory/manufacturer source is approved for MFG2.
    """
    from copy import deepcopy
    from collections import Counter
    from tkinter import filedialog
    import ezdxf
    from gui_modules.project.export_actions import _export_selected_parts

    original_bytes = FIXTURE.read_bytes()
    old_project = read_project(FIXTURE)
    assert not contains_submitted_nfb(old_project["snapshot"])

    def current_geometry(app):
        # The same canonical ResolvedManufacturingGeometry feeds both
        # 2D unfolded geometry and formed 3D placement/skin consumers.
        resolved = app._phase6_resolve_manufacturing_geometry()
        assert resolved.parts
        receipt = {}
        for part in resolved.parts:
            data = part.render_data
            skin = getattr(data, "material", None)
            pieces = tuple(getattr(data, "pieces", ()) or ())
            assert skin is not None or pieces, part.part_key
            if skin is not None and not skin.is_empty:
                flat = (
                    round(float(skin.area), 6),
                    round(float(skin.length), 6),
                    tuple(round(float(v), 6) for v in skin.bounds),
                )
            else:
                flat = None
            receipt[part.part_key] = (
                flat, tuple(dict(x) for x in part.x_profile),
                tuple(dict(y) for y in part.y_profile),
                part.placement, tuple(part.offset),
                tuple(str(getattr(piece, "role", "")) for piece in pieces),
            )
        return receipt

    def exported_dxf_signature(folder, app):
        folder.mkdir()
        flags = dict.fromkeys((
            "box_body", "head", "tail", "door", "base_plate",
            "indicator_box", "indicator_door",
        ), False)
        for key in ("box_body", "head", "tail", "door", "base_plate"):
            flags[key] = True
        files, failures = _export_selected_parts(app, str(folder), {}, flags, False)
        assert not failures, failures
        assert files, "Old unconfigured manufacturing cannot silently become zero output"
        signatures = {}
        for filename in files:
            physical_path = folder / filename
            assert physical_path.is_file(), filename
            doc = ezdxf.readfile(physical_path)
            entities = []
            for e in doc.modelspace():
                layer = str(e.dxf.layer)
                color = int(e.dxf.color) if e.dxf.hasattr("color") else None
                if e.dxftype() == "LWPOLYLINE":
                    geometry = tuple(
                        tuple(round(float(v), 5) for v in point)
                        for point in e.get_points("xyb")
                    )
                elif e.dxftype() == "LINE":
                    geometry = (
                        tuple(round(float(v), 5) for v in e.dxf.start),
                        tuple(round(float(v), 5) for v in e.dxf.end),
                    )
                elif e.dxftype() == "CIRCLE":
                    geometry = (
                        tuple(round(float(v), 5) for v in e.dxf.center),
                        round(float(e.dxf.radius), 5),
                    )
                elif e.dxftype() == "ARC":
                    geometry = (
                        tuple(round(float(v), 5) for v in e.dxf.center),
                        round(float(e.dxf.radius), 5),
                        round(float(e.dxf.start_angle), 5),
                        round(float(e.dxf.end_angle), 5),
                    )
                else:
                    geometry = ()
                entities.append((e.dxftype(), layer, color, geometry))
            assert entities, filename
            signatures[str(filename)] = Counter(repr(row) for row in entities)
        return signatures

    root = tk.Tk()
    root.withdraw()
    window = None
    try:
        main = gui.BoxCalculatorGUI(root)
        main.baseline_var.set("受電箱")
        root.update()
        app = main.open_original_fold_designer()
        monkeypatch.setattr(
            filedialog, "askopenfilename", lambda **_: str(FIXTURE),
        )
        assert app.load_project_file() == str(FIXTURE)
        root.update()
        app = main.fold_designer_app
        before = deepcopy(app._phase6_input_snapshot)
        assert not contains_submitted_nfb(before)
        original_geometry = current_geometry(app)
        original_dxf = exported_dxf_signature(tmp_path / "before", main)

        window = bridge._phase6_open_receiving_multi_settings(app)
        root.update()
        assert window._receiving_multi_apply(0)
        listing = window._receiving_multi_setting_list
        listing.selection_clear(0, tk.END)
        listing.selection_set(1)
        listing.event_generate("<<ListboxSelect>>")
        root.update()
        controls = _find_buttons(window._receiving_multi_settings_host)
        assert controls["確認套用 NFB"].instate(("disabled",))
        assert controls["複製至其他連"].instate(("disabled",))
        window._receiving_multi_close()
        window = None
        root.update()
        assert not contains_submitted_nfb(app._phase6_input_snapshot)
        assert current_geometry(app) == original_geometry

        destination = tmp_path / "legacy-ac16-reopened.p6fold"
        monkeypatch.setattr(
            filedialog, "asksaveasfilename", lambda **_: str(destination),
        )
        assert app.save_project_file_as()
        saved = read_project(destination)
        assert not contains_submitted_nfb(saved["snapshot"])
        assert all(
            (saved["snapshot"].get("part_features") or {}).get(k, []) == v
            for k, v in (old_project["snapshot"].get("part_features") or {}).items()
            if v
        )
        monkeypatch.setattr(
            filedialog, "askopenfilename", lambda **_: str(destination),
        )
        assert app.load_project_file() == str(destination)
        root.update()
        app = main.fold_designer_app
        assert not contains_submitted_nfb(app._phase6_input_snapshot)
        assert current_geometry(app) == original_geometry
        reopened_dxf = exported_dxf_signature(tmp_path / "after", main)
        assert reopened_dxf == original_dxf
        assert FIXTURE.read_bytes() == original_bytes
    finally:
        if window is not None and window.winfo_exists():
            window.destroy()
        root.destroy()


def test_ac16_vault_native_generic_hole_editor_cancel_does_not_mount_receiving_nfb():
    """Original 金庫型 door Hole Editor remains editable and atomic after #1504.

    Drives the unmodified native Tk editor rather than an NFB test mock.
    Cancelling a destructive draft must restore its exact original feature;
    merely opening the editor must not mutate the vault family to 受電箱
    or synthesize a persisted NFB submission.
    """
    import re

    from ae_engine.sheetmetal_features import (
        CircleFeature, FeatureAnchor, feature_surface_from_rect,
    )
    from ae_engine.sheetmetal_geometry import Vec2

    root = tk.Tk()
    root.geometry("900x650+0+0")
    try:
        main = gui.BoxCalculatorGUI(root)
        root.update()
        assert main.baseline_var.get() == "金庫型"
        assert main._make_original_fold_designer_snapshot()["model"] == "金庫型"

        hole = CircleFeature(
            diameter=20.0, anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
            offset=Vec2(50.0, 50.0),
        )
        original_features = [hole]
        door_features = list(original_features)
        surface = feature_surface_from_rect(
            "vault-door", Vec2(0.0, 0.0), Vec2(120.0, 120.0),
        )
        main._open_unified_hole_editor(
            "door", "金庫型門板", surface, 120.0, 120.0,
            feature_list_override=door_features,
        )
        editor = main.last_unified_hole_editor
        root.update()
        assert editor.winfo_exists()

        widgets = [editor]
        for widget in widgets:
            widgets.extend(widget.winfo_children())
        created = next(
            widget for widget in widgets
            if isinstance(widget, tk.Listbox)
            and widget.size() == 1
            and str(widget.get(0)).startswith("01")
        )
        delete_btn = next(
            widget for widget in widgets
            if isinstance(widget, tk.Button)
            and widget.cget("text") == "刪除選中"
        )
        cancel_btn = next(
            widget for widget in widgets
            if isinstance(widget, tk.Button)
            and widget.cget("text") == "取消全部"
        )
        created.selection_clear(0, tk.END)
        created.selection_set(0)
        created.event_generate("<<ListboxSelect>>")
        # Cross-platform invisible Tk virtual events may need the registered
        # Tcl binding invoked, as in the original Hole Editor GUI regression.
        binding = created.bind("<<ListboxSelect>>")
        match = re.search(r"\[(\d+on_created_select\b)", binding or "")
        if match:
            root.tk.call(match.group(1))
        root.update()
        delete_btn.invoke()
        root.update()
        assert door_features == []

        cancel_btn.invoke()
        root.update()
        assert door_features == original_features
        assert not editor.winfo_exists()
        assert main.baseline_var.get() == "金庫型"
        assert main._make_original_fold_designer_snapshot()["model"] == "金庫型"

        designer = main.open_original_fold_designer()
        root.update()
        assert designer._phase6_input_snapshot["model"] == "金庫型"
        assert not contains_submitted_nfb(designer._phase6_input_snapshot)
    finally:
        root.destroy()
