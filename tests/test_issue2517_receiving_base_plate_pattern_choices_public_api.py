# -*- coding: utf-8 -*-
"""#2517: Receiving physical BasePlate operator choices come from public Engine."""
from copy import deepcopy
from inspect import getsource

import ae_engine
from ae_engine import manufacturing_api as api
from ae_engine import sheetmetal_part_adapters as owner
from phase6_settings_panel_owned_render import Phase6SettingsPanelOwnedRenderMixin
from tests.test_issue2517_receiving_base_plate_settings_engine_api import (
    CENTER, _snapshot,
)


def test_public_engine_pattern_catalog_is_exact_builder_owner():
    assert (api.project_operator_receiving_base_plate_pattern_choices
            is owner.project_operator_receiving_base_plate_pattern_choices)
    assert (ae_engine.project_operator_receiving_base_plate_pattern_choices
            is owner.project_operator_receiving_base_plate_pattern_choices)
    assert "project_operator_receiving_base_plate_pattern_choices" in ae_engine.__all__
    choices = api.project_operator_receiving_base_plate_pattern_choices()
    assert isinstance(choices, tuple)
    assert choices == (
        ("left", owner.RECEIVING_BASE_PATTERN_LEFT),
        ("center", owner.RECEIVING_BASE_PATTERN_CENTER),
        ("right", owner.RECEIVING_BASE_PATTERN_RIGHT),
    )
    assert {pattern for _, pattern in choices} == owner.RECEIVING_BASE_PATTERNS
    assert len({role for role, _ in choices}) == len(choices) == 3


def test_selected_pattern_is_same_source_accepted_by_actual_engine_validator():
    snapshot = _snapshot()
    config = deepcopy(CENTER)
    before = deepcopy((snapshot, config))
    choices = dict(api.project_operator_receiving_base_plate_pattern_choices())
    config["pattern"] = choices["center"]
    accepted = api.validate_receiving_base_plate_settings(
        input_snapshot=snapshot, settings_values={}, config=config,
    )
    assert accepted == config
    assert accepted is not config
    assert (snapshot, config) == before


def test_gui_has_only_operator_labels_not_internal_physical_pattern_constants():
    source = getsource(Phase6SettingsPanelOwnedRenderMixin._render_owned_receiving_base_plate)
    assert "manufacturing_api.project_operator_receiving_base_plate_pattern_choices()" in source
    assert "from ae_engine.sheetmetal_part_adapters import" not in source
    assert "RECEIVING_BASE_PATTERN_" not in source
    for role in ("left", "center", "right"):
        assert f'"{role}"' in source
    assert "self._receiving_base_plate_commit(payload)" in source
