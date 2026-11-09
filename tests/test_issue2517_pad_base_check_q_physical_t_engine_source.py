# -*- coding: utf-8 -*-
"""#2517 PAD+Base CHECK/Q T provenance is validated by the public Engine."""
from __future__ import annotations

from copy import deepcopy
import inspect
import json
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api as api
from ae_engine.manufacturing_equivalence import (
    ManufacturingParameters, manufacturing_equivalence_payload,
)
from ae_engine import receiving_nfb_pad_pair_manufacturing as pair_owner
from gui_modules.project import export_actions as gui


def _host(snapshot):
    return SimpleNamespace(
        _flush_phase6_authoritative_state=lambda: None,
        fold_designer_app=SimpleNamespace(_phase6_input_snapshot=snapshot),
    )


def _stub_live_pad_action(monkeypatch, selected_snapshot, tmp_path):
    import fold_designer_bridge as bridge
    from tkinter import simpledialog

    calls = []
    monkeypatch.setattr(
        api, "committed_nfb_pad_draft_parts",
        lambda _: ("real-confirmed-pad",),
    )
    monkeypatch.setattr(
        bridge, "_phase6_final_scene_adapter",
        lambda _: SimpleNamespace(query_assembly_render_data=lambda:
            SimpleNamespace(assembly_parts=("real-assembly",))),
    )
    monkeypatch.setattr(
        api, "resolve_receiving_pad_base_export_source",
        lambda _: SimpleNamespace(
            snapshot=deepcopy(selected_snapshot), version_id="set1_bay1",
        ),
    )
    monkeypatch.setattr(
        simpledialog, "askstring",
        lambda title, _: "SPCC" if "材質" in title else "LASER",
    )
    monkeypatch.setattr(simpledialog, "askinteger", lambda *a, **kw: 2)
    monkeypatch.setattr(
        gui.filedialog, "askdirectory",
        lambda **kw: calls.append("ask-directory") or str(tmp_path),
    )
    monkeypatch.setattr(
        api, "export_verified_pad_base_part_only",
        lambda *args, **kw: calls.append(("export", args, kw)) or
            SimpleNamespace(
                pad_piece_count=2, base_piece_count=2,
                output_directory=str(tmp_path),
            ),
    )
    monkeypatch.setattr(
        gui.messagebox, "showinfo", lambda *a: calls.append(("success", a)),
    )
    monkeypatch.setattr(
        gui.messagebox, "showerror", lambda *a: calls.append(("error", a)),
    )
    return calls


@pytest.mark.parametrize("bad", [
    True, False, 0, -1, "0", "-1", None, "", "not-a-number",
    float("nan"), float("inf"), float("-inf"),
    "nan", "inf", "-inf", [], {},
])
def test_pad_gui_rejects_invalid_selected_source_before_path_or_export(
    monkeypatch, tmp_path, bad,
):
    root = {"model": "受電箱", "nfb_config_submitted": True, "t": 2.0}
    selected = {**root, "t": bad}
    before = repr((root, selected))
    calls = _stub_live_pad_action(monkeypatch, selected, tmp_path)
    assert gui.export_receiving_pad_base_part_only_dxf(_host(root)) is None
    assert len(calls) == 1 and calls[0][0] == "error"
    assert "T 包外尺寸" in calls[0][1][1]
    assert repr((root, selected)) == before
    assert not tuple(tmp_path.iterdir())


@pytest.mark.parametrize("selected_raw,expected", [
    (2, 2.0), ("2", 2.0), ("2.375", 2.375), (2.375, 2.375),
])
def test_pad_gui_forwards_engine_validated_selected_t_without_coercion(
    monkeypatch, tmp_path, selected_raw, expected,
):
    # Root value is NOT the projected selected version's physical T.
    root = {"model": "受電箱", "nfb_config_submitted": True, "t": 2.0}
    selected = {**root, "t": selected_raw}
    calls = _stub_live_pad_action(monkeypatch, selected, tmp_path)
    result = gui.export_receiving_pad_base_part_only_dxf(_host(root))
    assert result.pad_piece_count == 2
    assert [item if isinstance(item, str) else item[0] for item in calls] == [
        "ask-directory", "export", "success",
    ]
    args, kwargs = calls[1][1], calls[1][2]
    assert args[0] == selected
    assert args[1] == ("real-assembly",)
    params = kwargs["parameters"]
    assert isinstance(params, ManufacturingParameters)
    assert params == ManufacturingParameters("SPCC", expected, "LASER")
    assert params.thickness == api.normalize_operator_source_dimension(
        selected_raw, field="t",
    )
    assert root["t"] == 2.0


@pytest.mark.parametrize("bad", [
    True, False, 0, -1, "0", None, "nan", float("inf"), 1.5j,
])
def test_headless_pad_pair_export_fails_before_geometry_or_any_dxf(
    monkeypatch, tmp_path, bad,
):
    monkeypatch.setattr(
        pair_owner, "verified_pad_base_physical_sheets",
        lambda *a, **kw: pytest.fail(
            "bad T must fail before PAD/Base geometry or source solve",
        ),
    )
    out = tmp_path / "no-pad-output"
    with pytest.raises(ValueError, match="T 包外尺寸"):
        api.export_verified_pad_base_part_only(
            {}, (), out,
            version_id="real-version", box_count=1,
            parameters=ManufacturingParameters("SPCC", bad, "LASER"),
        )
    assert not out.exists()


@pytest.mark.parametrize("bad", [
    True, False, 0, "0", -1, None, "", "bad",
    float("nan"), float("inf"), "inf",
])
def test_headless_manufacturing_equivalence_fingerprint_rejects_bad_t_first(bad):
    # Source must fail before material or CUTTING access; an invalid
    # ManufacturingParameters T must never get a physical equivalence key.
    from types import SimpleNamespace
    render = SimpleNamespace(material=None, scene=None)
    with pytest.raises(ValueError, match="T 包外尺寸"):
        manufacturing_equivalence_payload(
            render, ManufacturingParameters("SPCC", bad, "LASER"),
        )


def test_headless_equivalence_preserves_fractional_t_and_json_roundtrip():
    from shapely.geometry import box
    from ae_engine.sheetmetal_drawing import LinePrimitive
    from ae_engine.sheetmetal_geometry import Vec2

    render = SimpleNamespace(
        material=box(0, 0, 10, 10),
        scene=SimpleNamespace(primitives=(
            LinePrimitive(Vec2(0, 0), Vec2(10, 0), "CUTTING"),
        )),
    )
    numeric = manufacturing_equivalence_payload(
        render, ManufacturingParameters("SPCC", 2.375, "LASER"),
    )
    serialized = manufacturing_equivalence_payload(
        render, ManufacturingParameters("SPCC", "2.375", "LASER"),
    )
    assert serialized == numeric
    assert json.loads(serialized)["parameters"]["thickness"] == 2.375


def test_pad_gui_and_pair_headless_use_one_engine_physical_t_policy():
    gui_source = inspect.getsource(gui.export_receiving_pad_base_part_only_dxf)
    pair_source = inspect.getsource(pair_owner.export_verified_pad_base_part_only)
    fingerprint_source = inspect.getsource(manufacturing_equivalence_payload)
    assert 'normalize_operator_source_dimension(' in gui_source
    assert 'snapshot.get("t"), field="t"' in gui_source
    assert 'float(snapshot["t"])' not in gui_source
    assert 'normalize_operator_source_dimension(parameters.thickness, field="t")' in pair_source
    assert 'normalize_operator_source_dimension(' in fingerprint_source
    assert 'parameters.thickness, field="t"' in fingerprint_source
