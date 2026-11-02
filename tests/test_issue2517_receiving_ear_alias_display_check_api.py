"""#2517 Receiving EAR SIDE 2D/3D and CHECK reuse one registered Family identity."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import inspect

import ezdxf
import pytest

from ae_engine import manufacturing_api as api
from gui_modules.application.receiving_ear_side_2d import (
    present_receiving_ear_side_piece_2d,
    present_receiving_ear_side_designer_piece_3d,
)
from gui_modules.project import export_actions
from tests.test_issue1503_ear_side_check_only_dxf import _actual
from tests.test_receiving_base_physical_3d_z_assembly import _assembled


def _source():
    snapshot, geometry = _actual(_assembled)
    body = geometry.part("box_body").render_data
    left = next(piece for piece in body.pieces if piece.role == "left_side")
    return snapshot, geometry, body, left


@pytest.mark.parametrize("model", (
    "受電箱", "RECEIVING", "receiving", "ReCeIvInG", "  receiving  ",
))
def test_registered_aliases_preserve_real_ear_source_display_and_3d(model):
    snapshot, geometry, body, left = _source()
    source = {**snapshot, "model": model}
    context = api.resolve_receiving_ear_side_display_context(
        source, "box_body:left_side", body,
    )
    assert context.should_project and context.source_stamp
    shown = api.project_receiving_ear_side_piece_2d_preview(
        source, left, piece_key="box_body:left_side", geometry=geometry,
        dimensions=context.dimensions, sheet_thickness=context.sheet_thickness,
        display_only_marking_overlap=True,
    )
    assert shown.render_data.metadata["ear_side_mark_preview_count"] == 3
    assert shown.render_data.material.equals(left.render_data.material)
    assert shown.render_data.metadata["ear_side_mark_preview_only"] is True
    assert tuple(left.render_data.scene.primitives) == tuple(
        next(piece for piece in body.pieces if piece.role == "left_side").render_data.scene.primitives
    )
    host = SimpleNamespace()
    isolated = present_receiving_ear_side_designer_piece_3d(
        host, source, geometry, left, "box_body:left_side",
    )
    assert isolated.metadata["ear_side_mark_preview_count"] == 3
    assert host.last_receiving_ear_single_piece_blocker is None


def test_real_gui_primary_2d_alias_uses_committed_designer_not_stale_mirror():
    snapshot, geometry, body, left = _source()
    source = {**snapshot, "model": "receiving"}
    calls = []
    designer = SimpleNamespace(
        _phase6_input_snapshot=source,
        _phase6_resolve_manufacturing_geometry=(
            lambda: calls.append("designer") or geometry
        ),
    )
    host = SimpleNamespace(
        fold_designer_app=designer,
        _compose_phase6_project_snapshot_from_main_gui=lambda: {
            "model": "受電箱", "nfb_config_submitted": False,
        },
    )
    shown, blocker = present_receiving_ear_side_piece_2d(
        host, body, left, "box_body:left_side",
    )
    assert blocker is None
    assert shown.render_data.metadata["ear_side_mark_preview_count"] == 3
    assert calls == ["designer"]


@pytest.mark.parametrize("model", ("受電箱", "receiving", "  ReCeIvInG  "))
def test_check_operator_public_preflight_uses_registered_family_and_keeps_mode(model):
    snapshot, _geometry, _body, _left = _source()
    source = {**snapshot, "model": model, "active_mode": "set_bay"}
    assert api.receiving_ear_side_check_operator_inputs(source) == (
        (800., 1600., 350.), 2.,
    )
    with pytest.raises(ValueError, match="數量版本"):
        api.receiving_ear_side_check_operator_inputs({**source, "active_mode": "quantity"})
    with pytest.raises(ValueError, match="單只"):
        api.receiving_ear_side_check_operator_inputs({**source, "nfb_config_submitted": False})


def test_real_check_only_dxf_alias_roundtrip_remains_unapproved(tmp_path):
    snapshot, geometry, _body, _left = _source()
    source = {**snapshot, "model": "receiving", "active_mode": "set_bay"}
    dimensions, thickness = api.receiving_ear_side_check_operator_inputs(source)
    receipt = api.export_receiving_ear_side_check_only_dxf(
        source, geometry, tmp_path,
        dimensions=dimensions, sheet_thickness=thickness,
    )
    assert receipt.saved_dxf_roundtrip_verified
    assert not receipt.manufacturing_ready
    assert not receipt.welding_workmanship_certified
    assert len(receipt.output_paths) == 2
    for _side, filepath in receipt.output_paths:
        assert Path(filepath).is_file()
        assert len(ezdxf.readfile(filepath).modelspace()) > 0


def test_non_receiving_and_unsubmitted_still_fail_closed(tmp_path):
    snapshot, geometry, body, left = _source()
    for model in ("金庫型", "UNKNOWN"):
        source = {**snapshot, "model": model}
        assert not api.resolve_receiving_ear_side_display_context(
            source, "box_body:left_side", body,
        ).should_project
        with pytest.raises(ValueError, match="REQUIRES_SUBMITTED_RECEIVING"):
            api.project_receiving_ear_side_piece_2d_preview(
                source, left, piece_key="box_body:left_side", geometry=geometry,
                dimensions=(800., 1600., 350.), sheet_thickness=2.,
            )
        with pytest.raises(ValueError, match="單只"):
            api.receiving_ear_side_check_operator_inputs(source)
    stale = {**snapshot, "model": "receiving", "nfb_config_submitted": False}
    with pytest.raises(ValueError, match="PRIMARY_SOURCE_DRIFT"):
        api.resolve_receiving_ear_side_display_context(
            stale, "box_body:left_side", body, main_mirror=snapshot,
        )
    with pytest.raises(ValueError, match="MATCHING_SUBMITTED"):
        api.export_receiving_ear_side_check_only_dxf(
            stale, geometry, tmp_path / "none",
            dimensions=(800., 1600., 350.), sheet_thickness=2.,
        )
    assert not (tmp_path / "none").exists()


def test_gui_check_does_not_own_family_source_gate_and_real_alias_reaches_engine(tmp_path, monkeypatch):
    snapshot, geometry, _body, _left = _source()
    source = {**snapshot, "model": "ReCeIvInG", "active_mode": "set_bay"}
    messages = []
    monkeypatch.setattr(export_actions.filedialog, "askdirectory", lambda **_kw: str(tmp_path))
    monkeypatch.setattr(export_actions.messagebox, "showerror",
                        lambda *args: messages.append(("error", args)))
    monkeypatch.setattr(export_actions.messagebox, "showinfo",
                        lambda *args: messages.append(("ok", args)))
    host = SimpleNamespace(
        _flush_phase6_authoritative_state=lambda: None,
        fold_designer_app=SimpleNamespace(
            _phase6_input_snapshot=source,
            _phase6_resolve_manufacturing_geometry=lambda: geometry,
        ),
    )
    receipt = export_actions.export_receiving_ear_side_check_dxf(host)
    assert receipt is not None and receipt.saved_dxf_roundtrip_verified
    assert messages and messages[-1][0] == "ok"
    gui_source = inspect.getsource(export_actions.export_receiving_ear_side_check_dxf)
    assert "manufacturing_api.receiving_ear_side_check_operator_inputs(" in gui_source
    assert 'snapshot.get("model")' not in gui_source
