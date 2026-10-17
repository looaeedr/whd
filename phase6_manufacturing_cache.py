# WHD 尺寸硬契約（CURRENT：個人AI檔案庫/第二層_專案與SOP/07_Phase6尺寸語意與標準截角母規則.md）：
# 3D 操作輸入為唯一資料來源，輸入的是折後包外尺寸及折彎方向；不可用下游組合體回寫輸入。
# 同一拓樸／板厚 T：料長 = 包外 − 實際相鄰 BEND 數(0/1/2)*T；包外 = 料長 + 同一折彎數*T。
# 展開 BEND = 料長前綴和；由展開邊界與 BEND 差分得料長，再按拓樸/T 可反算包外，正反算須一致。
# 單板3D、組合3D、2D及製造/DXF都由這份輸入推導；角度正負只定折彎方向，WRAP/OVERLAY 是裝配語意.

"""Explicit Phase 2 manufacturing cache ownership.

The cache owns only immutable cache keys and ManufacturingResolveResult values.
It has no knowledge of Tk, bridge objects, or application identity.
"""
from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass

from phase6_manufacturing_contracts import (
    ManufacturingCacheReceipt,
    ManufacturingResolveResult,
)


@dataclass(frozen=True)
class ManufacturingCacheKey:
    fingerprint: str

    def __post_init__(self) -> None:
        value = str(self.fingerprint or "").strip().lower()
        if len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
            raise ValueError("manufacturing cache fingerprint must be 64 hex characters")
        object.__setattr__(self, "fingerprint", value)


@dataclass(frozen=True)
class ManufacturingCacheLookup:
    result: ManufacturingResolveResult | None
    receipt: ManufacturingCacheReceipt


class ManufacturingCacheService:
    """Exact semantic manufacturing results with a tiny bounded undo history.

    Legacy/non-Receiving capacity is one. Receiving Set/Bay can retain the
    immediately preceding *complete* manufacturing result: undoing a tail
    append must be an exact fingerprint match, never per-part guesswork.
    No partial/unknown dependencies are silently reused. clear() drops all
    entries, including previously selected results, for baseline reloads.
    """

    def __init__(self, *, max_entries: int = 1) -> None:
        self._entries: OrderedDict[ManufacturingCacheKey, ManufacturingResolveResult] = OrderedDict()
        self.max_entries = 1
        self.set_capacity(max_entries)

    def set_capacity(self, max_entries: int) -> None:
        if type(max_entries) is not int or max_entries not in (1, 2):
            raise ValueError("manufacturing cache capacity must be exactly 1 or 2")
        self.max_entries = max_entries
        while len(self._entries) > max_entries:
            self._entries.popitem(last=False)

    def lookup(self, key: ManufacturingCacheKey) -> ManufacturingCacheLookup:
        if not isinstance(key, ManufacturingCacheKey):
            raise TypeError("key must be ManufacturingCacheKey")
        result = self._entries.get(key)
        hit = result is not None
        if hit:
            self._entries.move_to_end(key)
        return ManufacturingCacheLookup(
            result=result,
            receipt=ManufacturingCacheReceipt(
                signature=key.fingerprint,
                hit=hit,
                stored=False,
            ),
        )

    def store(
        self,
        key: ManufacturingCacheKey,
        result: ManufacturingResolveResult,
    ) -> ManufacturingCacheReceipt:
        if not isinstance(key, ManufacturingCacheKey):
            raise TypeError("key must be ManufacturingCacheKey")
        if not isinstance(result, ManufacturingResolveResult):
            raise TypeError("result must be ManufacturingResolveResult")
        self._entries[key] = result
        self._entries.move_to_end(key)
        while len(self._entries) > self.max_entries:
            self._entries.popitem(last=False)
        return ManufacturingCacheReceipt(
            signature=key.fingerprint,
            hit=False,
            stored=True,
        )

    def clear(self) -> None:
        self._entries.clear()

    @property
    def key(self) -> ManufacturingCacheKey | None:
        return next(reversed(self._entries), None)

    @property
    def result(self) -> ManufacturingResolveResult | None:
        key = self.key
        return self._entries.get(key) if key is not None else None


__all__ = [
    "ManufacturingCacheKey",
    "ManufacturingCacheLookup",
    "ManufacturingCacheService",
]
