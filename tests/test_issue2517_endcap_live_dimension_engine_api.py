"""#2517: EndCap live Fold/outer W-D synchronization is Engine-owned."""
from __future__ import annotations

import inspect
from types import SimpleNamespace

import pytest

from ae_engine import (
    endcap_derived_core_lengths,
    manufacturing_api,
    reconcile_endcap_live_outside_dimensions,
)
import fold_designer_bridge as bridge


class Var:
    def __init__(self, value):
        self.value = str(value)

    def get(self):
        return self.value

    def set(self, value):
        self.value = str(value)


def _snapshot(model):
    return {"model": model, "w": 800, "h": 1600, "d": 350, "t": 2, "fw": 29}


@pytest.mark.parametrize(
    "family,depth_core", [("受電箱", 346), ("金庫型", 344)]
)
def test_engine_core_roundtrip_matches_real_family_xy_fold(family, depth_core):
    snapshot = _snapshot(family)
    lengths = endcap_derived_core_lengths(snapshot, 800, 350)
    assert lengths == {"endcap_w_core": 792, "endcap_d_core": depth_core}
    for key in ("head", "tail"):
        profiles = manufacturing_api.build_endcap_xy_fold_profiles(snapshot, part_key=key)
        assert next(row["len"] for row in profiles["X"] if row.get("phase6_key") == "endcap_w_core") == 792
        assert next(row["len"] for row in profiles["Y"] if row.get("phase6_key") == "endcap_d_core") == depth_core
        assert reconcile_endcap_live_outside_dimensions(
            snapshot, top_width=800, top_depth=350, previous_width=800,
            previous_depth=350, profiles=profiles
        ) == {"w": 800, "d": 350}


@pytest.mark.parametrize("family,expected_depth", [("受電箱", 355), ("金庫型", 355)])
def test_engine_reconciles_changed_fold_and_prioritizes_explicit_top(family, expected_depth):
    snapshot = _snapshot(family)
    profiles = manufacturing_api.build_endcap_xy_fold_profiles(snapshot, part_key="head")
    for axis, key in (("X", "endcap_w_core"), ("Y", "endcap_d_core")):
        next(row for row in profiles[axis] if row.get("phase6_key") == key)["len"] += 5
    assert reconcile_endcap_live_outside_dimensions(
        snapshot, top_width=800, top_depth=350, previous_width=800,
        previous_depth=350, profiles=profiles,
    ) == {"w": 805, "d": expected_depth}
    assert reconcile_endcap_live_outside_dimensions(
        snapshot, top_width=820, top_depth=370, previous_width=800,
        previous_depth=350, profiles=profiles,
    ) == {"w": 820, "d": 370}


def test_missing_material_core_fails_closed_to_prior_outside_values():
    assert reconcile_endcap_live_outside_dimensions(
        _snapshot("受電箱"), top_width=800, top_depth=350,
        previous_width=800, previous_depth=350,
        profiles={"X": [{"phase6_key": "endcap_w_flat", "len": 800}], "Y": []},
    ) == {"w": 800, "d": 350}


def test_bridge_sync_delegates_to_public_engine_and_preserves_gui_state(monkeypatch):
    calls = []
    def fake_engine(snapshot, **kw):
        calls.append((dict(snapshot), kw))
        return {"w": 805, "d": 355}
    monkeypatch.setattr(manufacturing_api, "reconcile_endcap_live_outside_dimensions", fake_engine)
    monkeypatch.setattr(bridge, "_propagate_endcap_derived_cores", lambda host, w, d: calls.append(("propagate", w, d)))
    snapshot = _snapshot("受電箱")
    host = SimpleNamespace(
        _phase6_input_snapshot=snapshot,
        _phase6_last_w=800, _phase6_last_d=350,
        _phase6_box_whd={"w": 800, "h": 1600, "d": 350},
        v_w=Var(800), v_h=Var(1600), v_d=Var(350),
        state=SimpleNamespace(profiles={"X": [], "Y": []}),
    )
    bridge._sync_active_endcap_and_global_whd(host)
    assert calls[0][1]["profiles"] is host.state.profiles
    assert calls[1] == ("propagate", 805, 355)
    assert (host.v_w.get(), host.v_d.get()) == ("805", "355")
    assert (snapshot["w"], snapshot["d"]) == (805, 355)
    assert host._phase6_box_whd == {"w": 805, "h": 1600, "d": 355}


def test_gui_only_commits_engine_derived_cores_to_existing_rows(monkeypatch):
    calls = []
    monkeypatch.setattr(manufacturing_api, "endcap_derived_core_lengths", lambda *args: calls.append(args) or {"endcap_w_core": 777, "endcap_d_core": 333})
    x = [{"phase6_key": "endcap_w_core", "len": 20}]
    y = [{"phase6_key": "endcap_d_core", "len": 20}]
    host = SimpleNamespace(
        _phase6_input_snapshot=_snapshot("金庫型"),
        _phase6_part_profiles={"head": {"X": x, "Y": y}},
        active_part_key="head",
        state=SimpleNamespace(profiles={"X": x, "Y": y}),
    )
    bridge._propagate_endcap_derived_cores(host, 800, 350)
    assert (x[0]["len"], y[0]["len"]) == (777, 333)
    assert len(calls) == 1
    assert reconcile_endcap_live_outside_dimensions is manufacturing_api.reconcile_endcap_live_outside_dimensions
    assert endcap_derived_core_lengths is manufacturing_api.endcap_derived_core_lengths


def test_gui_contains_no_endcap_material_outside_formulas():
    source = inspect.getsource(bridge._sync_active_endcap_and_global_whd)
    propagation = inspect.getsource(bridge._propagate_endcap_derived_cores)
    assert "manufacturing_api.reconcile_endcap_live_outside_dimensions(" in source
    assert "manufacturing_api.endcap_derived_core_lengths(" in propagation
    for body in (source, propagation):
        assert "4.0 * t" not in body
        assert "endcap_depth_comp_t(" not in body
