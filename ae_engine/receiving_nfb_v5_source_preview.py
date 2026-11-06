# -*- coding: utf-8 -*-
"""Source-only Receiving V5 NFB preview cache; never a machining approval.

The brand CSV remains the sole model source. This owner validates stored V5
identity, captures file revision and rejects mid-read source drift. GUI paints
already-resolved NfbNumericSpec positions without inspecting CSV files.
"""
from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from hashlib import sha256
from functools import lru_cache

from .receiving_nfb_model_identity import (
    parse_numeric_model_ref, selected_numeric_spec,
)
from .receiving_nfb_numeric_catalog import NfbNumericSpec, brand_csv_path


@dataclass(frozen=True)
class ReceivingNfbV5SourcePreview:
    """Verified source identity/revision plus unapproved numeric catalogue data."""

    source_key: tuple[str, str, str, int, int, int]
    spec: NfbNumericSpec
    manufacturing_ready: bool = False


class ReceivingNfbV5SourcePreviewCache:
    """Bounded per-editor revision cache; repeat highlights do not reparse CSV."""

    def __init__(self, max_entries: int = 8):
        if type(max_entries) is not int or not 1 <= max_entries <= 32:
            raise ValueError("NFB V5 preview cache budget invalid")
        self.max_entries = max_entries
        self._entries: OrderedDict[tuple, ReceivingNfbV5SourcePreview] = OrderedDict()
        self.parse_count = 0

    def clear(self) -> None:
        """Explicitly invalidate per-editor cache without touching source CSV."""
        self._entries.clear()

    def __len__(self) -> int:
        """Count retained source revisions for performance and UAT probes."""
        return len(self._entries)

    @staticmethod
    def display_model_label(model_ref: object) -> str:
        """Display identity only, including an invalid reference on error."""
        parsed = parse_numeric_model_ref(model_ref)
        return parsed[1] if parsed is not None else str(model_ref)

    def load(self, brand: str, model_ref: str) -> ReceivingNfbV5SourcePreview:
        """Resolve EXACT selected brand/model and its current CSV revision."""
        parsed = parse_numeric_model_ref(model_ref)
        if parsed is None or parsed[0] != brand:
            raise ValueError("V5 型號與選定廠牌不符")
        source = brand_csv_path(brand)
        stamp = source.stat()
        key = ("v5", brand, model_ref, stamp.st_mtime_ns,
               stamp.st_ctime_ns, stamp.st_size)
        found = self._entries.get(key)
        if found is not None:
            self._entries.move_to_end(key)
            return found
        spec = selected_numeric_spec(brand, model_ref)
        # A CSV edited while parsing must never enter a cache under its old
        # provenance, even when the model name is unchanged.
        after = source.stat()
        if (after.st_mtime_ns, after.st_ctime_ns, after.st_size) != (
            stamp.st_mtime_ns, stamp.st_ctime_ns, stamp.st_size
        ):
            raise ValueError("V5 CSV 讀取期間來源版本變更")
        if spec is None:
            raise ValueError("廠牌 CSV 已無此型號")
        if not isinstance(spec, NfbNumericSpec) or (spec.brand, spec.model) != parsed:
            raise ValueError("V5 CSV 型號來源身份不一致")
        result = ReceivingNfbV5SourcePreview(key, spec)
        # Earlier revisions of the same model must not retain stale memory.
        for existing in tuple(self._entries):
            if existing[:3] == key[:3]:
                del self._entries[existing]
        self._entries[key] = result
        self.parse_count += 1
        while len(self._entries) > self.max_entries:
            self._entries.popitem(last=False)
        return result


@dataclass(frozen=True)
class ReceivingNfbV5ModelCatalogSnapshot:
    """One exact per-brand CSV revision and its current selectable identities.

    Operator source display only: no hole geometry or manufacturing approval.
    """

    brand: str
    source_sha256: str
    model_refs: tuple[str, ...]
    manufacturing_ready: bool = False


@lru_cache(maxsize=32)
def _read_nfb_catalog_models_for_exact_revision(
    brand: str, source_path: str, source_sha256: str,
) -> tuple[str, ...]:
    """Engine-owned bounded parser cache; never trust GUI-stored model rows."""
    from .receiving_nfb_model_identity import numeric_model_refs
    return numeric_model_refs(brand)


def project_receiving_nfb_v5_model_catalog_snapshot(
    brand: str,
) -> ReceivingNfbV5ModelCatalogSnapshot:
    """Read a fresh validated NFB catalog with full-byte source identity.

    A same-size, same-mtime CSV replacement must refresh the operator list.
    Fail closed if the source changes while the authoritative CSV parser
    reads it; no partial/stale model inventory is returned to GUI clients.
    """
    # Resolve the SAME live source-path owner used by numeric_model_refs(),
    # including an explicitly substituted source in a scoped GUI test.
    from . import receiving_nfb_numeric_catalog as numeric_catalog
    source = numeric_catalog.brand_csv_path(brand)
    before = source.read_bytes()
    digest = sha256(before).hexdigest()
    # Polling checks full file content every time but reparses only a new
    # exact CSV revision. The cache is bounded and keyed to the real source
    # path, not GUI-computed metadata or an operator-supplied model list.
    models = _read_nfb_catalog_models_for_exact_revision(
        brand, str(source.resolve()), digest,
    )
    if source.read_bytes() != before:
        raise ValueError("RECEIVING_NFB_V5_CATALOG_SOURCE_CHANGED_DURING_READ")
    return ReceivingNfbV5ModelCatalogSnapshot(
        brand=brand,
        source_sha256=digest,
        model_refs=models,
    )
