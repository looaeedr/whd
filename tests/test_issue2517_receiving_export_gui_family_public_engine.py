"""#2517 Receiving export buttons only interpret Engine-registered Family names."""
from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api
from gui_modules.project import export_actions as gui


class _Bool:
    def __init__(self, value=False):
        self.value = value

    def get(self):
        return self.value


def _flags_host(snapshot, available):
    flags = {
        "export_z_var": _Bool(), "export_head_var": _Bool(),
        "export_tail_var": _Bool(), "export_door_var": _Bool(),
        "export_base_plate_var": _Bool(True),
        "export_ib_var": _Bool(), "export_ib_door_var": _Bool(),
    }
    return SimpleNamespace(
        **flags,
        fold_designer_app=SimpleNamespace(
            _phase6_input_snapshot=snapshot,
            designer_workspace=SimpleNamespace(available_parts=available),
        ),
        _phase6_logical_part_present=lambda parts, key: any(
            str(p) == key or str(p).startswith(key + ":") for p in parts
        ),
    )


@pytest.mark.parametrize("model", ("受電箱", "RECEIVING", "receiving", " ReCeIvInG "))
def test_existing_export_checkbox_uses_current_authoritative_nfb_physical_parts(model):
    source = {"model": model, "nfb_config_submitted": True}
    original = deepcopy(source)
    host = _flags_host(source, ("base_plate:nfb_layer:0", "inner_door:0"))
    selected = gui._selected_export_flags(host, (), False)
    assert selected["base_plate"] is True
    assert not any(value for key, value in selected.items() if key != "base_plate")
    assert source == original


@pytest.mark.parametrize("changes", (
    {"model": "金庫型"},
    {"model": "UNKNOWN"},
    {"model": "receiving", "nfb_config_submitted": False},
))
def test_no_virtual_or_unsubmitted_base_sheet_from_family_alias(changes):
    snapshot = {"model": "受電箱", "nfb_config_submitted": True}
    snapshot.update(changes)
    host = _flags_host(snapshot, ("base_plate:nfb_layer:0",))
    assert gui._selected_export_flags(host, (), False)["base_plate"] is False


def test_two_bay_original_export_routes_alias_to_engine_multibay_gate(
    tmp_path, monkeypatch,
):
    from tests.test_issue1502_current_csv_multi_bay_once import _multi
    from tests.test_issue1502_multibay_original_gui_export_integration import (
        _native_callback_host,
    )
    from tests.test_issue1502_single_button_full_csv_receiving_export import _flags

    source = _multi()
    source["model"] = "receiving"
    original = deepcopy(source)
    host = _native_callback_host(monkeypatch, source, [])
    def proof(*_args, **_kwargs):
        raise ValueError("ENGINE_MULTIBAY_GATE_REACHED")
    monkeypatch.setattr(manufacturing_api, "export_current_receiving_multibay_dxf", proof)
    with pytest.raises(ValueError, match="ENGINE_MULTIBAY_GATE_REACHED"):
        gui._export_selected_resolved_parts(
            host, str(tmp_path),
            _flags(box_body=True, head=False, tail=False, door=False,
                   base_plate=False, indicator_box=False, indicator_door=False),
        )
    assert source == original
    assert not list(tmp_path.glob("*.dxf"))




def test_main_gui_grouped_dxf_opts_into_engine_saved_nfb_pairs(tmp_path, monkeypatch):
    from tests.test_issue1502_current_csv_multi_bay_once import _multi
    from tests.test_issue1502_multibay_original_gui_export_integration import (
        _native_callback_host,
    )

    snapshot = _multi()
    before = deepcopy(snapshot)
    host = _native_callback_host(monkeypatch, snapshot, [])
    host.receiving_dxf_group_mode_var = _Bool("ALL")
    seen = []
    def group_export(*_args, **kwargs):
        seen.append(kwargs)
        raise ValueError("ENGINE_COMPOSED_SOURCE_GATE_REACHED")
    monkeypatch.setattr(manufacturing_api, "export_grouped_receiving_multibay_dxf",
                        group_export)
    with pytest.raises(ValueError, match="ENGINE_COMPOSED_SOURCE_GATE_REACHED"):
        gui._export_selected_resolved_parts(
            host, str(tmp_path),
            {"head": True, "door": True, "base_plate": True},
        )
    assert len(seen) == 1
    assert seen[0]["group_mode"] == "ALL"
    assert seen[0]["include_saved_nfb_pairs"] is True
    assert snapshot == before
    assert not list(tmp_path.glob("*.dxf"))



def test_multibay_engine_accepts_registered_receiving_alias_not_vault(tmp_path):
    """The public multibay export gate uses Family Registry, never raw label case."""
    from ae_engine.receiving_layout import new_receiving_layout

    one_bay = new_receiving_layout(width=800, height=1600, depth=350)
    for model in ("receiving", "RECEIVING", "受電箱"):
        with pytest.raises(
            ValueError, match="RECEIVING_MULTIBAY_REQUIRES_MULTIPLE_PHYSICAL_BAYS",
        ):
            manufacturing_api.export_current_receiving_multibay_dxf(
                {"model": model, "active_mode": "set_bay",
                 "receiving_layout": one_bay},
                physical_bay_geometry_provider=None, flags={},
                output_dir=tmp_path,
            )
    with pytest.raises(ValueError, match="RECEIVING_MULTIBAY_CURRENT_FAMILY_REQUIRED"):
        manufacturing_api.export_current_receiving_multibay_dxf(
            {"model": "vault", "active_mode": "set_bay",
             "receiving_layout": one_bay},
            physical_bay_geometry_provider=None, flags={},
            output_dir=tmp_path,
        )


def test_real_side_marking_button_uses_engine_registered_receiving_family(
    tmp_path, monkeypatch,
):
    from tests.test_issue2517_receiving_ear_alias_display_check_api import _source

    snapshot, geometry, _body, _left = _source()
    source = {**snapshot, "model": "receiving", "active_mode": "set_bay"}
    observed = []
    events = []
    def output(snap, actual, folder, **options):
        observed.append((snap, actual, folder, options))
        return SimpleNamespace(
            physical_ear_ids=("ear-left", "ear-right"),
            marking_lines_verified=6,
            output_paths=(("box_body:left_side", "left.dxf"),
                          ("box_body:right_side", "right.dxf")),
        )
    monkeypatch.setattr(
        manufacturing_api, "export_receiving_ear_side_manufacturing_marking_dxf",
        output,
    )
    monkeypatch.setattr(gui.filedialog, "askdirectory", lambda **_kw: str(tmp_path))
    monkeypatch.setattr(gui.messagebox, "showerror", lambda *_args: events.append("error"))
    monkeypatch.setattr(gui.messagebox, "showinfo", lambda *_args: events.append("ok"))
    host = SimpleNamespace(
        _flush_phase6_authoritative_state=lambda: None,
        fold_designer_app=SimpleNamespace(
            _phase6_input_snapshot=source,
            _phase6_resolve_manufacturing_geometry=lambda: geometry,
        ),
    )
    result = gui.export_receiving_ear_side_manufacturing_dxf(host)
    assert result is not None
    assert events == ["ok"]
    assert observed == [(
        source, geometry, str(tmp_path),
        {"dimensions": (800., 1600., 350.),
         "sheet_thickness": 2., "overwrite": False},
    )]


def test_pad_operator_alias_reaches_engine_source_check_before_any_picker(monkeypatch):
    import fold_designer_bridge as bridge
    from tkinter import simpledialog

    source = {"model": " ReCeIvInG ", "nfb_config_submitted": True}
    original = deepcopy(source)
    seen = []
    monkeypatch.setattr(
        manufacturing_api, "committed_nfb_pad_draft_parts",
        lambda snapshot: seen.append(snapshot) or ("verified-draft",),
    )
    monkeypatch.setattr(
        bridge, "_phase6_final_scene_adapter",
        lambda _designer: SimpleNamespace(query_assembly_render_data=(
            lambda: SimpleNamespace(assembly_parts=("verified-scene",))
        )),
    )
    monkeypatch.setattr(simpledialog, "askstring", lambda *_args: None)
    monkeypatch.setattr(gui.messagebox, "showerror",
                        lambda *_args: pytest.fail("alias must reach material picker"))
    host = SimpleNamespace(
        _flush_phase6_authoritative_state=lambda: None,
        fold_designer_app=SimpleNamespace(_phase6_input_snapshot=source),
    )
    assert gui.export_receiving_pad_base_part_only_dxf(host) is None
    assert seen == [source]
    assert source == original


def test_pad_nonreceiving_remains_blocked_before_engine_draft(monkeypatch):
    calls = []
    monkeypatch.setattr(
        manufacturing_api, "committed_nfb_pad_draft_parts",
        lambda _snapshot: calls.append("wrong_family") or ("bad",),
    )
    messages = []
    monkeypatch.setattr(gui.messagebox, "showerror",
                        lambda _title, text: messages.append(text))
    host = SimpleNamespace(
        _flush_phase6_authoritative_state=lambda: None,
        fold_designer_app=SimpleNamespace(
            _phase6_input_snapshot={
                "model": "金庫型", "nfb_config_submitted": True,
            },
        ),
    )
    assert gui.export_receiving_pad_base_part_only_dxf(host) is None
    assert not calls
    assert messages and "受電箱" in messages[0]
