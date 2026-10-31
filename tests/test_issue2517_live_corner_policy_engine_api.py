"""#2517 live manual CornerType policy is Engine-owned, distinct from raw payload."""
from __future__ import annotations

import inspect
from types import SimpleNamespace

import pytest

from ae_engine import resolve_live_corner_policy, manufacturing_api
from ae_engine.corner_type_ui import (
    known_model_corner_state, new_manual_corner_state, policy_from_corner_state,
)
from ae_engine.sheetmetal_geometry import CornerTypeId, CornerTypeSelection, CrossCornerMode
import gui


def test_engine_public_live_policy_preserves_explicit_typed_legacy_corner():
    assert resolve_live_corner_policy is manufacturing_api.resolve_live_corner_policy
    state = new_manual_corner_state(("head",))
    state["head"]["top_left"] = CornerTypeSelection(CornerTypeId.C02, 1)
    policy = resolve_live_corner_policy(state, "head", 29, model_name="金庫型")
    assert policy.fw == 29.0
    assert policy.top_left.type_id is CornerTypeId.C02
    assert policy.top_left.rotation_quadrants == 1
    assert policy.bottom_right.cross_mode is CrossCornerMode.STANDARD


@pytest.mark.parametrize("family", ("金庫型", "受電箱"))
def test_missing_live_part_uses_only_explicit_known_family_registry(family):
    actual = resolve_live_corner_policy(
        {}, "head", 25, model_name=family, cabinet_family=family,
    )
    fallback = known_model_corner_state(("head",), cabinet_family=family)["head"]
    assert actual == policy_from_corner_state(fallback, fw=25)


def test_custom_missing_live_part_uses_engine_cross_defaults():
    actual = resolve_live_corner_policy({}, "head", 25)
    expected = policy_from_corner_state(new_manual_corner_state(("head",))["head"], fw=25)
    assert actual == expected
    assert all(getattr(actual, c).type_id is CornerTypeId.CROSS
               for c in ("top_left", "top_right", "bottom_left", "bottom_right"))


def test_incomplete_manual_live_corner_state_rejects_not_fake_fallback():
    incomplete = {"head": {"top_left": CornerTypeSelection(CornerTypeId.CROSS)}}
    with pytest.raises(ValueError, match="缺少手動截角狀態"):
        resolve_live_corner_policy(incomplete, "head", 25, model_name="金庫型", cabinet_family="金庫型")


def test_gui_uses_engine_public_live_policy_and_retains_endcap_family_hook(monkeypatch):
    calls = []
    sentinel = object()
    result = object()
    def engine(state, part, fw, *, model_name, cabinet_family):
        calls.append((state, part, fw, model_name, cabinet_family))
        return sentinel
    monkeypatch.setattr(manufacturing_api, "resolve_live_corner_policy", engine)
    host = SimpleNamespace(
        manual_corner_state={"head": {"top_left": object()}},
        _baseline_source_model=lambda: "金庫型",
        _apply_cabinet_family_endcap_policy=lambda policy, part: result,
    )
    assert gui.Phase6ApplicationHost._manual_corner_policy(host, "head", 25) is result
    assert calls == [(host.manual_corner_state, "head", 25, "金庫型", None)]
    source = inspect.getsource(gui.Phase6ApplicationHost._manual_corner_policy)
    assert "manufacturing_api.resolve_live_corner_policy(" in source
    assert "policy_from_corner_state(" not in source
    assert "new_manual_corner_state(" not in source
    assert "known_model_corner_state(" not in source


def test_gui_missing_custom_state_forwards_without_model(monkeypatch):
    seen = []
    monkeypatch.setattr(manufacturing_api, "resolve_live_corner_policy",
                        lambda state, part, fw, **kw: seen.append(kw) or 1)
    host = SimpleNamespace(manual_corner_state={}, _baseline_source_model=lambda: None)
    assert gui.Phase6ApplicationHost._manual_corner_policy(host, "tail", 25) == 1
    assert seen == [{"model_name": None, "cabinet_family": None}]
