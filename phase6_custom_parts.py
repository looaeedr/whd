"""Pure metadata authority for top-level custom physical sheets.

Profiles and manufacturing geometry belong to the Fold/manufacturing owners.
Names never serve as IDs; the persisted allocator never recycles deleted IDs.
"""
from copy import deepcopy
from collections.abc import Mapping
import math
import re

PREFIX = "custom:"
PRESET = "OUTSIDE_17_100"

def is_custom_part(key):
    return str(key or "").startswith(PREFIX)

def _positive_integer(value, label):
    if isinstance(value, bool) or not (
        isinstance(value, int) or isinstance(value, str) and re.fullmatch(r"[0-9]+", value.strip())
    ):
        raise ValueError(f"{label}必須是正整數")
    result = int(value)
    if result < 1:
        raise ValueError(f"{label}必須是正整數")
    return result

def _descriptor(key, value):
    row = deepcopy(dict(value))
    if row.get("physical_id",key) != key:
        raise ValueError("自訂板件 physical ID 不一致")
    name = str(row.get("display_name") or "").strip()
    axis = str(row.get("fold_axis") or "").strip().upper()
    if not name:
        raise ValueError("板件名稱不得為空")
    if axis not in {"X","Y"}:
        raise ValueError("折法軸必須擇一為 X 或 Y")
    raw = row.get("transverse_length")
    try:
        length = float(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError("另一軸尺寸必須是有限正數") from exc
    if isinstance(raw,bool) or not math.isfinite(length) or length <= 0:
        raise ValueError("另一軸尺寸必須是有限正數")
    count = _positive_integer(row.get("per_box_count",1),"每箱片數")
    if row.get("fold_preset",PRESET) != PRESET:
        raise ValueError("不支援的自訂板件折法預設")
    row.update(physical_id=key,display_name=name,fold_axis=axis,
               transverse_length=length,per_box_count=count,fold_preset=PRESET)
    return row

class CustomPartCatalog:
    def __init__(self, payload=None):
        if payload is not None and not isinstance(payload,Mapping):
            raise ValueError("自訂板件資料必須是 mapping")
        data=dict(payload or {})
        self._next_id=_positive_integer(data.get("next_id",1),"自訂 ID counter")
        self._items={}
        for key,row in dict(data.get("items") or {}).items():
            match=re.fullmatch(r"custom:([1-9][0-9]*)",str(key))
            if not match:
                raise ValueError("非法自訂板件 physical ID")
            self._items[key]=_descriptor(key,row)
            self._next_id=max(self._next_id,int(match.group(1))+1)

    @property
    def has_history(self):
        return bool(self._items) or self._next_id > 1

    def snapshot(self):
        return {"next_id":self._next_id,"items":deepcopy(self._items)}

    def get(self,key):
        return deepcopy(self._items.get(str(key)))

    def add(self,**values):
        key=f"{PREFIX}{self._next_id}"
        item=_descriptor(key,values)
        self._items[key]=item
        self._next_id+=1
        return key

    def update(self,key,**values):
        key=str(key)
        if key not in self._items:
            raise ValueError("自訂板件不存在")
        if set(values) - {"display_name","fold_axis","transverse_length","per_box_count"}:
            raise ValueError("不支援的自訂板件設定")
        item=_descriptor(key,{**self._items[key],**values})
        changed=item != self._items[key]
        if changed:
            self._items[key]=item
        return changed

    def remove(self,key):
        return self._items.pop(str(key),None) is not None
