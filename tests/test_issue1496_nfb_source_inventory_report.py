# -*- coding: utf-8 -*-
"""#1496: canonical indexed-source coverage never conflates missing and 0."""
from __future__ import annotations

import csv
from hashlib import sha256
import json

import ezdxf
import pytest

from tools.nfb_source_audit import (
    DEFAULT_INDEX, DEFAULT_PINS, build_source_coverage_report, main,
)


def _case(tmp_path):
    index = tmp_path / "開關索引.csv"
    with index.open("w", encoding="utf-8-sig", newline="") as fd:
        writer = csv.writer(fd)
        writer.writerow(("圖塊名稱", "士林", "深", "東元", "深", "伍菱", "深"))
        writer.writerow(("K1", "A.dxf", "", "A.dxf", "", "B.dxf", ""))
        writer.writerow(("K2", "A.dxf", "", "C.dxf", "", "無對應檔案", ""))
    root = tmp_path / "NFB"
    for brand in ("士林", "東元", "伍菱"):
        (root / brand).mkdir(parents=True)
    shihlin = ezdxf.new("R2010")
    m = shihlin.modelspace()
    m.add_circle((5, 7), 3, dxfattribs={"color": 30})
    m.add_lwpolyline([(0, 0), (10, 0), (10, 16), (0, 16)],
                     close=True, dxfattribs={"color": 150})
    m.add_arc((5, 7), 4, 0, 90, dxfattribs={"color": 212})
    source = root / "士林" / "A.dxf"
    shihlin.saveas(source)
    teco = ezdxf.new("R2010")
    teco.modelspace().add_circle((1, 1), 2, dxfattribs={"color": 30})
    teco.saveas(root / "東元" / "A.dxf")
    pins = tmp_path / "來源輪廓索引.csv"
    with pins.open("w", encoding="utf-8-sig", newline="") as fd:
        writer = csv.writer(fd)
        writer.writerow(("brand", "indexed_filename", "source_sha256"))
        writer.writerow(("士林", "A.dxf", sha256(source.read_bytes()).hexdigest()))
        # Corrupted/replaced original is counted UNKNOWN, not a trusted zero.
        writer.writerow(("東元", "A.dxf", "0" * 64))
    return index, root, pins, source


def test_complete_per_brand_audit_has_exact_links_and_null_unknown(tmp_path):
    index, root, pins, original = _case(tmp_path)
    before_index, before_original = index.read_bytes(), original.read_bytes()
    report = build_source_coverage_report(index, source_root=root, pin_path=pins)
    assert report["schema"] == "WHD_NFB_INDEXED_SOURCE_COLOR_COVERAGE_V1"
    assert report["index_records"] == 2
    assert report["source_index_sha256"] == sha256(before_index).hexdigest()
    assert report["totals"] == {
        "source_references": 5, "unique_brand_filenames": 4,
        "observed_uncertified": 1, "unknown": 3,
    }
    entries = {(r["brand"], r["indexed_filename"]): r for r in report["records"]}
    shihlin = entries["士林", "A.dxf"]
    assert shihlin["source_sha256"] == shihlin["expected_sha256"]
    assert shihlin["provenance_pin_matches"] is True
    assert shihlin["status"] == "SOURCE_OBSERVED_UNCERTIFIED"
    assert tuple(shihlin["model_links"]) == (
        {"csv_row": 2, "model_key": "K1"},
        {"csv_row": 3, "model_key": "K2"},
    )
    assert [shihlin[f"color_{v}_entities"] for v in (30, 150, 212)] == [1, 1, 1]
    changed = entries["東元", "A.dxf"]
    assert changed["status"] == "SOURCE_IDENTITY_MISMATCH_UNKNOWN"
    assert changed["provenance_pin_matches"] is False
    assert changed["diagnostic"] == "ORIGINAL_SHA_DIFFERS_FROM_PIN"
    assert changed["source_sha256"] is not None
    for entry in [changed, entries["東元", "C.dxf"], entries["伍菱", "B.dxf"]]:
        assert (entry["color_30_entities"], entry["color_150_entities"],
                entry["color_212_entities"]) == (None, None, None)
        assert entry["manufacturing_ready"] is False
    assert index.read_bytes() == before_index
    assert original.read_bytes() == before_original
    assert report["manufacturing_ready"] is False


def test_cli_writes_report_but_never_overwrites_original_sources(tmp_path):
    index, root, pins, original = _case(tmp_path)
    path = tmp_path / "audit" / "coverage.json"
    args = ["--index", str(index), "--source-root", str(root),
            "--pins", str(pins), "--out", str(path)]
    assert main(args) == 0
    assert json.loads(path.read_text(encoding="utf-8"))["totals"]["unknown"] == 3
    with pytest.raises(ValueError, match="overwrite source indexes"):
        main([*args[:-1], str(index)])
    with pytest.raises(ValueError, match="under NFB originals"):
        main([*args[:-1], str(root / "unexpected.json")])
    assert original.is_file()


def test_native_original_index_is_42_rows_24_sources_and_64_references(tmp_path):
    # GitHub's actual index exists in this repository. Absence of raw DXF in
    # CI leaves every color UNKNOWN, not a fabricated count of zero.
    report = build_source_coverage_report(
        DEFAULT_INDEX, source_root=tmp_path / "missing_NFB_originals",
        pin_path=DEFAULT_PINS,
    )
    assert report["index_records"] == 42
    assert report["totals"] == {
        "source_references": 64, "unique_brand_filenames": 24,
        "observed_uncertified": 0, "unknown": 24,
    }
    assert report["by_brand"] == {
        "士林": {"unique_sources": 8, "references": 21, "observed_uncertified": 0, "unknown": 8},
        "東元": {"unique_sources": 8, "references": 19, "observed_uncertified": 0, "unknown": 8},
        "伍菱": {"unique_sources": 8, "references": 24, "observed_uncertified": 0, "unknown": 8},
    }
    for row in report["records"]:
        assert row["status"] == "SOURCE_MISSING_UNKNOWN"
        assert all(row[f"color_{color}_entities"] is None for color in (30, 150, 212))
        assert row["manufacturing_ready"] is False
    matched = next(r for r in report["records"]
                   if r["brand"] == "士林"
                   and r["indexed_filename"] == "400_140X257_107.dxf")
    assert matched["expected_sha256"] == (
        "8daecaacacb9683c1436d29aa75fbba85c09d54536b92945fbaad06e049fadf3"
    )
    assert len(matched["model_links"]) == 5
    assert matched["source_sha256"] is None


def test_invalid_pins_cannot_certify_foreign_source(tmp_path):
    index, root, pins, _ = _case(tmp_path)
    with pins.open("a", encoding="utf-8") as fd:
        fd.write("假廠,FOREIGN.dxf," + "1" * 64 + "\n")
    with pytest.raises(ValueError, match="absent from the current switch index"):
        build_source_coverage_report(index, source_root=root, pin_path=pins)
