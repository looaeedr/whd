"""#2517 FinalScene and manufacture cannot disagree after live Family read failures."""
from __future__ import annotations

from copy import deepcopy
import inspect
from types import SimpleNamespace

import pytest

import phase6_manufacturing_adapter as adapter


class OperatorVar:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


class UnreadableOperatorVar:
    def get(self):
        raise RuntimeError("Tk control destroyed")


def _app(control=None, *, snapshot=None, initial="受電箱"):
    original = snapshot or {
        "model": "金庫型", "w": 800, "h": 1600, "d": 350, "t": 2,
    }
    workspace = SimpleNamespace(
        active_part="door",
        features_for=lambda _: (),
        face_features_for=lambda _: {},
        box_body_structure_state=lambda: {},
    )
    return SimpleNamespace(
        _phase6_input_snapshot=deepcopy(original),
        _settings_values={"model": "受電箱", "w": 777},
        _phase6_box_whd={},
        _phase6_baseline_initial_model=initial,
        baseline_model_var=control,
        state=SimpleNamespace(profiles={}, profiles_vault={}),
        designer_workspace=workspace,
        _phase6_endcap_fw_state={},
        _phase6_endcap_bottom_wrap_state={},
        _phase6_corner_state={},
    )


@pytest.mark.parametrize("control,expected", (
    (OperatorVar("金庫型"), "金庫型"),
    (OperatorVar("受電箱"), "受電箱"),
    (OperatorVar(""), "金庫型"),
    (OperatorVar(None), "金庫型"),
    (None, "金庫型"),
))
def test_gui_final_scene_and_immutable_request_resolve_identical_actual_family(
    control, expected,
):
    app = _app(control)
    before = deepcopy(app._phase6_input_snapshot)
    scene = adapter.build_scene_payload_for_app(app, "door")
    actual = adapter._cabinet_model(app, app._phase6_input_snapshot)
    assert actual == expected
    assert scene["model"] == actual
    assert app._phase6_input_snapshot == before
    # A stale settings model must not replace a saved source when live control
    # is blank, and cannot override an explicitly selected live Family.


def test_blank_legacy_unsaved_source_uses_initial_family_without_fabricating_geometry():
    app = _app(OperatorVar(""), snapshot={"w": 800, "h": 1600, "d": 350, "t": 2})
    source = deepcopy(app._phase6_input_snapshot)
    assert adapter._cabinet_model(app, source) == "受電箱"
    scene = adapter.build_scene_payload_for_app(app, "door")
    assert scene["model"] == "受電箱"
    assert source == app._phase6_input_snapshot


def test_saved_cabinet_type_identity_is_not_silently_overridden_by_stale_global_settings():
    app = _app(
        OperatorVar(""),
        snapshot={"cabinet_type": "receiving", "w": 800,
                  "h": 1600, "d": 350, "t": 2},
        initial="金庫型",
    )
    scene = adapter.build_scene_payload_for_app(app, "door")
    assert scene["model"] == "receiving"
    assert adapter._cabinet_model(app, app._phase6_input_snapshot) == "receiving"


@pytest.mark.parametrize("part_key", ("door", "head", "tail", "box_body"))
def test_unreadable_present_tk_family_control_never_creates_stale_manufacturing_scene(
    part_key,
):
    app = _app(UnreadableOperatorVar())
    before = deepcopy(app._phase6_input_snapshot)
    with pytest.raises(
        ValueError, match="MANUFACTURING_OPERATOR_SOURCE_READ_FAILED:baseline_model_var",
    ):
        adapter.build_scene_payload_for_app(app, part_key)
    with pytest.raises(
        ValueError, match="MANUFACTURING_OPERATOR_SOURCE_READ_FAILED:baseline_model_var",
    ):
        adapter._cabinet_model(app, app._phase6_input_snapshot)
    assert app._phase6_input_snapshot == before


def test_real_adapter_route_reuses_strict_model_reader_not_gui_silent_fallback():
    src = inspect.getsource(adapter.build_scene_payload_for_app)
    assert "_cabinet_model(" in src
    assert "_safe_var_get(" not in src
    model = inspect.getsource(adapter._cabinet_model)
    assert "_manufacturing_operator_var_get(" in model
    assert "snapshot.get(\"model\")" in model
