"""#2517 PAD/Base operator export source identity is Engine-owned, never GUI authority."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import inspect

import pytest

from ae_engine import manufacturing_api as api
from ae_engine.receiving_layout import new_receiving_layout
from gui_modules.project import export_actions as gui


def _one_bay(model="受電箱"):
    layout = new_receiving_layout(width=800., height=1600., depth=350.)
    data = {"source": "committed-nfb"}
    bay = layout["sets"][0]["bays"][0]
    bay.update({"nfb_config_submitted": True, "nfb_config": deepcopy(data)})
    snapshot = {
        "model": model, "active_mode": "set_bay",
        "nfb_config_submitted": True, "nfb_config": deepcopy(data),
        "receiving_layout": layout, "t": 2.,
    }
    return snapshot


@pytest.mark.parametrize("family", ("受電箱", "RECEIVING", "receiving", "  ReCeIvInG  "))
def test_real_singleton_set_bay_source_id_is_selected_by_public_engine(family):
    source = _one_bay(family)
    before = deepcopy(source)
    result = api.resolve_receiving_pad_base_export_source(source)
    saved = source["receiving_layout"]["sets"][0]
    assert isinstance(result, api.ReceivingPadBaseExportSource)
    assert result.version_id == (
        saved["stable_id"] + "__" + saved["bays"][0]["stable_id"]
    )
    assert result.snapshot["_receiving_runtime_selection"] == {
        "set_id": saved["stable_id"], "bay_id": saved["bays"][0]["stable_id"],
        "set_index": 0, "bay_index": 0,
    }
    assert result.snapshot is not source
    assert source == before


def test_explicit_set_bay_selection_survives_without_synthetic_identity():
    source = _one_bay()
    source["_receiving_runtime_selection"] = {
        "set_id": "actual-set", "bay_id": "actual-bay",
        "set_index": 0, "bay_index": 0,
    }
    before = deepcopy(source)
    result = api.resolve_receiving_pad_base_export_source(source)
    assert result.version_id == "actual-set__actual-bay"
    assert source == before
    with pytest.raises(ValueError, match="實際識別碼"):
        api.resolve_receiving_pad_base_export_source({
            **source, "_receiving_runtime_selection": {"set_id": "", "bay_id": "b"}
        })


def test_multibay_or_stale_singleton_source_cannot_invent_a_current_selector():
    source = _one_bay()
    source["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"] = {
        "source": "other-bay"
    }
    with pytest.raises(ValueError, match="實體選取"):
        api.resolve_receiving_pad_base_export_source(source)
    source = _one_bay()
    first = source["receiving_layout"]["sets"][0]["bays"][0]
    source["receiving_layout"]["sets"][0]["bays"].append(deepcopy(first))
    with pytest.raises(ValueError, match="實體選取"):
        api.resolve_receiving_pad_base_export_source(source)


@pytest.mark.parametrize("edits", (
    {"model": "金庫型"},
    {"model": "unknown"},
    {"nfb_config_submitted": False},
))
def test_nonreceiving_and_unsubmitted_rejected_at_engine_boundary(edits):
    source = {**_one_bay(), **edits}
    with pytest.raises(ValueError, match="提交 NFB"):
        api.resolve_receiving_pad_base_export_source(source)


def test_quantity_version_reuses_actual_saved_nfb_and_common_box_projection():
    from ae_engine.receiving_quantity_versions import QuantityModel
    from tests.test_issue1502_single_button_full_csv_receiving_export import _prepare

    root, _ = _prepare(False)
    q = QuantityModel()
    version = q.selected_version_id
    q.set_version_nfb_config(version, submitted=True, config=root["nfb_config"])
    source = {
        **root, "model": "receiving", "active_mode": "quantity",
        "quantity": q.snapshot(),
        "receiving_quantity_box": {
            "w": root["w"], "h": root["h"], "d": root["d"],
            "inner_door_layers": 1,
        },
    }
    before = deepcopy(source)
    result = api.resolve_receiving_pad_base_export_source(source)
    assert result.version_id == version
    assert result.snapshot["active_mode"] == "quantity"
    assert result.snapshot["nfb_config_submitted"] is True
    assert result.snapshot["nfb_config"] == root["nfb_config"]
    assert result.snapshot["receiving_layout"]["sets"][0]["bays"][0][
        "nfb_config_submitted"
    ] is True
    assert source == before
    stale = {**source, "nfb_config": {"wrong": "version"}}
    with pytest.raises(ValueError, match="來源已失效"):
        api.resolve_receiving_pad_base_export_source(stale)


def test_original_gui_pad_callback_only_consumes_engine_source_response(
    tmp_path, monkeypatch,
):
    import fold_designer_bridge as bridge
    from tkinter import simpledialog

    source = {"model": "受電箱", "nfb_config_submitted": True, "t": 2.}
    selected_source = {**source, "_receiving_runtime_selection": {"set_id": "a"}}
    hits = []
    monkeypatch.setattr(api, "committed_nfb_pad_draft_parts",
                        lambda snapshot: ("verified-pad",))
    monkeypatch.setattr(
        bridge, "_phase6_final_scene_adapter",
        lambda _: SimpleNamespace(query_assembly_render_data=lambda:
            SimpleNamespace(assembly_parts=("real-assembly",))),
    )
    monkeypatch.setattr(api, "resolve_receiving_pad_base_export_source",
                        lambda snap: hits.append(("source", snap)) or
                        SimpleNamespace(snapshot=selected_source, version_id="source-v2"))
    monkeypatch.setattr(simpledialog, "askstring",
                        lambda title, _: "SPCC" if "材質" in title else "LASER")
    monkeypatch.setattr(simpledialog, "askinteger", lambda *_a, **_kw: 2)
    monkeypatch.setattr(gui.filedialog, "askdirectory", lambda **_kw: str(tmp_path))
    monkeypatch.setattr(gui.messagebox, "showerror",
                        lambda *_a: pytest.fail("valid Engine source must reach exporter"))
    monkeypatch.setattr(gui.messagebox, "showinfo",
                        lambda *_a: hits.append(("notice",)))
    def exporter(*args, **kw):
        hits.append(("export", args, kw))
        return SimpleNamespace(pad_piece_count=2, base_piece_count=2,
                               output_directory=str(tmp_path))
    monkeypatch.setattr(api, "export_verified_pad_base_part_only", exporter)
    host = SimpleNamespace(
        _flush_phase6_authoritative_state=lambda: None,
        fold_designer_app=SimpleNamespace(_phase6_input_snapshot=source),
    )
    result = gui.export_receiving_pad_base_part_only_dxf(host)
    assert result.pad_piece_count == 2
    assert hits[0] == ("source", source)
    exported = hits[1]
    assert exported[0] == "export"
    assert exported[1][0] is selected_source
    assert exported[1][1] == ("real-assembly",)
    assert exported[2]["version_id"] == "source-v2"
    assert exported[2]["box_count"] == 2
    assert hits[2] == ("notice",)
    ui = inspect.getsource(gui.export_receiving_pad_base_part_only_dxf)
    for forbidden in (
        "from phase6_quantity_model import", "selected_version_id",
        "nfb_config_for_version(", "receiving_layout", '"set_id"', '"bay_id"',
    ):
        assert forbidden not in ui


class _Bool:
    def __init__(self, value):
        self.value = value
    def get(self):
        return self.value


@pytest.mark.parametrize("model", ("receiving", "  ReCeIvInG  ", "金庫型"))
def test_existing_named_dxf_for_registered_family_never_overwrites_without_confirmation(
    tmp_path, monkeypatch, model,
):
    name = "verified-head.dxf"
    final = tmp_path / name
    final.write_bytes(b"EXISTING-PREVIOUS-DXF")
    calls = []
    def fake_staged(_host, stage, _values, _flags, _stock):
        Path(stage, name).write_bytes(b"NEW-DXF-NEVER-PUBLISH")
        return ([name], [])

    monkeypatch.setattr(gui, "_export_selected_parts", fake_staged)
    monkeypatch.setattr(gui.filedialog, "askdirectory",
                        lambda **_kw: str(tmp_path))
    monkeypatch.setattr(gui.messagebox, "askyesno",
                        lambda *args, **kw: calls.append((args, kw)) or False)
    monkeypatch.setattr(gui.messagebox, "showinfo",
                        lambda *_a: pytest.fail("cancel cannot report success"))
    monkeypatch.setattr(gui.messagebox, "showerror",
                        lambda *_a: pytest.fail("this is an operator cancellation"))
    snapshot = {"model": model}
    host = SimpleNamespace(
        fold_designer_app=SimpleNamespace(_phase6_input_snapshot=snapshot),
        _flush_phase6_authoritative_state=lambda: None,
        _phase6_current_existing_parts=lambda: ("head",),
        _has_any_indicator_box=lambda: False,
        _phase6_logical_part_present=lambda *_: False,
        get_float_values=lambda: {"w": 800., "h": 1600., "d": 350.},
        export_z_var=_Bool(False), export_head_var=_Bool(True),
        export_tail_var=_Bool(False), export_door_var=_Bool(False),
        export_base_plate_var=_Bool(False), export_ib_var=_Bool(False),
        export_ib_door_var=_Bool(False), multi_door_enabled_var=_Bool(False),
        draw_stock_var=_Bool(False), receiving_dxf_group_mode_var=_Bool(True),
    )
    assert gui.export_selected_dxf(host) is None
    assert calls and "DXF 檔名已存在" in str(calls[0][0])
    assert final.read_bytes() == b"EXISTING-PREVIOUS-DXF"
    assert not list(tmp_path.glob(".whd-export-stage-*"))
