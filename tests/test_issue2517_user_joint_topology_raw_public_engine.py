# -*- coding: utf-8 -*-
"""#2517 USER_ADDED AssemblyJoint source topology is public Engine-owned."""
from copy import deepcopy
import inspect
import json
from types import SimpleNamespace

import pytest

import fold_designer_bridge as gui
from ae_engine import manufacturing_api as api
from ae_engine import assembly_joint as owner
from ae_engine.certified_relief_formula_io import (
    normalize_operator_relief_topology_levels as canonical_levels,
)


def _source():
    return {"existing_parts": ["box_body", "head", "tail"],
            "assembly_type": "INSERT_OVERLAY"}


def _kwargs():
    return {"subject_part": "head", "target_part": "box_body",
            "relation": "WRAP", "subject_region": "rear_edge",
            "target_region": "rear_mating", "clearance_policy": "ZERO"}


class Var:
    def __init__(self, value):
        self.value = value
        self.writes = []
    def get(self):
        return self.value
    def set(self, value):
        self.writes.append(value)


def _ui(raw):
    return SimpleNamespace(
        _phase6_input_snapshot=_source(),
        relief_joint_subject_var=Var("head"),
        relief_joint_target_var=Var("box_body"),
        relief_joint_relation_var=Var("WRAP"),
        relief_joint_subject_region_var=Var("rear_edge"),
        relief_joint_target_region_var=Var("rear_mating"),
        relief_joint_clearance_var=Var("ZERO"),
        relief_joint_topology_var=Var(raw),
        relief_joint_status_var=Var("ready"),
    )


def _route_real_joint(monkeypatch):
    refreshed = []
    monkeypatch.setattr(
        gui, "_phase6_registry_diagnostics",
        lambda _host: SimpleNamespace(
            route_joint_add=lambda callback, **kw: callback(**kw)
        ),
    )
    monkeypatch.setattr(
        gui, "_phase6_joint_form_refresh",
        lambda host: refreshed.append(host),
    )
    return refreshed


def test_public_engine_joint_and_registry_topology_owners_unchanged():
    assert api.commit_operator_user_assembly_joint is owner.add_user_assembly_joint
    assert api.normalize_operator_relief_topology_levels is canonical_levels


@pytest.mark.parametrize("raw,expected", [
    ("1", 1), ("2", 2), (1, 1), (2, 2),
    ("1.0", 1), ("2.0", 2), (1.0, 1), (2.0, 2),
])
def test_valid_topology_normalizes_in_canonical_engine_transaction(raw, expected):
    original = _source()
    before = deepcopy(original)
    operator = {"topology_levels": raw, "notes": {"operator": "source"}}
    saved = deepcopy(operator)
    staged, row = api.commit_operator_user_assembly_joint(
        original, **_kwargs(), solver_constraints=operator,
    )
    assert row["solver_constraints"]["topology_levels"] == expected
    assert row["solver_constraints"]["notes"] == {"operator": "source"}
    assert staged["assembly_joints"][-1] == row
    assert original == before and operator == saved
    operator["notes"]["operator"] = "changed"
    assert row["solver_constraints"]["notes"]["operator"] == "source"


@pytest.mark.parametrize("raw", [
    True, False, 0, 3, -1, "0", "3", "1.5", 1.5, 1.999,
    float("nan"), float("inf"), float("-inf"), "nan", "Infinity",
    "bad", None, [], {},
])
def test_invalid_topology_rejected_without_mutating_saved_joint(raw):
    original = _source()
    before = deepcopy(original)
    with pytest.raises((RuntimeError, ValueError, TypeError), match="topology_levels"):
        api.commit_operator_user_assembly_joint(
            original, **_kwargs(),
            solver_constraints={"topology_levels": raw},
        )
    assert original == before


@pytest.mark.parametrize("raw", [
    [], [("topology_levels", 1)], (), 42, True, False, "1", "",
])
def test_non_mapping_constraint_source_cannot_silently_default(raw):
    source = _source()
    previous = deepcopy(source)
    with pytest.raises(ValueError, match="solver_constraints"):
        api.commit_operator_user_assembly_joint(
            source, **_kwargs(), solver_constraints=raw,
        )
    assert source == previous


def test_absent_legacy_joint_solver_constraints_remain_supported():
    source = _source()
    previous = deepcopy(source)
    _staged, row = api.commit_operator_user_assembly_joint(source, **_kwargs())
    assert row["solver_constraints"] == {}
    assert source == previous


@pytest.mark.parametrize("raw,expected", [("1", 1), ("2", 2), ("1.0", 1)])
def test_actual_gui_form_forwards_raw_value_to_engine_and_survives_json_roundtrip(
    monkeypatch, raw, expected,
):
    host = _ui(raw)
    initial = deepcopy(host._phase6_input_snapshot)
    refreshed = _route_real_joint(monkeypatch)
    observed = []
    original = api.commit_operator_user_assembly_joint
    def tracking(*args, **kwargs):
        observed.append(deepcopy(kwargs["solver_constraints"]))
        return original(*args, **kwargs)
    monkeypatch.setattr(api, "commit_operator_user_assembly_joint", tracking)

    row = gui._phase6_joint_form_add(host)
    assert observed == [{"topology_levels": raw}]
    assert row["solver_constraints"]["topology_levels"] == expected
    assert row["source"] == "USER_ADDED"
    assert refreshed == [host]
    assert host.relief_joint_status_var.writes[-1].endswith("已新增接合規則")
    assert initial == _source()
    disk = json.loads(json.dumps(host._phase6_input_snapshot, ensure_ascii=False))
    reloaded = owner.migrate_legacy_snapshot_joints(disk)
    matched = [item for item in reloaded["assembly_joints"]
               if item["joint_id"] == row["joint_id"]]
    assert len(matched) == 1
    assert matched[0]["solver_constraints"]["topology_levels"] == expected


@pytest.mark.parametrize("raw", [
    True, False, "1.5", 1.5, "3", 0, "nan", None,
])
def test_gui_invalid_joint_stage_never_mutates_snapshot_or_refreshes(
    monkeypatch, raw,
):
    host = _ui(raw)
    initial = deepcopy(host._phase6_input_snapshot)
    refreshed = _route_real_joint(monkeypatch)
    seen = []
    original = api.commit_operator_user_assembly_joint
    def tracking(*args, **kwargs):
        seen.append(deepcopy(kwargs["solver_constraints"]))
        return original(*args, **kwargs)
    monkeypatch.setattr(api, "commit_operator_user_assembly_joint", tracking)

    assert gui._phase6_joint_form_add(host) is None
    assert seen == [{"topology_levels": raw}]
    assert host._phase6_input_snapshot == initial
    assert refreshed == []
    assert "新增失敗：" in host.relief_joint_status_var.writes[-1]


def test_gui_does_not_cast_joint_topology_before_engine_source_validation():
    form = inspect.getsource(gui._phase6_joint_form_add)
    assert '"topology_levels": self.relief_joint_topology_var.get()' in form
    assert "int(self.relief_joint_topology_var.get())" not in form
    assert "manufacturing_api.commit_operator_user_assembly_joint(" in (
        inspect.getsource(gui._phase6_add_user_joint)
    )
