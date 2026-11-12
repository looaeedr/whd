"""#2517: legacy Receiving Bay N must not auto-create inner frames from bad T/FW.

The single authority is the existing Engine positive physical mm gate, before
the original Receiving Family generates transient default inner-door sources.
No new frame, Panel, Divider geometry or 3D/DXF approval is authored here.
"""
from __future__ import annotations

from copy import deepcopy

import pytest

from ae_engine import manufacturing_api as api
from ae_engine.receiving_layout import project_receiving_bay_legacy_aliases
from tests.test_issue2517_receiving_saved_door_mode_source_parity import (
    _actual_bay_source,
)
import phase6_project_file as project


def _bay_two(source):
    return project_receiving_bay_legacy_aliases(
        source, set_index=0, bay_index=1, validate_common=False,
    )


@pytest.mark.parametrize("field", ("t", "fw"))
@pytest.mark.parametrize("invalid", (
    True, False, None, 0, -2, "nan", "inf", float("nan"),
    float("inf"), {}, [],
))
def test_raw_invalid_thickness_or_frame_width_cannot_mint_second_bay_inner_frame(
    field, invalid,
):
    source = _actual_bay_source("true")
    source[field] = invalid
    before = repr(source)
    with pytest.raises(ValueError, match="包外尺寸"):
        _bay_two(source)
    assert repr(source) == before


@pytest.mark.parametrize("field", ("t", "fw"))
def test_absent_legacy_physical_source_cannot_grant_transient_inner_frame(field):
    source = _actual_bay_source(True)
    source.pop(field)
    before = deepcopy(source)
    if field == "t":
        # Original legacy requirement: no T means no physical source.
        view = _bay_two(source)
        assert "inner_doors" not in view
    else:
        # Only absent FW has an existing Receiving Family default.
        view = _bay_two(source)
        assert view["multi_door_enabled"] is True
        assert view["inner_doors"]
    assert source == before


@pytest.mark.parametrize("raw_t,raw_fw", (
    (2.0, 29.0),
    ("2.125", "29.25"),
    (2.5, 30.5),
))
def test_valid_original_mm_preserves_legacy_inner_panel_and_frame_source(
    raw_t, raw_fw,
):
    source = _actual_bay_source("true")
    source.update({"t": raw_t, "fw": raw_fw})
    before = deepcopy(source)
    bay = _bay_two(source)
    assert bay["t"] == raw_t
    assert bay["fw"] == raw_fw
    assert bay["multi_door_enabled"] is True
    assert bay["door_layout_columns"] == [[800.0, [1100.0, 500.0]]]
    assert len(bay["inner_doors"]) == 1
    assert bay["inner_doors"][0]["cell_key"] == "0:0"
    # The real public Receiving Family owns finished inner-door panels
    # and frame sheets; the legacy fallback never writes those to project.
    assert len(api.derive_receiving_inner_door_panels(bay)) == 1
    assert source == before


def test_real_project_reload_preserves_authored_t_fw_and_no_bay2_door_state(tmp_path):
    source = _actual_bay_source("true")
    source["t"], source["fw"] = 2.125, 29.25
    original = deepcopy(source)
    target = project.write_project(
        tmp_path / "receiving-bay-innerdoor-physical-t-fw.p6fold",
        {"schema": project.PROJECT_SCHEMA, "snapshot": source},
    )
    reopened = project.read_project(target)["snapshot"]
    assert reopened["t"] == 2.125
    assert reopened["fw"] == 29.25
    saved_before = deepcopy(reopened)
    bay = _bay_two(reopened)
    assert bay["multi_door_enabled"] is True
    assert bay["inner_doors"]
    assert "door_state" not in bay["receiving_layout"]["sets"][0]["bays"][1]
    assert reopened == saved_before
    assert source == original
