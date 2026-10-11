# -*- coding: utf-8 -*-
"""#1496 indexed NFB-source discovery: dedupe DXF *filenames*, not switch models.

Authority is the user-maintained 開關索引.csv. Both known schemas have named
士林 / 東元 / 伍菱 columns, with adjacent 深 / 高度 / 準確率 metadata.
One brand+filename is inspected once and may serve many index/model rows.
The same basename in DIFFERENT brand directories is not automatically one
file; missing or invalid originals remain UNKNOWN, never zero openings.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import csv
import hashlib
from typing import Iterable

BRANDS = ("士林", "東元", "伍菱")
NO_SOURCE = "SOURCE_MISSING_UNKNOWN"
UNCERTIFIED = "SOURCE_OBSERVED_UNCERTIFIED"


@dataclass(frozen=True)
class NfbIndexLink:
    row_number: int
    model_key: str


@dataclass(frozen=True)
class NfbUniqueIndexedDxf:
    brand: str
    filename: str
    links: tuple[NfbIndexLink, ...]

    @property
    def relative_path(self) -> Path:
        return Path(self.brand) / self.filename


@dataclass(frozen=True)
class NfbIndexSourceCatalog:
    index_path: str
    index_sha256: str
    records_read: int
    sources: tuple[NfbUniqueIndexedDxf, ...]
    diagnostics: tuple[str, ...]


@dataclass(frozen=True)
class NfbIndexedDxfAudit:
    source: NfbUniqueIndexedDxf
    path: str
    status: str
    source_sha256: str | None
    inventory: object | None
    diagnostic: str | None

    @property
    def process_color_entity_counts(self) -> tuple[tuple[int, int], ...] | None:
        # None is UNKNOWN, not zero. Counts on an observed drawing do not
        # prove the upper opening / plate part / model is manufacturable.
        if self.inventory is None:
            return None
        return self.inventory.process_aci_entity_counts


def _source_filename(raw: str, *, row_number: int, brand: str) -> tuple[str | None, str | None]:
    value = str(raw or "").strip().strip('"').strip()
    # Both original 7-col and RC 10-col tables use 「無對應檔案」 for
    # *no catalog mapping*. This is ordinary absence, NOT a bad filename.
    if not value or value.casefold() in {
        "-", "—", "無", "無檔", "無對應", "無對應檔案", "無對應文件",
        "n/a", "na", "none", "null",
    }:
        return None, None
    if value.endswith(("；", ";")):
        return None, f"row {row_number} {brand}:UNEXPECTED_FILENAME_FORMAT"
    if not value.casefold().endswith(".dxf"):
        return None, f"row {row_number} {brand}:NON_DXF_SOURCE_VALUE"
    # Index is a list of filenames. A path is *not* acceptable here: never
    # let CSV cells escape the known brand folder through /, \\, or traversal.
    if ("/" in value or "\\" in value or value in {".", ".."}
            or Path(value).name != value or "\x00" in value
            or len(value) <= len(".dxf")):
        return None, f"row {row_number} {brand}:UNSAFE_DXF_FILENAME"
    return value, None


def unique_nfb_dxfs_from_switch_index(path: str | Path) -> NfbIndexSourceCatalog:
    """Read 7/10-column 開關索引.csv by named brand columns, not column offsets.

    Other fields (圖塊名稱/深/高度/準確率) are metadata, NOT DXF source names.
    Retain all row links after deduplication for downstream UI/model lookup.
    """
    src = Path(path)
    data = src.read_bytes()
    try:
        content = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("開關索引.csv must be UTF-8 / UTF-8-BOM") from exc
    rows = csv.reader(content.splitlines())
    try:
        header = tuple(v.strip().lstrip("\ufeff") for v in next(rows))
    except StopIteration:
        raise ValueError("開關索引.csv is empty") from None
    if not header or header[0] != "圖塊名稱":
        raise ValueError("開關索引.csv first column must be 圖塊名稱")
    locations: dict[str, int] = {}
    for brand in BRANDS:
        matches = [n for n, value in enumerate(header) if value == brand]
        if len(matches) != 1:
            raise ValueError(f"開關索引.csv requires exactly one {brand} filename column")
        locations[brand] = matches[0]
    if not all(0 < pos < len(header) for pos in locations.values()):
        raise ValueError("開關索引.csv invalid brand column positions")

    groups: dict[tuple[str, str], list[NfbIndexLink]] = {}
    originals: dict[tuple[str, str], str] = {}
    diagnostics: list[str] = []
    records_read = 0
    for lineno, cells in enumerate(rows, start=2):
        if not cells or not any(str(c).strip() for c in cells):
            continue
        records_read += 1
        model = str(cells[0] if cells else "").strip()
        if not model:
            diagnostics.append(f"row {lineno}:MISSING_MODEL_KEY")
            continue
        for brand in BRANDS:
            pos = locations[brand]
            raw = cells[pos] if pos < len(cells) else ""
            filename, diagnostic = _source_filename(raw, row_number=lineno, brand=brand)
            if diagnostic:
                diagnostics.append(diagnostic)
            if filename is None:
                continue
            # Filename dedupe is case-insensitive inside EACH manufacturer
            # folder, but a matching basename across brands is not identity.
            key = (brand, filename.casefold())
            if key not in groups:
                groups[key] = []
                originals[key] = filename
            groups[key].append(NfbIndexLink(lineno, model))
    sources = tuple(
        NfbUniqueIndexedDxf(brand=brand, filename=originals[(brand, lower)],
                            links=tuple(links))
        for (brand, lower), links in groups.items()
    )
    return NfbIndexSourceCatalog(
        index_path=src.name,
        index_sha256=hashlib.sha256(data).hexdigest(),
        records_read=records_read,
        sources=sources,
        diagnostics=tuple(diagnostics),
    )


def audit_unique_nfb_index_sources(
    index_path: str | Path, *, nfb_root: str | Path,
) -> tuple[NfbIndexSourceCatalog, tuple[NfbIndexedDxfAudit, ...]]:
    """Inspect each indexed brand+DXF only once, preserving missing UNKNOWN.

    nfb_root is expected to contain the three named brand subfolders.
    Source analysis is read-only and cannot enable any NFB CUTTING.
    Upper Color150 reference/selection must be independently validated; this
    batch does NOT infer a main hole from overall DXF bbox or lower spacer.
    """
    from .receiving_nfb_dxf_source import inspect_nfb_dxf_source

    index = unique_nfb_dxfs_from_switch_index(index_path)
    root = Path(nfb_root)
    items: list[NfbIndexedDxfAudit] = []
    for source in index.sources:
        target = root / source.relative_path
        if not target.is_file():
            items.append(NfbIndexedDxfAudit(
                source=source, path=str(target), status=NO_SOURCE,
                source_sha256=None, inventory=None, diagnostic="MISSING_DXF_UNKNOWN",
            ))
            continue
        try:
            inventory = inspect_nfb_dxf_source(target)
        except (OSError, ValueError, RuntimeError, UnicodeError) as exc:
            # A file that cannot be reliably parsed is NOT zero holes.
            items.append(NfbIndexedDxfAudit(
                source=source, path=str(target),
                status="SOURCE_UNREADABLE_UNKNOWN", source_sha256=None,
                inventory=None, diagnostic=type(exc).__name__,
            ))
            continue
        items.append(NfbIndexedDxfAudit(
            source=source, path=str(target), status=UNCERTIFIED,
            source_sha256=inventory.source_sha256, inventory=inventory,
            diagnostic=(";".join(inventory.diagnostics) or None),
        ))
    return index, tuple(items)
