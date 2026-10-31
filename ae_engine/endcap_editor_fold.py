# -*- coding: utf-8 -*-
"""Engine-owned legacy 3-row EndCap Fold editor profile (not FinalScene)."""
from __future__ import annotations
from collections.abc import Mapping, Sequence
from .box_body_fold_profile import _ui_len, apply_outside_dimension_compensation


def build_endcap_editor_simple_profile(snapshot: Mapping[str, object]) -> list[dict]:
    rows = [
        {"len": _ui_len(snapshot.get("ytop1")), "angle": -90, "phase6_key": "ytop1"},
        {"len": _ui_len(snapshot.get("d")), "angle": -90, "phase6_key": "endcap_d"},
        {"len": _ui_len(snapshot.get("ybottom1")), "phase6_key": "ybottom1"},
    ]
    return apply_outside_dimension_compensation(rows, snapshot.get("t", 2))


def read_endcap_editor_simple_profile(profile: Sequence[Mapping[str, object]]) -> dict:
    by_key = {str(s.get("phase6_key")): s for s in profile if s.get("phase6_key")}
    if not {"ytop1", "endcap_d", "ybottom1"}.issubset(by_key):
        raise ValueError("封頭/封尾折彎資料缺少原本三段")
    return {
        "ytop1": _ui_len(by_key["ytop1"].get("len")),
        "d": _ui_len(by_key["endcap_d"].get("len")),
        "ybottom1": _ui_len(by_key["ybottom1"].get("len")),
    }
