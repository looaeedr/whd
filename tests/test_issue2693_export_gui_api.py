"""#2693 GUI export must call Engine, never compose manufacturing in GUI."""
from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

import ezdxf
import pytest

from ae_engine import manufacturing_api
from ae_engine.receiving_layout import new_receiving_layout, resize_receiving_bays
from gui_modules.project import export_actions as gui
from tests.test_issue2690_composed_panel_dxf import _flat, _geometry


def _vault_host(name):
    snapshot = {"model": "金庫型", "panel_name": name}
    designer = SimpleNamespace(
        _phase6_input_snapshot=snapshot,
        _phase6_resolve_manufacturing_geometry=lambda: _geometry(
            ("door", _flat("door", width=80, height=40)),
        ),
    )
    return SimpleNamespace(
        fold_designer_app=designer,
        receiving_dxf_group_mode_var=SimpleNamespace(get=lambda: "ALL"),
    )


def test_vault_gui_exports_one_real_composed_dxf_with_engine_api(tmp_path, monkeypatch):
    host = _vault_host("A01")
    monkeypatch.setattr(gui, "_assert_legacy_nfb_export_scope_safe",
                        lambda _host, flags: None)
    exported, errors = gui._export_selected_resolved_parts(
        host, tmp_path, {"door": True},
    )
    assert exported == ["A01.dxf"] and not errors
    assert {p.name for p in tmp_path.iterdir()} == {"A01.dxf"}
    model = tuple(ezdxf.readfile(tmp_path / "A01.dxf").modelspace())
    assert any(e.dxf.layer == "CUTTING" for e in model)
    assert any(e.dxftype() == "MTEXT" and e.plain_text() == "A01"
               and e.dxf.layer == "CHECK" for e in model)


def test_vault_blank_name_uses_taipei_time_engine_contract(tmp_path, monkeypatch):
    host = _vault_host("")
    monkeypatch.setattr(gui, "_assert_legacy_nfb_export_scope_safe",
                        lambda _host, flags: None)
    monkeypatch.setattr(
        manufacturing_api, "vault_panel_dxf_filename",
        lambda name: "金庫型_20261101_235900.dxf",
    )
    exported, errors = gui._export_selected_resolved_parts(
        host, tmp_path, {"door": True},
    )
    assert exported == ["金庫型_20261101_235900.dxf"]
    assert errors == [] and (tmp_path / exported[0]).exists()


def test_vault_source_drift_pre_commit_fails_closed(tmp_path, monkeypatch):
    host = _vault_host("A01")
    monkeypatch.setattr(gui, "_assert_legacy_nfb_export_scope_safe",
                        lambda _host, flags: None)
    original = manufacturing_api.save_composed_panel_dxf
    def mutating(*args, **kwargs):
        host.fold_designer_app._phase6_input_snapshot["panel_name"] = "OTHER"
        return original(*args, **kwargs)
    monkeypatch.setattr(manufacturing_api, "save_composed_panel_dxf", mutating)
    with pytest.raises(ValueError, match="來源已變更"):
        gui._export_selected_resolved_parts(host, tmp_path, {"door": True})
    assert not list(tmp_path.glob("*.dxf"))


def test_receiving_gui_selection_delegates_grouping_and_local_geometry(monkeypatch, tmp_path):
    layout = new_receiving_layout(width=800, height=1600, depth=350)
    layout = resize_receiving_bays(layout, set_index=0, bay_count=2)
    snapshot = {"model": "受電箱", "active_mode": "set_bay",
                "receiving_layout": layout}
    designer = SimpleNamespace(
        _phase6_input_snapshot=snapshot,
        _phase6_resolve_manufacturing_geometry=lambda: object(),
    )
    host = SimpleNamespace(
        fold_designer_app=designer,
        receiving_dxf_group_mode_var=SimpleNamespace(
            get=lambda: "END_VS_MIDDLE",
        ),
    )
    class FakeComposition:
        def receiving_bay_preview_request(self, *args, **kwargs):
            return SimpleNamespace(
                render_data=SimpleNamespace(assembly_parts=(object(),)),
            )
    import fold_designer_bridge as bridge
    monkeypatch.setattr(bridge, "_phase6_composition",
                        lambda app: FakeComposition())
    geometry = _geometry(("door", _flat("door")))
    monkeypatch.setattr(
        manufacturing_api, "resolve_receiving_bay_local_export_geometry",
        lambda *args, **kwargs: geometry,
    )
    calls = []
    def fake_export(source, **kwargs):
        calls.append(kwargs)
        assert source["receiving_layout"] == layout
        assert kwargs["group_mode"] == "END_VS_MIDDLE"
        assert kwargs["flags"] == {"door": True}
        assert kwargs["pre_commit_guard"]() is None
        assert kwargs["physical_bay_geometry_provider"](0, 1) is geometry
        return {"頭尾盤.dxf": str(tmp_path / "頭尾盤.dxf")}
    monkeypatch.setattr(
        manufacturing_api, "export_grouped_receiving_multibay_dxf",
        fake_export,
    )
    out, err = gui._export_selected_resolved_parts(
        host, tmp_path, {"door": True},
    )
    assert (out, err) == (["頭尾盤.dxf"], [])
    assert len(calls) == 1


def test_grouped_and_legacy_precommit_guard_snapshots_only_operator_inputs():
    host = _vault_host("A01")
    snap = host.fold_designer_app._phase6_input_snapshot
    guard = gui._current_authoritative_export_guard(host.fold_designer_app, snap)
    snap["panel_name"] = "A02"
    with pytest.raises(ValueError, match="來源已變更"):
        guard()
