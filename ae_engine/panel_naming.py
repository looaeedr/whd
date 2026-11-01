# -*- coding: utf-8 -*-
"""Canonical operator panel names; never physical manufacturing identities."""
from __future__ import annotations

from copy import deepcopy
import re
from typing import Mapping

_FORBIDDEN = set('<>:"/\\|?*')
_RESERVED = {"CON", "PRN", "AUX", "NUL"} | {
    f"{prefix}{i}" for prefix in ("COM", "LPT") for i in range(1, 10)
}
PANEL_NUMBER_RE = re.compile(r"[Pp]([1-9][0-9]*)\Z")


def normalize_panel_name(value: object, *, allow_blank: bool = False) -> str:
    """Validate the operator label as a safe, portable DXF filename stem."""
    if not isinstance(value, str):
        raise ValueError("盤名必須是文字")
    name = value.strip()
    if not name:
        if allow_blank:
            return ""
        raise ValueError("受電箱盤名不能空白")
    if (len(name) > 120 or name.endswith(".") or name in {".", ".."}
            or any(ord(ch) < 32 or ord(ch) == 127 or ch in _FORBIDDEN for ch in name)
            or name.split(".", 1)[0].upper() in _RESERVED):
        raise ValueError("盤名含有不合法的檔名字元或保留名稱")
    return name


def set_cabinet_panel_name(snapshot: Mapping[str, object], name: str) -> dict[str, object]:
    """Public single-cabinet input mutation; Receiving uses per-Bay names."""
    if not isinstance(snapshot, Mapping):
        raise ValueError("箱體專案必須是物件")
    from .cabinet_types.receiving import is_receiving_snapshot
    if is_receiving_snapshot(snapshot):
        raise ValueError("受電箱請編輯指定 Set／Bay 的盤名")
    updated = deepcopy(dict(snapshot))
    updated["panel_name"] = normalize_panel_name(name, allow_blank=True)
    return updated
