"""#2517: selected Receiving Bay input authority is Engine, never GUI overlay."""
from copy import deepcopy
from pathlib import Path

import pytest

from ae_engine import manufacturing_api as api
from ae_engine.receiving_bay_preview_source import (
    ReceivingBayPreviewOperatorInputs,
    project_receiving_bay_preview_operator_inputs as owner,
)
from ae_engine.part_dimension_projection import project_part_dimensions
from ae_engine.receiving_layout import (
    new_receiving_layout, resize_receiving_bays, update_receiving_bay,
    project_receiving_bay_legacy_aliases, RECEIVING_RUNTIME_SELECTION_KEY,
)


def _source():
    layout = resize_receiving_bays(
        new_receiving_layout(width=800, height=1600, depth=350),
        set_index=0, bay_count=4,
    )
    layout = update_receiving_bay(
        layout, set_index=0, bay_index=1, width=900, height=1700, depth=400,
    )
    layout = update_receiving_bay(
        layout, set_index=0, bay_index=1,
        door_state={"multi_door_enabled": False,
                    "door_layout_columns": [[900, [1100, 600]]]},
    )
    return {"model": "受電箱", "active_mode": "set_bay",
            "t": 2, "fw": 29, "receiving_layout": layout,
            "w": 800, "h": 1600, "d": 350}


@pytest.mark.parametrize("bay,whd", [
    (0, (800, 1600, 350)), (1, (900, 1700, 400)),
    (2, (800, 1600, 350)), (3, (800, 1600, 350)),
])
def test_four_real_bays_preserve_source_dimensions_and_projection(bay, whd):
    source = _source()
    settings = {"w": 800, "h": 1600, "d": 350, "t": 3, "fw": 29}
    before = deepcopy((source, settings))
    projected = api.project_receiving_bay_preview_operator_inputs(
        source, settings, set_index=0, bay_index=bay,
    )
    assert isinstance(projected, ReceivingBayPreviewOperatorInputs)
    assert projected == owner(source, settings, set_index=0, bay_index=bay)
    assert tuple(projected.snapshot[k] for k in ("w", "h", "d")) == whd
    assert tuple(projected.settings_values[k] for k in ("w", "h", "d")) == whd
    assert projected.snapshot["part_dimensions"] == project_part_dimensions(projected.snapshot)
    assert projected.snapshot["t"] == 3
    assert (source, settings) == before
    assert projected.snapshot["receiving_layout"] == source["receiving_layout"]
    assert projected.snapshot[RECEIVING_RUNTIME_SELECTION_KEY]["bay_index"] == bay


def test_stale_global_door_layout_and_nfb_must_not_override_committed_bay():
    source = _source()
    settings = {"w": 800, "h": 1600, "d": 350, "t": 2, "fw": 29,
                "multi_door_enabled": True,
                "door_layout_columns": [[800, [1100, 500]]],
                "inner_doors": {"stale": True},
                "nfb_config_submitted": True,
                "nfb_config": {"stale": "unverified"},
                RECEIVING_RUNTIME_SELECTION_KEY: {"bay_index": 0},
                "receiving_layout": {"stale": "old-layout"}}
    result = api.project_receiving_bay_preview_operator_inputs(
        source, settings, set_index=0, bay_index=1,
    )
    assert result.snapshot["door_layout_columns"] == [[900, [1100, 600]]]
    assert result.snapshot["multi_door_enabled"] is False
    assert "inner_doors" not in result.snapshot
    assert "nfb_config_submitted" not in result.snapshot
    assert "nfb_config" not in result.snapshot
    assert result.snapshot["receiving_layout"] == source["receiving_layout"]
    assert result.snapshot[RECEIVING_RUNTIME_SELECTION_KEY]["bay_index"] == 1
    assert result.settings_values["w"] == 900


def test_candidate_receiving_layout_changes_only_projection_not_source():
    source = _source()
    candidate = update_receiving_bay(
        source["receiving_layout"], set_index=0, bay_index=2,
        width=970, height=1850, depth=425,
    )
    working = {**source, "receiving_layout": candidate}
    before = deepcopy((source, candidate))
    got = api.project_receiving_bay_preview_operator_inputs(
        working, {"t": 2}, set_index=0, bay_index=2,
    )
    assert tuple(got.snapshot[x] for x in ("w", "h", "d")) == (970, 1850, 425)
    assert got.snapshot["part_dimensions"]["box_body"]["width"] == 970
    assert (source, candidate) == before


@pytest.mark.parametrize("bad", [None, [], "invalid", 0])
def test_invalid_operator_source_fails_closed(bad):
    with pytest.raises(TypeError, match="SOURCE_MAPPING_REQUIRED"):
        api.project_receiving_bay_preview_operator_inputs(
            bad, {}, set_index=0, bay_index=1,
        )


def test_gui_uses_one_public_source_projection_no_local_bay_key_filter():
    root = Path(__file__).resolve().parents[1]
    body = (root / "gui_modules/application/fold_designer_composition_receiving.py"
           ).read_text(encoding="utf-8").split(
        "def receiving_bay_preview_request(", 1,
    )[1].split("def receiving_layer_preview_payload(", 1)[0]
    assert "manufacturing_api.project_receiving_bay_preview_operator_inputs(" in body
    assert "RECEIVING_DOOR_STATE_KEYS" not in body
    assert "bay_authoritative" not in body
    assert "snapshot.update({" not in body
    assert 'snapshot["part_dimensions"] = project_part_dimensions(snapshot)' not in body
    owner_text = (root / "ae_engine/receiving_bay_preview_source.py"
                  ).read_text(encoding="utf-8")
    assert "from gui_modules" not in owner_text
    assert "from phase6_" not in owner_text
