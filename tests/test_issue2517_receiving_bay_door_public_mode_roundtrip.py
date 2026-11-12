"""#2517 Receiving saved Bay Door mode shares Engine source between 2D and DXF.

The .p6fold codec preserves textual operator booleans. The same physical Bay
must not have an extra Door in one GUI query and no Door in another.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import ezdxf
import pytest

from ae_engine import manufacturing_api as api
from ae_engine.contracts import ManufacturingContext
from ae_engine.receiving_layout import (
    new_receiving_layout, update_receiving_bay,
    project_receiving_bay_legacy_aliases,
)
import phase6_project_file as project


def _bay_snapshot(flag, *, columns=None):
    if columns is None:
        columns = [[800.0, [1100.0, 500.0]]]
    layout = new_receiving_layout(width=800, height=1600, depth=350)
    layout = update_receiving_bay(
        layout, set_index=0, bay_index=0,
        door_state={
            "multi_door_enabled": flag,
            "door_layout_columns": deepcopy(columns),
            "door_layout_scope": "receiving-main",
            "inner_doors": [],
        },
    )
    return {
        "model": "受電箱", "active_mode": "set_bay",
        "receiving_layout": layout,
        "w": 800.0, "h": 1600.0, "d": 350.0,
        "t": 2.0, "fw": 29.0,
    }


@pytest.mark.parametrize("flag", (False, "false", " FALSE ", "off", "0", 0))
def test_disabled_saved_bay_door_mode_never_draws_or_selects_physical_door(flag):
    snapshot = _bay_snapshot(flag)
    before = deepcopy(snapshot)
    projected = project_receiving_bay_legacy_aliases(
        snapshot, set_index=0, bay_index=0,
    )
    assert projected["multi_door_enabled"] == flag
    bay = projected["receiving_layout"]["sets"][0]["bays"][0]
    assert api.project_receiving_operator_bay_door_split_ratio(bay) is None
    assert api.project_receiving_operator_door_cell_sources(
        snapshot, set_index=0, bay_index=0,
    ) is None
    assert snapshot == before


@pytest.mark.parametrize("flag", (False, "false", "0"))
def test_disabled_bay_needs_no_active_door_grid_to_validate(flag):
    snapshot = _bay_snapshot(flag, columns=[])
    projected = project_receiving_bay_legacy_aliases(
        snapshot, set_index=0, bay_index=0,
    )
    assert projected["multi_door_enabled"] == flag
    bay = projected["receiving_layout"]["sets"][0]["bays"][0]
    assert api.project_receiving_operator_bay_door_split_ratio(bay) is None
    assert api.project_receiving_operator_door_cell_sources(
        snapshot, set_index=0, bay_index=0,
    ) is None


@pytest.mark.parametrize("flag", (True, "true", " TRUE ", "on", "1", 1))
def test_true_saved_bay_door_uses_same_canonical_two_physical_cells(flag):
    snapshot = _bay_snapshot(flag)
    before = deepcopy(snapshot)
    view = project_receiving_bay_legacy_aliases(
        snapshot, set_index=0, bay_index=0,
    )
    bay = view["receiving_layout"]["sets"][0]["bays"][0]
    seam = api.project_receiving_operator_bay_door_split_ratio(bay)
    assert seam == pytest.approx(1100.0 / 1600.0)
    assert api.project_receiving_operator_bay_sketch_dimensions(bay) == pytest.approx(
        (800.0, 1600.0, seam),
    )
    selection = api.project_receiving_operator_door_cell_sources(
        snapshot, set_index=0, bay_index=0,
    )
    assert selection is not None
    selected, cells = selection
    assert selected == view
    assert [(c.column_index, c.row_index, c.start_height) for c in cells] == [
        (0, 0, 1100.0), (0, 1, 500.0),
    ]
    assert snapshot == before


@pytest.mark.parametrize("flag", (None, "sometimes", 2, -1, 0.5, [], {}))
def test_invalid_bay_mode_cannot_hide_or_enable_untrusted_physical_door(flag):
    snapshot = _bay_snapshot(flag)
    prior = repr(snapshot)
    bay = snapshot["receiving_layout"]["sets"][0]["bays"][0]
    with pytest.raises(ValueError, match="設定的布林值"):
        api.project_receiving_operator_bay_door_split_ratio(bay)
    with pytest.raises(ValueError, match="設定的布林值"):
        project_receiving_bay_legacy_aliases(
            snapshot, set_index=0, bay_index=0,
        )
    with pytest.raises(ValueError, match="設定的布林值"):
        api.project_receiving_operator_door_cell_sources(
            snapshot, set_index=0, bay_index=0,
        )
    assert repr(snapshot) == prior


@pytest.mark.parametrize("flag", ("false", "true"))
def test_real_bay_p6fold_reload_preserves_public_door_mode_source(tmp_path, flag):
    original = _bay_snapshot(flag)
    saved_file = project.write_project(
        tmp_path / ("receiving-bay-door-" + flag + ".p6fold"),
        {"schema": project.PROJECT_SCHEMA, "snapshot": original},
    )
    restored = project.read_project(saved_file)["snapshot"]
    bay = restored["receiving_layout"]["sets"][0]["bays"][0]
    assert bay["door_state"]["multi_door_enabled"] == flag
    before = deepcopy(restored)
    view = project_receiving_bay_legacy_aliases(
        restored, set_index=0, bay_index=0,
    )
    selection = api.project_receiving_operator_door_cell_sources(
        restored, set_index=0, bay_index=0,
    )
    if flag == "false":
        assert selection is None
        assert api.project_receiving_operator_bay_door_split_ratio(bay) is None
    else:
        assert selection is not None
        assert len(selection[1]) == 2
        assert api.project_receiving_operator_bay_door_split_ratio(bay) == pytest.approx(
            1100.0 / 1600.0,
        )
        # A saved GUI Door stable ID must select the very same Engine sheet
        # for a real FinalScene/CUTTING+BEND export, never guessed 2D geometry.
        upper = selection[1][0]
        spec = api.build_door_operator_part_spec(
            {
                "w": upper.start_width, "h": upper.start_height,
                "t": view["t"], "fw": view["fw"],
                "door_gap_w": 3.5, "door_gap_h": 3.5,
                "door_fold_l": 19.0, "door_fold_r": 19.0,
                "door_fold_t": 19.0, "door_fold_b": 19.0,
            },
            model_name="受電箱", frame_edges=upper.edges,
        )
        render = api.build_part_render_data(
            spec, ManufacturingContext(resource_root=Path(__file__).resolve().parents[1]),
        )
        assert render.material is not None and render.material.area > 0
        dxf = tmp_path / "receiving-bay-upper-door.dxf"
        api.save_part_render_data_dxf(render, dxf, verify_reopen=True)
        assert api.verify_saved_part_render_data_dxf(render, dxf).ok
        assert {"CUTTING", "BEND"} <= {
            entity.dxf.layer for entity in ezdxf.readfile(dxf).modelspace()
        }
    assert restored == before
