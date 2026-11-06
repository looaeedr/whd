# -*- coding: utf-8 -*-
"""#2517: direct physical inner-door Confirm All has one public Engine owner."""
from copy import deepcopy
import inspect

import pytest

import ae_engine
from ae_engine import manufacturing_api
from ae_engine.receiving_inner_door_candidates import validate_door_config
from gui_modules.application import receiving_inner_door_hole_editor as editor
from tests.test_issue1500_receiving_candidate_main_save import _source_with_saved_version


def _source():
    _, staged, part_key, _ = _source_with_saved_version()
    return staged, part_key, staged["features"][part_key]


def test_public_engine_request_matches_existing_candidate_validator_and_preserves_inputs():
    staged, part_key, features = _source()
    before_staged, before_features = deepcopy(staged), deepcopy(features)
    prepared = manufacturing_api.prepare_receiving_inner_door_physical_confirm(
        staged, part_key, features,
    )
    expected = validate_door_config(staged)
    expected["features"][part_key] = deepcopy(list(features))
    assert prepared == validate_door_config(expected)
    assert staged == before_staged and features == before_features
    assert prepared is not staged and prepared["features"] is not staged["features"]
    assert ae_engine.prepare_receiving_inner_door_physical_confirm is (
        manufacturing_api.prepare_receiving_inner_door_physical_confirm
    )


@pytest.mark.parametrize("bad_key", ("door", "box_body", "inner_door:upper:top_frame", None))
def test_public_engine_rejects_non_inner_physical_parts_before_candidate_write(bad_key):
    staged, _, features = _source()
    before = deepcopy(staged)
    with pytest.raises(ValueError, match="實體內門門板"):
        manufacturing_api.prepare_receiving_inner_door_physical_confirm(
            staged, bad_key, features,
        )
    assert staged == before


def test_invalid_staged_and_final_features_fail_closed_without_input_mutation():
    staged, part_key, features = _source()
    broken = deepcopy(staged)
    broken["layers"] = True
    before = deepcopy(broken)
    with pytest.raises(ValueError):
        manufacturing_api.prepare_receiving_inner_door_physical_confirm(
            broken, part_key, features,
        )
    assert broken == before
    with pytest.raises((ValueError, TypeError)):
        manufacturing_api.prepare_receiving_inner_door_physical_confirm(
            staged, part_key, object(),
        )


def test_real_gui_direct_confirm_delegates_setting_and_identity_to_public_engine():
    source = inspect.getsource(editor.open_inner_door_hole_editor)
    assert "manufacturing_api.prepare_receiving_inner_door_physical_confirm(" in source
    assert "from ae_engine.receiving_inner_door_candidates import validate_door_config" not in source
    assert 'config.setdefault("features"' not in source
    assert "adapter.apply_inner_door_candidate_to_bays(" in source
    assert source.index("manufacturing_api.prepare_receiving_inner_door_physical_confirm(") < source.index("adapter.apply_inner_door_candidate_to_bays(")
