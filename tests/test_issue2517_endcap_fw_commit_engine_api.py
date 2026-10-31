"""#2517: EndCap FW state edits must be Engine-owned public operations."""
from __future__ import annotations

from copy import deepcopy
import inspect

import pytest

from ae_engine import (
    ENDCAP_FW_PARTS, FW_FOLLOW_BODY, FW_FOLLOW_HEAD, FW_FOLLOW_TAIL,
    FW_INDEPENDENT, commit_box_fw, commit_endcap_fw, set_endcap_fw_follow,
    set_endcap_fw_override,
)
from ae_engine import manufacturing_api
from ae_engine import endcap_factory_fold as owner
import phase6_endcap_semantics as gui


def test_public_read_write_endcap_fw_uses_same_engine_owner():
    for name in ("commit_box_fw", "commit_endcap_fw", "set_endcap_fw_follow", "set_endcap_fw_override"):
        assert getattr(manufacturing_api, name) is getattr(owner, name)
    assert ENDCAP_FW_PARTS is owner.ENDCAP_FW_PARTS
    assert gui.FW_FOLLOW_BODY == FW_FOLLOW_BODY
    assert gui.FW_FOLLOW_HEAD == FW_FOLLOW_HEAD
    assert gui.FW_FOLLOW_TAIL == FW_FOLLOW_TAIL
    assert gui.FW_INDEPENDENT == FW_INDEPENDENT


def test_operator_head_tail_fw_edit_then_box_reset_drives_real_endcap_fold():
    state = manufacturing_api.normalize_endcap_fw_state({"model": "金庫型", "fw": 25})
    assert state["mode"] == FW_FOLLOW_BODY
    assert commit_endcap_fw(state, "head", 31, box_fw=25) is state
    assert state["mode"] == FW_FOLLOW_HEAD
    assert state["head"]["value"] == state["tail"]["value"] == 31
    assert gui.commit_endcap_fw(state, "head", 33, box_fw=25) is state
    assert state["head"]["value"] == state["tail"]["value"] == 33
    assert commit_endcap_fw(state, "tail", 36, box_fw=25) is state
    assert state["mode"] == FW_INDEPENDENT
    assert state["head"]["value"] == 33
    assert state["tail"]["value"] == 36
    snapshot = {"model": "金庫型", "w": 500, "d": 200, "t": 2, "fw": 25, "endcap_fw": deepcopy(state)}
    for part, outside_fw in (("head", 33), ("tail", 36)):
        assert manufacturing_api.resolve_endcap_fw(snapshot, part) == outside_fw
        physical = manufacturing_api.build_endcap_xy_fold_profiles(snapshot, part_key=part)
        assert next(row for row in physical["Y"] if row["phase6_key"] == "fw")["len"] == outside_fw
    assert gui.commit_box_fw(state, 40) is state
    assert state["mode"] == FW_FOLLOW_BODY
    assert state["head"]["value"] == state["tail"]["value"] == 40
    assert all(state[part]["follow_box"] is True for part in ENDCAP_FW_PARTS)


def test_legacy_missing_mode_migrates_at_real_engine_commit_seam():
    saved = {
        "head": {"follow_box": True, "value": 25},
        "tail": {"follow_box": True, "value": 25},
    }
    assert commit_endcap_fw(saved, "head", 32, box_fw=25) is saved
    assert saved["mode"] == FW_FOLLOW_HEAD
    assert saved["head"]["value"] == saved["tail"]["value"] == 32
    assert set_endcap_fw_override(saved, "tail", 39) is saved["tail"]
    assert saved["mode"] == FW_INDEPENDENT
    assert saved["head"]["value"] == 32
    assert saved["tail"]["value"] == 39


def test_legacy_follow_control_keeps_original_return_item_and_state():
    saved = manufacturing_api.normalize_endcap_fw_state({"fw": 25})
    item = gui.set_endcap_fw_follow(saved, "head", False, box_fw=25)
    assert item is saved["head"]
    assert saved["mode"] == FW_INDEPENDENT
    assert item["follow_box"] is False
    assert item["value"] == 25
    assert set_endcap_fw_follow(saved, "head", True, box_fw=25) is saved["head"]


@pytest.mark.parametrize("fn", ("commit_endcap_fw", "set_endcap_fw_follow", "set_endcap_fw_override"))
def test_unknown_endcap_part_fails_closed(fn):
    state = manufacturing_api.normalize_endcap_fw_state({"fw": 25})
    with pytest.raises(ValueError, match="不支援的封頭尾板件"):
        if fn == "commit_endcap_fw":
            commit_endcap_fw(state, "forged", 30, box_fw=25)
        elif fn == "set_endcap_fw_follow":
            set_endcap_fw_follow(state, "forged", False, box_fw=25)
        else:
            set_endcap_fw_override(state, "forged", 30)


def test_phase6_does_not_write_independent_fw_manufacturing_state():
    for name in ("commit_box_fw", "commit_endcap_fw", "set_endcap_fw_follow", "set_endcap_fw_override"):
        src = inspect.getsource(getattr(gui, name))
        assert f"manufacturing_api.{name}(" in src
    assert "from phase6_" not in inspect.getsource(owner)
