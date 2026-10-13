# -*- coding: utf-8 -*-
"""#1496: repeatable, read-only brand+filename DXF provenance/color coverage.

Run from repo root:
    python tools/nfb_source_audit.py --source-root /path/to/NFB --out /tmp/nfb-audit.json

The 24 unique entries are the SOURCE filenames in 開關索引.csv, not one per
switch-index row. A missing/unreadable/unresolved DXF is UNKNOWN, never zero.
Existing source-identity pins must match exactly or color observations are
withheld. This is evidence, not a manufacturing-capability registry.
"""
from __future__ import annotations

import argparse
import csv
from dataclasses import replace
import json
from pathlib import Path
import re
import sys
from tempfile import TemporaryDirectory
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ae_engine.receiving_nfb_index_sources import (
    UNCERTIFIED,
    audit_unique_nfb_index_sources,
    build_nfb_indexed_color_evidence,
)

DEFAULT_INDEX = ROOT / "基準檔" / "開孔" / "NFB" / "開關索引.csv"
# Real source drawings are NOT stored alongside the index CSV.
DEFAULT_SOURCE_ROOT = ROOT / "基準檔" / "NFB"
DEFAULT_PINS = ROOT / "基準檔" / "開孔" / "NFB" / "來源輪廓索引.csv"


def _identity_pins(path: Path) -> dict[tuple[str, str], str]:
    """Read exact indexed-name/brand SHA pins, never fuzzy filename aliases."""
    if not path.is_file():
        raise ValueError("NFB expected SHA source-outline index is missing")
    with path.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        mandatory = {"brand", "indexed_filename", "source_sha256"}
        if not mandatory.issubset(reader.fieldnames or []):
            raise ValueError("NFB source-outline pin index lacks mandatory columns")
        result: dict[tuple[str, str], str] = {}
        for line, row in enumerate(reader, start=2):
            brand = (row["brand"] or "").strip()
            filename = (row["indexed_filename"] or "").strip()
            expected = (row["source_sha256"] or "").strip().lower()
            if (not brand or not filename.lower().endswith(".dxf")
                    or not re.fullmatch("[0-9a-f]{64}", expected)):
                raise ValueError(f"NFB invalid pinned source identity at row {line}")
            key = brand, filename.casefold()
            if key in result:
                raise ValueError("NFB duplicate pinned brand/filename identity")
            result[key] = expected
    return result


def _audit_with_optional_archive(
    index_path: str | Path, *, source_root: str | Path,
    archive_path: str | Path | None,
):
    """Use original brand folders, then only uniquely named ZIP members.

    The archive is read-only. A missing indexed name may be sampled from one
    uniquely matching ZIP member, NEVER from a guessed manufacturer alias.
    The temporary tree is cleaned automatically. No original file is copied
    back or modified; the evidence records archival provenance separately.
    """
    from ae_engine.receiving_nfb_index_sources import (
        audit_unique_nfb_index_sources, unique_nfb_dxfs_from_switch_index,
    )
    if archive_path is None:
        catalog, audits = audit_unique_nfb_index_sources(
            index_path, nfb_root=source_root,
        )
        return catalog, audits, {}
    catalog = unique_nfb_dxfs_from_switch_index(index_path)
    stored = {}
    with ZipFile(archive_path) as archive, TemporaryDirectory(
        prefix="whd-nfb-index-source-audit-"
    ) as scratch:
        members_by_basename = {}
        for info in archive.infolist():
            if info.is_dir():
                continue
            basename = info.filename.rsplit("/", 1)[-1].casefold()
            members_by_basename.setdefault(basename, []).append(info)
        staged = Path(scratch)
        for item in catalog.sources:
            origin = Path(source_root) / item.relative_path
            destination = staged / item.relative_path
            destination.parent.mkdir(parents=True, exist_ok=True)
            key = (item.brand, item.filename.casefold())
            if origin.is_file():
                destination.symlink_to(origin.resolve())
                stored[key] = "BRAND_SOURCE_FOLDER"
                continue
            matches = members_by_basename.get(item.filename.casefold(), ())
            if len(matches) == 1:
                destination.write_bytes(archive.read(matches[0]))
                stored[key] = "ARCHIVE_SINGLE_EXACT_BASENAME_TEMP"
            else:
                stored[key] = (
                    "ARCHIVE_AMBIGUOUS_UNKNOWN" if matches
                    else "SOURCE_MISSING_UNKNOWN"
                )
        _catalog, audits = audit_unique_nfb_index_sources(
            index_path, nfb_root=staged,
        )
        if _catalog != catalog:
            raise ValueError("NFB staged archive index identity changed")
        return catalog, audits, stored


def build_source_coverage_report(
    index_path: str | Path, *, source_root: str | Path,
    pin_path: str | Path, archive_path: str | Path | None = None,
) -> dict[str, object]:
    """Resolve every catalog name; unknown observations carry JSON null counts.

    Pins are provenance checks, NOT permissions for main-hole CUTTING.
    A real file with unexpected bytes stays UNKNOWN despite parsable geometry.
    """
    catalog, audits, storage = _audit_with_optional_archive(
        index_path, source_root=source_root, archive_path=archive_path,
    )
    if catalog.diagnostics:
        raise ValueError("NFB source catalog has unresolved CSV diagnostics: "
                         + ";".join(catalog.diagnostics))
    pins = _identity_pins(Path(pin_path))
    catalog_keys = {(row.brand, row.filename.casefold()) for row in catalog.sources}
    if set(pins) - catalog_keys:
        raise ValueError("NFB pinned source is absent from the current switch index")
    guarded = []
    for audit in audits:
        key = audit.source.brand, audit.source.filename.casefold()
        pinned = pins.get(key)
        if (pinned is not None and audit.source_sha256 is not None
                and audit.source_sha256 != pinned):
            guarded.append(replace(
                audit, status="SOURCE_IDENTITY_MISMATCH_UNKNOWN",
                inventory=None, diagnostic="ORIGINAL_SHA_DIFFERS_FROM_PIN",
            ))
        else:
            guarded.append(audit)
    evidence = build_nfb_indexed_color_evidence(catalog, guarded)
    records = []
    by_brand: dict[str, dict[str, int]] = {}
    for row in evidence:
        key = row.brand, row.filename.casefold()
        expected = pins.get(key)
        if row.status == UNCERTIFIED and expected is not None:
            assert row.source_sha256 == expected
        records.append({
            "brand": row.brand, "indexed_filename": row.filename,
            "source_relative_path": str(row.brand + "/" + row.filename),
            "source_storage": storage.get(
                key, "BRAND_SOURCE_FOLDER" if row.source_sha256
                else "SOURCE_MISSING_UNKNOWN"
            ),
            "model_links": [
                {"csv_row": x.row_number, "model_key": x.model_key}
                for x in row.model_links
            ],
            "source_sha256": row.source_sha256,
            "expected_sha256": expected,
            "provenance_pin_matches": (
                row.source_sha256 == expected
                if row.source_sha256 is not None and expected is not None
                else None
            ),
            "status": row.status,
            "color_30_entities": row.aci30_count,
            "color_150_entities": row.aci150_count,
            "color_212_entities": row.aci212_count,
            "diagnostic": row.diagnostic,
            "manufacturing_ready": False,
        })
        stats = by_brand.setdefault(row.brand, {
            "unique_sources": 0, "references": 0,
            "observed_uncertified": 0, "unknown": 0,
        })
        stats["unique_sources"] += 1
        stats["references"] += len(row.model_links)
        stats["observed_uncertified" if row.status == UNCERTIFIED else "unknown"] += 1
    references = sum(len(row.model_links) for row in evidence)
    assert len(records) == len(catalog.sources)
    return {
        "schema": "WHD_NFB_INDEXED_SOURCE_COLOR_COVERAGE_V1",
        "source_index": catalog.index_path,
        "source_index_sha256": catalog.index_sha256,
        "index_records": catalog.records_read,
        "totals": {
            "source_references": references,
            "unique_brand_filenames": len(records),
            "observed_uncertified": sum(v["observed_uncertified"] for v in by_brand.values()),
            "unknown": sum(v["unknown"] for v in by_brand.values()),
        },
        "by_brand": by_brand,
        "records": records,
        "scope": "DXF_SOURCE_COLOR_OBSERVATION_ONLY",
        "manufacturing_ready": False,
        "warnings": [
            "NULL Color30/150/212 = UNKNOWN, not zero features or holes",
            "Observed color entity counts are NOT manufacturing-ready hole counts",
            "Color212 or source region alone cannot assign a physical part",
            "The source drawing's whole-file bbox is NEVER a main-hole pivot",
            "Lower PAD/spacer region is deferred; do not emit base/middle plate CUTTING",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", type=Path, default=DEFAULT_INDEX)
    parser.add_argument("--source-root", type=Path,
                        default=DEFAULT_SOURCE_ROOT)
    parser.add_argument("--archive", type=Path, default=None,
                        help="Optional ZIP fallback for uniquely named missing originals")
    parser.add_argument("--pins", type=Path, default=DEFAULT_PINS)
    parser.add_argument("--out", type=Path,
                        help="Optional report path; absent means stdout only")
    args = parser.parse_args(argv)
    report = build_source_coverage_report(
        args.index, source_root=args.source_root, pin_path=args.pins,
        archive_path=args.archive,
    )
    payload = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.out is not None:
        output = args.out.resolve()
        for source in (args.index, args.pins):
            if output == source.resolve():
                raise ValueError("NFB audit report cannot overwrite source indexes")
        if output.is_relative_to(args.source_root.resolve()):
            raise ValueError("NFB audit report must not be written under NFB originals")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(payload, encoding="utf-8")
    else:
        sys.stdout.write(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
