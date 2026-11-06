"""#2517 Receiving explicit BasePlate source survives operator aliases and Save/Reload."""
from copy import deepcopy
from types import SimpleNamespace
import inspect

import pytest

from ae_engine import manufacturing_api as api
from ae_engine.cabinet_types import policy as family_policy
from gui_modules.application import fold_designer_snapshot_projection as gui
from tests.test_issue2517_receiving_base_plate_settings_engine_api import CENTER
import phase6_project_file as project


@pytest.mark.parametrize("model", ("受電箱", "RECEIVING", "receiving", "ReCeIvInG"))
def test_authoritative_snapshot_projection_detaches_original_receiving_baseplate(model):
    current = {"model": model, "w": 800.0, "h": 1600.0, "t": 2.0}
    stored = {"model": "受電箱", "receiving_base_plate": deepcopy(CENTER)}
    before = deepcopy((current, stored))
    assert family_policy.canonical_family_name(current) == "受電箱"
    projected = api.project_operator_receiving_base_plate_snapshot_source(current, stored)
    assert projected == {"receiving_base_plate": CENTER}
    assert projected["receiving_base_plate"] is not stored["receiving_base_plate"]
    assert (current, stored) == before
    projected["receiving_base_plate"]["height"] = 100
    assert stored["receiving_base_plate"]["height"] == CENTER["height"]
    assert api.validate_receiving_base_plate_settings(
        input_snapshot=current, settings_values={}, config=CENTER,
    ) == CENTER


@pytest.mark.parametrize("model", ("受電箱", "RECEIVING", "receiving", "ReCeIvInG"))
def test_committed_explicit_physical_plate_survives_real_project_save_reload(tmp_path, model):
    current = {"model": model, "w": 800.0, "h": 1600.0, "d": 350.0, "t": 2.0}
    selection = api.project_operator_receiving_base_plate_snapshot_source(
        current, {"receiving_base_plate": CENTER},
    )
    original = {**current, **selection}
    target = project.write_project(tmp_path / "receiving-plate.p6fold", {
        "schema": project.PROJECT_SCHEMA, "snapshot": original,
    })
    restored = project.read_project(target)["snapshot"]
    assert restored["receiving_base_plate"] == CENTER
    assert family_policy.canonical_family_name(restored) == "受電箱"
    assert original["receiving_base_plate"] == CENTER


def test_missing_reset_invalid_or_wrong_family_never_forges_plate_source():
    receiving = {"model": "receiving"}
    assert api.project_operator_receiving_base_plate_snapshot_source(receiving, {}) == {}
    assert api.project_operator_receiving_base_plate_snapshot_source(
        receiving, {"receiving_base_plate": None},
    ) == {"receiving_base_plate": None}
    assert api.project_operator_receiving_base_plate_snapshot_source(
        {"model": "金庫型"}, {"receiving_base_plate": CENTER},
    ) == {}
    with pytest.raises(ValueError, match="SNAPSHOT_SOURCE_INVALID"):
        api.project_operator_receiving_base_plate_snapshot_source(receiving, False)
    with pytest.raises(ValueError, match="SNAPSHOT_SOURCE_INVALID"):
        api.project_operator_receiving_base_plate_snapshot_source(
            receiving, {"receiving_base_plate": ["invalid"]},
        )
    with pytest.raises(ValueError, match="只有受電箱"):
        api.validate_receiving_base_plate_settings(
            input_snapshot={"model": "金庫型"}, settings_values={}, config=CENTER,
        )


class Var:
    def __init__(self, value):
        self.value = value
    def get(self):
        return self.value


class SnapshotHost:
    """Exercise the actual GUI snapshot shell, not a synthetic engine selection."""
    def __init__(self, model, stored):
        self.baseline_var = Var(model)
        self.project_controller = SimpleNamespace(project_path="")
        self.workspace_controller = SimpleNamespace(active_part="box_body")
        self.fold_designer_app = SimpleNamespace(_phase6_input_snapshot=stored)
        self._phase6_input_snapshot = {}
        self._current_box_assembly_type = lambda: "INSERT_OVERLAY"
        self.endcap_fw_state = {}
        self.door_layout_scope = "main"
        self.manual_corner_pair_same = {}
        self._collect_main_setting_values = lambda: {}
        self._serialize_manual_corner_state = lambda: {}
        self._baseline_model_choices = lambda: ("金庫型", "受電箱")
    def __getattr__(self, name):
        if name.endswith("_var"):
            return Var({"w_var": 800.0, "h_var": 1600.0,
                        "d_var": 350.0, "t_var": 2.0,
                        "fw_z_var": 29.0}.get(name, 2.0))
        raise AttributeError(name)


@pytest.mark.parametrize("model", ("受電箱", "RECEIVING", "receiving", "ReCeIvInG"))
def test_actual_gui_snapshot_routes_explicit_plate_via_public_engine(model, monkeypatch):
    source = {"model": model, "receiving_base_plate": deepcopy(CENTER)}
    host = SnapshotHost(model, source)
    routed = []
    real = api.project_operator_receiving_base_plate_snapshot_source
    def observe(snapshot, stored):
        routed.append(snapshot["model"])
        return real(snapshot, stored)
    monkeypatch.setattr(api, "project_operator_receiving_base_plate_snapshot_source", observe)
    actual = gui._snapshot_base_state(host)
    assert routed == [model]
    assert actual["receiving_base_plate"] == CENTER
    assert actual["receiving_base_plate"] is not source["receiving_base_plate"]
    assert source["receiving_base_plate"] == CENTER


def test_gui_source_only_passes_inputs_not_family_manufacturing_rules():
    src = inspect.getsource(gui._snapshot_base_state)
    assert "manufacturing_api.project_operator_receiving_base_plate_snapshot_source(" in src
    assert 'snapshot["model"] in {"受電箱", "RECEIVING"}' not in src
