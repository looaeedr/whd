from phase6_settings_center import settings_for_context
from phase6_settings_panel import DEFAULT_HIDDEN_KEYS_BY_CONTEXT, partition_setting_specs


def test_right_settings_panel_excludes_fold_values_already_editable_on_left():
    expected = {
        'box_body': {'zl1', 'zl2', 'zr1', 'zr2'},
        'head': {'yl1', 'yr1', 'ytop1', 'ybottom1'},
        'tail': {'yl1', 'yr1', 'ytop1', 'ybottom1'},
        'door': {'door_fold_l', 'door_fold_r', 'door_fold_t', 'door_fold_b'},
        'base_plate': {
            'base_plate_shrink_top', 'base_plate_shrink_bottom',
            'base_plate_shrink_left', 'base_plate_shrink_right',
        },
        'indicator_box': {'indicator_box_fold'},
        'indicator_door': {'indicator_door_fold'},
    }
    for context, keys in expected.items():
        assert keys.issubset(DEFAULT_HIDDEN_KEYS_BY_CONTEXT[context])
        groups = partition_setting_specs(
            context,
            settings_for_context(context),
            hidden_keys=DEFAULT_HIDDEN_KEYS_BY_CONTEXT[context],
        )
        visible = {
            spec.key
            for group in (groups.normal, groups.advanced, groups.baseline, groups.compatibility_hidden)
            for spec in group
        }
        assert not (keys & visible), (context, keys & visible)


def test_base_plate_bend_remains_in_parameter_settings_panel():
    groups = partition_setting_specs(
        "base_plate",
        settings_for_context("base_plate"),
        hidden_keys=DEFAULT_HIDDEN_KEYS_BY_CONTEXT["base_plate"],
    )
    visible = {
        spec.key
        for group in (groups.normal, groups.advanced, groups.baseline, groups.compatibility_hidden)
        for spec in group
    }
    assert "base_plate_bend" in visible
    assert "base_plate_bend" not in DEFAULT_HIDDEN_KEYS_BY_CONTEXT["base_plate"]
