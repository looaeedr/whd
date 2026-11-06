"""#2517: actual BoxBody Fold -> Engine EndCap PartSpec source ownership."""
from copy import deepcopy
from types import SimpleNamespace
import inspect

import pytest

from ae_engine import manufacturing_api
from gui_modules.application import manufacturing_adapter as adapter


def _values(model):
    return {
        "model": model, "w": 500.0, "h": 600.0, "d": 200.0,
        "t": 2.0, "fw": 25.0, "yl1": 15.0, "yr1": 15.0,
        "ytop1": 16.0, "ybottom1": 15.0, "zl1": 12.0, "zr1": 12.0,
    }


def _real_fold():
    return [
        {"phase6_key": "fw_left", "len": 23.0, "angle": -90.0, "ui_len_add": 999.0},
        {"phase6_key": "w", "len": 500.0, "angle": -90.0, "core": "W"},
        {"phase6_key": "fw_right", "len": 18.0, "ui_len_add": 999.0},
    ]


def _build(values, *, is_tail, **kwargs):
    return manufacturing_api.build_endcap_operator_part_spec(
        values, model_name=values["model"], is_tail=is_tail,
        holes=(), **kwargs,
    )


@pytest.mark.parametrize("family", ("受電箱", "金庫型"))
@pytest.mark.parametrize("is_tail", (False, True))
def test_headless_endcap_part_spec_derives_formed_fw_from_real_fold(family, is_tail):
    values = _values(family)
    profile = _real_fold()
    original = deepcopy(profile)
    # Real topology has one adjacent bend at each FW, so each adds exactly T.
    expected = (25.0, 20.0)
    assert manufacturing_api.formed_box_body_fw_widths(profile, values["t"]) == expected
    actual = _build(values, is_tail=is_tail, box_body_fold_profile=profile)
    old_equivalent = _build(
        values, is_tail=is_tail, box_body_formed_fw_left=expected[0],
        box_body_formed_fw_right=expected[1],
    )
    assert actual == old_equivalent
    assert (actual.box_body_formed_fw_left,
            actual.box_body_formed_fw_right) == expected
    assert profile == original  # stale metadata never rewritten by construction


def test_missing_physical_right_fw_does_not_resurrect_removed_fold():
    profile = _real_fold()[:2]
    assert manufacturing_api.formed_box_body_fw_widths(profile, 2.0) == (25.0, None)
    actual = _build(_values("受電箱"), is_tail=False, box_body_fold_profile=profile)
    assert actual.box_body_formed_fw_left == 25.0
    assert actual.box_body_formed_fw_right is None


def test_legacy_direct_formed_widths_without_source_remain_supported():
    values = _values("金庫型")
    spec = _build(
        values, is_tail=True,
        box_body_formed_fw_left=25.0, box_body_formed_fw_right=20.0,
    )
    assert (spec.box_body_formed_fw_left, spec.box_body_formed_fw_right) == (25.0, 20.0)
    legacy_no_width = _build(values, is_tail=False)
    assert legacy_no_width.box_body_formed_fw_left is None
    assert legacy_no_width.box_body_formed_fw_right is None


def test_raw_fold_and_precomputed_widths_cannot_compete_for_authority():
    with pytest.raises(ValueError, match="ENDCAP_OPERATOR_FORMED_FW_DUPLICATE_SOURCE"):
        _build(
            _values("受電箱"), is_tail=False,
            box_body_fold_profile=_real_fold(), box_body_formed_fw_left=100.0,
        )


@pytest.mark.parametrize("is_tail", (False, True))
def test_gui_sends_original_fold_as_engine_source_not_manufactured_fw(monkeypatch, is_tail):
    profile = _real_fold()
    captured = []

    def engine(values, **kwargs):
        captured.append((dict(values), kwargs))
        return "engine-owned-spec"

    monkeypatch.setattr(manufacturing_api, "build_endcap_operator_part_spec", engine)
    controller = SimpleNamespace(
        profile_for=lambda key: None,
        box_body_profile=lambda: profile,
        box_body_structure_state=lambda: {"active_type": "three_piece"},
    )
    host = SimpleNamespace(
        workspace_controller=controller,
        _effective_endcap_fw=lambda key, fw: fw,
        _current_box_assembly_type=lambda: "INSERT",
        _resolved_committed_assembly_relief_cuts=lambda *args: (),
        _baseline_source_model=lambda: "受電箱",
        _manual_corner_policy=lambda *args: None,
        _endcap_depth_comp_t_for_family=lambda *args: 0.0,
        head_holes=(),
        tail_holes=(),
        assembly_joint_state={},
    )
    host._end_cap_part_spec_from_values = (
        lambda values, **kwargs: adapter._end_cap_part_spec_from_values(
            host, values, **kwargs
        )
    )
    assert adapter._end_cap_part_spec(host, _values("受電箱"), is_tail=is_tail) == "engine-owned-spec"
    assert len(captured) == 1
    _operator, kwargs = captured[0]
    assert kwargs["box_body_fold_profile"] is profile
    assert kwargs["box_body_formed_fw_left"] is None
    assert kwargs["box_body_formed_fw_right"] is None
    src = inspect.getsource(adapter._end_cap_part_spec)
    assert "formed_box_body_fw_widths(" not in src
    assert "box_body_fold_profile=" in src
