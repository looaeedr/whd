# -*- coding: utf-8 -*-
"""#2517: Fold Designer Single/Candidate Confirm delegates source ownership."""
from copy import deepcopy
import inspect

import pytest

import ae_engine
from ae_engine import manufacturing_api
from ae_engine.receiving_inner_door_candidates import validate_door_config
from gui_modules.application import fold_designer_composition_receiving as composition
from tests.test_issue1500_receiving_candidate_main_save import _source_with_saved_version


def _source():
    _, staged, part_key, _ = _source_with_saved_version()
    return staged, part_key, staged["features"][part_key]


def test_embedded_staged_settings_use_identical_public_engine_validation():
    staged, _, _ = _source()
    original = deepcopy(staged)
    assert manufacturing_api.validate_receiving_inner_door_config(staged) == validate_door_config(staged)
    assert ae_engine.validate_receiving_inner_door_config is manufacturing_api.validate_receiving_inner_door_config
    assert staged == original
    bad = deepcopy(staged)
    bad["layers"] = True
    with pytest.raises(ValueError):
        manufacturing_api.validate_receiving_inner_door_config(bad)
    assert bad["layers"] is True


def test_single_and_candidate_source_prepare_share_existing_public_owner():
    staged, part_key, features = _source()
    before = deepcopy(staged)
    prepared = manufacturing_api.prepare_receiving_inner_door_physical_confirm(
        staged, part_key, features,
    )
    expected = validate_door_config(staged)
    expected["features"][part_key] = deepcopy(list(features))
    assert prepared == validate_door_config(expected)
    assert staged == before and prepared is not staged
    with pytest.raises(ValueError, match="實體內門門板"):
        manufacturing_api.prepare_receiving_inner_door_physical_confirm(
            staged, "inner_door:upper:left_frame", features,
        )


def test_real_gui_staged_and_single_candidate_confirm_use_public_engine_only():
    source = inspect.getsource(composition)
    inner_edit = source.split("    def inner_edit(", 1)[1].split("    def ", 1)[0]
    assert "manufacturing_api.validate_receiving_inner_door_config(staged)" in inner_edit
    assert "from ae_engine.receiving_inner_door_candidates import validate_door_config" not in inner_edit
    confirm = source.split("    def launch_inner_editor(", 1)[1].split("    def edit_single_inner_door(", 1)[0]
    assert "from ae_engine.receiving_inner_door_candidates import validate_door_config" not in confirm
    # A local facade import in the Quantity branch shadows the module-level
    # binding and breaks Single/Candidate Confirm with UnboundLocalError.
    assert "from ae_engine import manufacturing_api" not in confirm
    assert "validate_door_config(" not in confirm
    assert 'setdefault("features"' not in confirm
    assert confirm.count("manufacturing_api.prepare_receiving_inner_door_physical_confirm(") == 2
    assert 'adapter.apply_inner_door_candidate_to_bays(' in confirm
    assert "create_inner_candidate(" in confirm and "update_inner_candidate(" in confirm
    assert "manufacturing_api.preview_quantity_inner_door_confirm(" in confirm
