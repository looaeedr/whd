"""Explicit Phase 2 manufacturing cache ownership.

The cache owns only immutable cache keys and ManufacturingResolveResult values.
It has no knowledge of Tk, bridge objects, or application identity.
"""
from __future__ import annotations

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
    """Single-entry manufacturing cache with explicit hit/miss receipts."""

    def __init__(self) -> None:
        self._key: ManufacturingCacheKey | None = None
        self._result: ManufacturingResolveResult | None = None

    def lookup(self, key: ManufacturingCacheKey) -> ManufacturingCacheLookup:
        if not isinstance(key, ManufacturingCacheKey):
            raise TypeError("key must be ManufacturingCacheKey")
        hit = self._key == key and self._result is not None
        return ManufacturingCacheLookup(
            result=self._result if hit else None,
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
        self._key = key
        self._result = result
        return ManufacturingCacheReceipt(
            signature=key.fingerprint,
            hit=False,
            stored=True,
        )

    def clear(self) -> None:
        self._key = None
        self._result = None

    @property
    def key(self) -> ManufacturingCacheKey | None:
        return self._key

    @property
    def result(self) -> ManufacturingResolveResult | None:
        return self._result


__all__ = [
    "ManufacturingCacheKey",
    "ManufacturingCacheLookup",
    "ManufacturingCacheService",
]
