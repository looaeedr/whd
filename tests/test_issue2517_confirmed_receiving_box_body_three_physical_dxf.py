"""#2517 confirmed Receiving BoxBody uses existing independent physical sheets."""
from dataclasses import replace
from pathlib import Path

import ezdxf
import pytest

from ae_engine import manufacturing_api
from ae_engine.contracts import BoxBodyPartSpec, ManufacturingContext
from ae_engine.integration_api import (
    ManufacturingResolvedBayInput, ManufacturingSourceIdentity,
    export_verified_resolved_integration_bays,
)

REPO = Path(__file__).resolve().parents[1]


def _three_piece_spec():
    # Explicit factory-confirmed test values from the existing Receiving
    # Family defaults; no real source DXF or incomplete input is inferred.
    snapshot = {
        "model": "受電箱", "w": 800.0, "h": 1600.0, "d": 350.0,
        "t": 2.0, "fw": 29.0, "zl1": -24.0,
        "zl2": 24.0, "zr2": 18.0,
    }
    state = manufacturing_api.resolve_receiving_box_body_structure_state(None)
    state = manufacturing_api.set_side_back_back_panel_mode(state, "FULL")
    back = manufacturing_api.resolve_box_body_back_panel_contract(
        "受電箱", snapshot, structure_state=state,
    )
    return BoxBodyPartSpec(
        width=800.0, height=1600.0, depth=350.0, thickness=2.0,
        frame_width=29.0, model_name="受電箱",
        fold_profile=manufacturing_api.box_body_profile_to_fold_segments(
            manufacturing_api.build_box_body_fold_profile(snapshot),
        ), structure_state=state, back_panel_contract=back,
    )


def _bay(spec):
    return ManufacturingResolvedBayInput(
        family="受電箱",
        source=ManufacturingSourceIdentity("P1", "sha", "Set1", "Bay1"),
        confirmed_parts=(("box_body", spec),),
    )


def test_confirmed_receiving_box_body_reopens_three_physical_dxfs(tmp_path):
    spec = _three_piece_spec()
    checks = []
    result = export_verified_resolved_integration_bays(
        (_bay(spec),), tmp_path / "manufactured",
        context=ManufacturingContext(resource_root=REPO),
        pre_commit_guard=lambda: checks.append("same-original"),
    )
    assert checks == ["same-original", "same-original"]
    assert result.physical_dxf_roundtrip_verified
    assert len(result.output_files) == 3
    filenames = {Path(p).name for p in result.output_files.values()}
    assert all(any(role in name for name in filenames)
               for role in ("left_side", "back", "right_side"))
    for filename in result.output_files.values():
        drawing = ezdxf.readfile(filename)
        layers = {e.dxf.layer for e in drawing.modelspace()}
        assert "CUTTING" in layers


def test_confirmed_box_body_uses_existing_structural_engine_resolver(tmp_path, monkeypatch):
    original = manufacturing_api.build_box_body_structure_render_data
    calls = []
    def capture(spec, ctx):
        calls.append((spec, ctx))
        return original(spec, ctx)
    monkeypatch.setattr(manufacturing_api, "build_box_body_structure_render_data", capture)
    spec = _three_piece_spec()
    context = ManufacturingContext(resource_root=REPO)
    export_verified_resolved_integration_bays(
        (_bay(spec),), tmp_path / "manufactured",
        context=context, pre_commit_guard=lambda: None,
    )
    assert calls == [(spec, context)]


@pytest.mark.parametrize("edit", [
    {"fold_profile": ()},
    {"back_panel_contract": {}},
    {"structure_state": {"active_type": "integral"}},
])
def test_unconfirmed_three_piece_input_never_writes_output(tmp_path, edit):
    spec = replace(_three_piece_spec(), **edit)
    with pytest.raises(ValueError, match="RECEIVING_BOX_BODY_AUTHORED_FOLD_REQUIRED"):
        export_verified_resolved_integration_bays(
            (_bay(spec),), tmp_path / "manufactured",
            context=ManufacturingContext(resource_root=REPO),
            pre_commit_guard=lambda: None,
        )
    assert not (tmp_path / "manufactured").exists()


def test_missing_three_physical_reference_baselines_fails_closed(tmp_path):
    spec = _three_piece_spec()
    with pytest.raises((ValueError, FileNotFoundError)):
        export_verified_resolved_integration_bays(
            (_bay(spec),), tmp_path / "manufactured",
            context=ManufacturingContext(resource_root=tmp_path),
            pre_commit_guard=lambda: None,
        )
    assert not (tmp_path / "manufactured").exists()
