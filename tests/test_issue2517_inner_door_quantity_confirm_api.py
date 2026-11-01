# -*- coding: utf-8 -*-
"""#2517: both Receiving inner-door Confirm All paths use one Engine precommit."""
from copy import deepcopy
import inspect

import pytest

from ae_engine import manufacturing_api
from ae_engine.receiving_nfb_csv_committed_config import (
    committed_csv_nfb_config, preview_quantity_nfb_submission,
)
from ae_engine.receiving_quantity_box import update_common_box
from phase6_project_file import _decode, _encode
from phase6_quantity_model import QuantityModel
from phase6_receiving_modes import fresh_receiving_mode
from tests.test_issue1500_receiving_candidate_main_save import _source_with_saved_version
from gui_modules.application.receiving_inner_door_hole_editor import (
    open_inner_door_hole_editor,
)


def _inputs():
    _, staged, part_key, _ = _source_with_saved_version()
    snapshot = fresh_receiving_mode(
        "quantity", {"w": 800, "h": 1600, "d": 350},
    )
    quantity = QuantityModel()
    return snapshot, quantity, part_key, staged, staged["features"][part_key]


def test_headless_real_csv_precommit_matches_existing_family_and_quantity_owner():
    snapshot, quantity, part_key, staged, features = _inputs()
    original_snapshot, original_quantity = deepcopy(snapshot), quantity.snapshot()

    projected, typed = manufacturing_api.preview_quantity_inner_door_confirm(
        snapshot, quantity, part_key, features, staged,
    )
    expected_source = update_common_box(snapshot, {
        "inner_door_layers": staged["layers"],
        "inner_door_models": deepcopy(staged["models"]),
        **({"inner_door_layer_heights_mm": deepcopy(staged["layer_heights_mm"])}
           if staged.get("layer_heights_mm") is not None else {}),
    })
    expected_config = committed_csv_nfb_config(part_key, features, staged)
    assert typed == expected_config
    assert projected == preview_quantity_nfb_submission(
        expected_source, quantity, expected_config,
    )
    assert snapshot == original_snapshot and quantity.snapshot() == original_quantity
    assert projected["receiving_layout"]["sets"][0]["bays"][0][
        "nfb_config_submitted"
    ] is True
    assert all(hole["manual_x_state"] == "UNVERIFIED_BASIS"
               for hole in typed["holes"])
    assert _decode(_encode(projected)) == projected


def test_invalid_csv_holes_and_family_box_leave_live_source_unchanged():
    snapshot, quantity, part_key, staged, features = _inputs()
    original_quantity = quantity.snapshot()
    original_snapshot = deepcopy(snapshot)
    with pytest.raises(ValueError, match="NFB_CSV_COMMIT_MISSING_CONFIRMED_HOLE"):
        manufacturing_api.preview_quantity_inner_door_confirm(
            snapshot, quantity, part_key, features[:-1], staged,
        )
    assert snapshot == original_snapshot and quantity.snapshot() == original_quantity

    broken = deepcopy(snapshot)
    broken["receiving_quantity_box"]["w"] = 0
    before = deepcopy(broken)
    with pytest.raises(ValueError, match="有限正數"):
        manufacturing_api.preview_quantity_inner_door_confirm(
            broken, quantity, part_key, features, staged,
        )
    assert broken == before and quantity.snapshot() == original_quantity


def test_native_only_confirmation_projects_settings_without_submitting_nfb():
    snapshot, quantity, part_key, staged, _ = _inputs()
    initial = quantity.snapshot()
    projected, typed = manufacturing_api.preview_quantity_inner_door_confirm(
        snapshot, quantity, part_key, (), staged,
        include_missing_heights=True,
    )
    assert typed is None
    assert projected["receiving_quantity_box"]["inner_door_layers"] == staged["layers"]
    assert projected["receiving_quantity_box"]["inner_door_models"] == staged["models"]
    assert quantity.snapshot() == initial
    assert not any(row.get("nfb_config_submitted")
                   for row in projected["quantity"]["versions"])


def test_gui_paths_delegate_precommit_to_public_api_without_local_csv_calculation():
    direct = inspect.getsource(open_inner_door_hole_editor)
    assert "manufacturing_api.preview_quantity_inner_door_confirm(" in direct
    assert "preview_quantity_nfb_submission(" not in direct
    assert "update_common_box(" not in direct

    from pathlib import Path
    gui = Path(__file__).resolve().parents[1] / (
        "gui_modules/application/fold_designer_composition_receiving.py"
    )
    src = gui.read_text(encoding="utf-8")
    start = src.index("def confirmed(actual_part, features, staged_config):")
    end = src.index('if mode == "single":', start)
    confirm = src[start:end]
    assert "manufacturing_api.preview_quantity_inner_door_confirm(" in confirm
    assert "preview_quantity_nfb_submission(" not in confirm
    assert "committed_csv_nfb_config(" not in confirm
    assert confirm.index("manufacturing_api.preview_quantity_inner_door_confirm(") < (
        confirm.index("quantity.set_version_nfb_config(")
    )
