"""#3414 second slice: real multi-Bay owner ambiguity must not manufacture marks.

The existing numeric-CSV Receiving fixture supplies TWO saved physical Bays.
No panel name, synthetic namespace, or unrelated render licenses copying the
single-root manual intent to both identical canonical physical part keys.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace

import ezdxf
import pytest

import phase6_project_file as project
from ae_engine import manufacturing_api as api
from ae_engine.receiving_layout import project_receiving_bay_legacy_aliases
from ae_engine.receiving_csv_multibay_manufacturing import (
    export_current_receiving_multibay_dxf,
)
from tests.test_issue1502_current_csv_multi_bay_once import _multi, _provider
from tests.test_issue1502_multibay_original_gui_export_integration import (
    _native_callback_host,
)
from tests.test_issue3412_manual_marking_first_sheet import actual_sheet, _mark


def _two_real_bays_with_unscoped_saved_mark(tmp_path, sheet):
    clean = _multi()
    saved = deepcopy(clean)
    saved["workspace"] = dict(saved.get("workspace") or {})
    features = dict(saved["workspace"].get("part_features") or {})
    mark = _mark(sheet, pattern="dashed")
    features["base_plate"] = [mark]
    saved["workspace"]["part_features"] = features
    path = project.write_project(
        tmp_path / "original-two-bay-manual-scope.p6fold",
        {"schema": project.PROJECT_SCHEMA, "snapshot": saved},
    )
    untouched = path.read_bytes()
    loaded = project.read_project(path)["snapshot"]
    restored = loaded["workspace"]["part_features"]["base_plate"][0]
    assert restored == mark and api.is_manual_mark(restored)
    scoped = (
        project_receiving_bay_legacy_aliases(loaded, set_index=0, bay_index=0),
        project_receiving_bay_legacy_aliases(loaded, set_index=0, bay_index=1),
    )
    left_owner = scoped[0]["_receiving_runtime_selection"]
    right_owner = scoped[1]["_receiving_runtime_selection"]
    assert left_owner["set_id"] == right_owner["set_id"]
    assert left_owner["bay_id"] == "receiving:set:1:bay:1"
    assert right_owner["bay_id"] == "receiving:set:1:bay:2"
    assert scoped[0]["workspace"]["part_features"]["base_plate"] == (
        scoped[1]["workspace"]["part_features"]["base_plate"]
    )
    return path, loaded, clean, untouched


def test_saved_root_manual_mark_cannot_claim_two_real_bays_or_replace_dxf(
    actual_sheet, tmp_path,
):
    path, loaded, clean, original = _two_real_bays_with_unscoped_saved_mark(
        tmp_path, actual_sheet,
    )
    provider, calls = _provider(clean)
    destination = tmp_path / "old-output"
    destination.mkdir()
    prior = destination / "previous-valid.dxf"
    prior.write_bytes(b"EARLIER-CANONICAL-DXF-UNTOUCHED")
    with pytest.raises(
        ValueError, match="MANUAL_BATCH_SET_BAY_OWNER_UNRESOLVED:base_plate",
    ):
        export_current_receiving_multibay_dxf(
            loaded, physical_bay_geometry_provider=provider,
            flags={"base_plate": True}, output_dir=destination,
            group_mode="ALL", pre_commit_guard=lambda: None,
            overwrite=True,
        )
    assert calls == []  # rejected before a renderer could drop the saved ink
    assert path.read_bytes() == original
    assert prior.read_bytes() == b"EARLIER-CANONICAL-DXF-UNTOUCHED"
    assert tuple(destination.iterdir()) == (prior,)


def test_live_selected_manual_render_without_scoped_owner_is_rejected(
    actual_sheet, tmp_path,
):
    original = _multi()
    provider, _calls = _provider(original)
    _source, actual, _context, _point, _angle = actual_sheet
    marked = api.with_physical_sheet_features(
        "base_plate", actual, (_mark(actual_sheet),),
    )

    def one_wrong_owner(si, bi):
        geometry = provider(si, bi)
        if bi != 1:
            return geometry
        return replace(geometry, parts=tuple(
            replace(part, render_data=marked)
            if part.part_key == "base_plate" else part
            for part in geometry.parts
        ))

    dest = tmp_path / "live-owner"
    dest.mkdir()
    prior = dest / "previous.dxf"
    prior.write_bytes(b"OLD-APPROVED-DXF")
    with pytest.raises(
        ValueError, match="MANUAL_BATCH_SET_BAY_OWNER_UNRESOLVED",
    ):
        export_current_receiving_multibay_dxf(
            original, physical_bay_geometry_provider=one_wrong_owner,
            flags={"base_plate": True}, output_dir=dest,
            group_mode="ALL", pre_commit_guard=lambda: None, overwrite=True,
        )
    assert prior.read_bytes() == b"OLD-APPROVED-DXF"
    assert tuple(dest.iterdir()) == (prior,)


def test_unselected_base_mark_does_not_block_saved_head_grouped_dxf(
    actual_sheet, tmp_path,
):
    path, loaded, clean, original = _two_real_bays_with_unscoped_saved_mark(
        tmp_path, actual_sheet,
    )
    # The true HEAD is independently resolved from both saved Bay sources.
    # Its original manufacturing eligibility does not depend on a BasePlate
    # marking that the operator did NOT select.
    provider, calls = _provider(clean)
    destination = tmp_path / "head-only"
    outputs = export_current_receiving_multibay_dxf(
        loaded, physical_bay_geometry_provider=provider,
        flags={"head": True}, output_dir=destination,
        group_mode="ALL", pre_commit_guard=lambda: None,
    )
    assert calls == [(0, 0), (0, 1)]
    assert len(outputs) == 2  # selected grouped DXF and machining total
    assert path.read_bytes() == original
    for filename in outputs.values():
        drawing = ezdxf.readfile(filename)
        assert not drawing.audit().errors
        assert drawing.header["$INSUNITS"] == ezdxf.units.MM
        assert any(entity.dxf.layer == "CUTTING"
                   for entity in drawing.modelspace())
    assert len(tuple(destination.glob("*.dxf"))) == 2


def test_real_tk_export_callback_reports_ambiguous_saved_owner_without_output(
    actual_sheet, tmp_path, monkeypatch,
):
    import tkinter as tk
    from gui_modules.project import export_actions as gui

    path, loaded, _clean, original = _two_real_bays_with_unscoped_saved_mark(
        tmp_path, actual_sheet,
    )
    root = tk.Tk()
    try:
        root.withdraw()
        used = []
        host = _native_callback_host(monkeypatch, loaded, used)
        for key, attr in (
            ("box_body", "export_z_var"),
            ("head", "export_head_var"),
            ("tail", "export_tail_var"),
            ("door", "export_door_var"),
            ("base_plate", "export_base_plate_var"),
            ("indicator_box", "export_ib_var"),
            ("indicator_door", "export_ib_door_var"),
        ):
            setattr(host, attr, tk.BooleanVar(
                master=root, value=(key == "base_plate"),
            ))
        destination = tmp_path / "tk-out"
        destination.mkdir()
        prior = destination / "old.dxf"
        prior.write_bytes(b"OLD-CUTTING-KEPT")
        errors, infos = [], []
        monkeypatch.setattr(gui.filedialog, "askdirectory",
                            lambda **_kw: str(destination))
        monkeypatch.setattr(gui.messagebox, "showerror",
                            lambda title, message: errors.append((title, message)))
        monkeypatch.setattr(gui.messagebox, "showwarning",
                            lambda title, message: errors.append((title, message)))
        monkeypatch.setattr(gui.messagebox, "showinfo",
                            lambda title, message: infos.append((title, message)))
        monkeypatch.setattr(gui.messagebox, "askyesno",
                            lambda *_a, **_kw: False)
        gui.export_selected_dxf(host)
        assert errors and not infos
        assert path.read_bytes() == original
        assert prior.read_bytes() == b"OLD-CUTTING-KEPT"
        assert tuple(destination.iterdir()) == (prior,)
    finally:
        root.destroy()


def test_vault_root_marking_editor_still_requires_one_quantity_version():
    from ae_engine.operator_persisted_marking_candidate import require_ordinary_selected_marking_stock
    from ae_engine.receiving_quantity_versions import QuantityModel

    model = QuantityModel()
    model.set_piece_count(2)
    model.add_version()
    snapshot = {"model": "金庫型", "active_mode": "quantity", "quantity": model.snapshot()}
    with pytest.raises(ValueError, match="OWNER_MARKING_SINGLE_NORMAL_SCOPE_REQUIRED"):
        require_ordinary_selected_marking_stock(snapshot, None, "door")
