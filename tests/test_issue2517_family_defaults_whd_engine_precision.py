"""#2517: Engine owns Family preset W/H/D validity and GUI displays exact values."""
from copy import deepcopy
from types import SimpleNamespace
import inspect

import pytest

from ae_engine import manufacturing_api as api
import gui_modules.application.fold_designer_composition_shell_settings as shell


def _engine_plan(factory_defaults):
    source = {
        "model": "受電箱", "w": 800.0, "h": 1600.0, "d": 350.0,
        "t": 2.0, "fw": 25.0,
        "factory_defaults": deepcopy(factory_defaults),
    }
    before = deepcopy(source)
    result = api.plan_cabinet_family_model_transition(
        "金庫型", "受電箱",
        new_editable=False, old_editable=False,
        input_snapshot=source,
        settings_values={"w": 800.0, "h": 1600.0, "d": 350.0, "t": 2.0},
        corner_state={}, corner_pair_same={}, endcap_bottom_wrap_state={},
        assembly_type="INSERT_OVERLAY",
        available_parts=("box_body", "head", "tail"),
    )
    assert source == before
    return result


def test_family_plan_preserves_fractional_outside_defaults_without_source_mutation():
    result = _engine_plan({
        "w": "820.25", "h": 1600.5, "d": "360.75", "t": 2.0, "fw": 25.0,
    })
    assert tuple(result.transition.defaults[key] for key in ("w", "h", "d")) == (
        820.25, 1600.5, 360.75,
    )
    assert tuple(result.input_snapshot[key] for key in ("w", "h", "d")) == (
        820.25, 1600.5, 360.75,
    )


@pytest.mark.parametrize("axis", ("w", "h", "d"))
@pytest.mark.parametrize("bad", (True, False, None, 0, -1, "nan", "inf", "bad"))
def test_invalid_family_physical_preset_rejected_before_plan_commit(axis, bad):
    defaults = {"w": 820.25, "h": 1600.5, "d": 360.75, "t": 2, "fw": 25}
    defaults[axis] = bad
    with pytest.raises((ValueError, TypeError)):
        _engine_plan(defaults)


class Var:
    def __init__(self, value):
        self.value = str(value)
        self.calls = []
    def get(self):
        return self.value
    def set(self, value):
        self.value = str(value)
        self.calls.append(self.value)


def _gui_host(defaults, *, old=(500, 600, 250)):
    app = SimpleNamespace(
        state=SimpleNamespace(w=old[0], h=old[1], d=old[2]),
        v_w=Var(old[0]), v_h=Var(old[1]), v_d=Var(old[2]),
        _phase6_settings_guard=False,
        left_global_vars={}, setting_vars={},
    )
    legacy = SimpleNamespace(
        get_int=lambda *_: (_ for _ in ()).throw(AssertionError(
            "legacy integer readback cannot touch physical W/H/D"
        )),
        tk=SimpleNamespace(BooleanVar=type("BooleanVar", (), {})),
    )
    controller = SimpleNamespace(
        app=app,
        _required=lambda _ns, name: {
            "_setting_number_text": str,
            "original": legacy,
        }[name],
    )
    plan = SimpleNamespace(
        defaults=deepcopy(defaults),
        assembly_type="INSERT_OVERLAY",
        remember_non_receiving_structure=None,
    )
    return controller, app, plan


def test_gui_family_model_projection_displays_engine_exact_fractional_dimensions():
    controller, app, plan = _gui_host({
        "w": 820.25, "h": "1600.5", "d": 360.75,
    })
    shell.settings_application_project_ui_values(
        controller, object(), {}, baseline_transition=plan,
        baseline_stage="commit",
        new_model="金庫型", old_model="金庫型",
    )
    assert tuple(getattr(app.state, axis) for axis in ("w", "h", "d")) == (
        820.25, 1600.5, 360.75,
    )
    assert tuple(float(v.get()) for v in (app.v_w, app.v_h, app.v_d)) == (
        820.25, 1600.5, 360.75,
    )
    assert app._phase6_last_w == 820.25
    assert app._phase6_last_d == 360.75
    assert all(len(v.calls) == 1 for v in (app.v_w, app.v_h, app.v_d))
    source = inspect.getsource(shell.settings_application_project_ui_values)
    assert "normalize_operator_source_dimension(" in source
    assert "original.get_int(defaults[key])" not in source


def test_gui_invalid_late_default_fails_before_any_partial_widget_or_state_change():
    controller, app, plan = _gui_host({"w": 820.25, "h": "nan", "d": 360.75})
    before = (app.state.w, app.state.h, app.state.d)
    with pytest.raises((ValueError, TypeError)):
        shell.settings_application_project_ui_values(
            controller, object(), {}, baseline_transition=plan,
            baseline_stage="commit", new_model="金庫型", old_model="金庫型",
        )
    assert (app.state.w, app.state.h, app.state.d) == before
    assert not (app.v_w.calls or app.v_h.calls or app.v_d.calls)
    assert app._phase6_settings_guard is False


def test_gui_partial_family_defaults_preserve_unchanged_axes():
    controller, app, plan = _gui_host({"w": "820.25"}, old=(500, 600, 250))
    shell.settings_application_project_ui_values(
        controller, object(), {}, baseline_transition=plan,
        baseline_stage="commit", new_model="金庫型", old_model="金庫型",
    )
    assert (app.state.w, app.state.h, app.state.d) == (820.25, 600, 250)
