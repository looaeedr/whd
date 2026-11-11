"""#2517: independently reopened Receiving per-Bay DXFs recheck live source."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import ezdxf
import pytest

from ae_engine import manufacturing_api as api
from gui_modules.project import export_actions as gui
from tests.test_issue1504_ac09_ac24_original_multibay_independent_export import (
    _source_with_missing_second_model, _fresh_unrelated_geometry,
)
from tests.test_issue1502_single_button_full_csv_receiving_export import _flags


def _head_only():
    return _flags(
        box_body=False, head=True, tail=False, door=False,
        base_plate=False, indicator_box=False, indicator_door=False,
    )


def test_headless_actual_two_bay_dxf_reopens_and_checks_source_twice(tmp_path):
    source = _source_with_missing_second_model()
    before = deepcopy(source)
    checks = []
    outputs = api.export_current_receiving_multibay_dxf(
        source,
        physical_bay_geometry_provider=lambda si, bi:
            _fresh_unrelated_geometry(source, si, bi),
        flags=_head_only(),
        output_dir=tmp_path / "fresh",
        pre_commit_guard=lambda: checks.append("same physical source"),
    )
    assert checks == ["same physical source", "same physical source"]
    assert len(outputs) == 2
    assert all("head" in name for name in outputs)
    assert all(
        any(e.dxf.layer == "CUTTING" for e in ezdxf.readfile(path).modelspace())
        for path in outputs.values()
    )
    assert source == before


def test_headless_drift_after_actual_dxf_staging_retains_preexisting_bay_outputs(
    tmp_path,
):
    source = _source_with_missing_second_model()
    before = deepcopy(source)
    root = tmp_path / "previous"
    earlier = api.export_current_receiving_multibay_dxf(
        source,
        physical_bay_geometry_provider=lambda si, bi:
            _fresh_unrelated_geometry(source, si, bi),
        flags=_head_only(), output_dir=root,
    )
    retained = {p: Path(p).read_bytes() for p in earlier.values()}
    checks = []

    def stale_guard():
        checks.append("checked")
        if len(checks) == 2:
            # A different user's confirmed Hole Editor state may change while
            # the source's original live multibay DXF is being staged.
            source["receiving_layout"]["sets"][0]["bays"][1]["panel_name"] = "updated"
        if source != before:
            raise ValueError("DXF_WORKSPACE_SOURCE_CHANGED")

    with pytest.raises(ValueError, match="DXF_WORKSPACE_SOURCE_CHANGED"):
        api.export_current_receiving_multibay_dxf(
            source,
            physical_bay_geometry_provider=lambda si, bi:
                _fresh_unrelated_geometry(source, si, bi),
            flags=_head_only(), output_dir=root,
            pre_commit_guard=stale_guard, overwrite=True,
        )
    assert checks == ["checked", "checked"]
    assert {p: Path(p).read_bytes() for p in retained} == retained
    assert {str(p) for p in root.glob("*.dxf")} == set(retained)


def test_invalid_supplied_source_witness_is_rejected_before_writing_any_dxf(
    tmp_path,
):
    source = _source_with_missing_second_model()
    target = tmp_path / "invalid"
    with pytest.raises(TypeError, match="RECEIVING_MULTIBAY_PRECOMMIT_GUARD_INVALID"):
        api.export_current_receiving_multibay_dxf(
            source,
            physical_bay_geometry_provider=lambda si, bi:
                _fresh_unrelated_geometry(source, si, bi),
            flags=_head_only(), output_dir=target,
            pre_commit_guard="true",
        )
    assert not target.exists()


def test_original_gui_ungrouped_multi_bay_passes_current_source_witness(
    tmp_path, monkeypatch,
):
    import fold_designer_bridge as bridge
    from tests.test_issue1502_multibay_original_gui_export_integration import (
        _native_callback_host,
    )

    source = _source_with_missing_second_model()
    host = _native_callback_host(monkeypatch, source, [])
    # The GUI only gathers a callback. The Engine owns all source validation,
    # real manufacturing geometry and atomic writing for this selected route.
    monkeypatch.setattr(bridge, "_phase6_composition", lambda _app: object())
    observed = []

    def capture(snapshot, **kwargs):
        guard = kwargs["pre_commit_guard"]
        assert callable(guard)
        guard()
        observed.append((snapshot, kwargs["flags"], kwargs["group_mode"] if
                         "group_mode" in kwargs else None))
        return {"head": tmp_path / "passed.dxf"}

    monkeypatch.setattr(api, "export_current_receiving_multibay_dxf", capture)
    names, errors = gui._export_selected_resolved_parts(
        host, str(tmp_path), _head_only(),
    )
    assert names == ["passed.dxf"] and not errors
    assert len(observed) == 1
    assert observed[0][0] == source
    assert observed[0][2] is None
