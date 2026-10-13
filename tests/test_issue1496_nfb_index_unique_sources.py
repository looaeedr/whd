# -*- coding: utf-8 -*-
"""#1496 index-authoritative NFB file deduplication and auditable source lookup."""
from __future__ import annotations

import csv
import json
import os
from pathlib import Path

import ezdxf
import pytest

from ae_engine.receiving_nfb_index_sources import (
    audit_unique_nfb_index_sources,
    unique_nfb_dxfs_from_switch_index,
)


def _index(tmp_path, *, ten_columns=False):
    path = tmp_path / "開關索引.csv"
    if ten_columns:
        header = (
            "圖塊名稱", "士林", "高度", "準確率",
            "東元", "高度", "準確率",
            "伍菱", "高度", "準確率",
        )
        rows = [
            ("M400", "400_140X257_107(1).dxf", "107", "0.8",
             "400_Type.dxf", "95", "0.7", "A.dxf", "110", "0.9"),
            ("M400B", "400_140X257_107(1).dxf", "107", "0.8",
             "400_Type.dxf", "95", "0.7", "A.dxf", "110", "0.9"),
            ("M500", "Other.DXF", "180", "0.4",
             "400_Type.dxf", "95", "0.7", "", "", ""),
            ("M600", "", "", "", "400_Type.dxf", "95", "",
             "400_140X257_107(1).dxf", "110", "0.9"),
        ]
    else:
        header = ("圖塊名稱", "士林", "深", "東元", "深", "伍菱", "深")
        rows = [
            ("M400", "400_140X257_107(1).dxf", "107", "400_Type.dxf", "95", "A.dxf", "110"),
            ("M400B", "400_140X257_107(1).dxf", "107", "400_Type.dxf", "95", "A.dxf", "110"),
            ("M500", "Other.DXF", "180", "400_Type.dxf", "95", "", ""),
            ("M600", "", "", "400_Type.dxf", "95", "400_140X257_107(1).dxf", "110"),
        ]
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(header)
        writer.writerows(rows)
    return path


@pytest.mark.parametrize("ten_columns", [False, True])
def test_csv_filenames_are_unique_per_brand_not_per_model_or_dimensions(
    tmp_path, ten_columns,
):
    path = _index(tmp_path, ten_columns=ten_columns)
    index = unique_nfb_dxfs_from_switch_index(path)
    assert index.records_read == 4
    assert index.index_path == "開關索引.csv"
    assert len(index.index_sha256) == 64
    assert index.diagnostics == ()
    catalog = {(entry.brand, entry.filename): entry for entry in index.sources}
    assert set(catalog) == {
        ("士林", "400_140X257_107(1).dxf"),
        ("士林", "Other.DXF"),
        ("東元", "400_Type.dxf"),
        ("伍菱", "A.dxf"),
        ("伍菱", "400_140X257_107(1).dxf"),
    }
    # 5 unique brand/path pairs: four rows do NOT imply four unique DXFs per brand.
    assert len(index.sources) == 5
    assert len(catalog[("東元", "400_Type.dxf")].links) == 4
    assert {entry.model_key for entry in catalog[("東元", "400_Type.dxf")].links} == {
        "M400", "M400B", "M500", "M600",
    }
    assert len(catalog[("士林", "400_140X257_107(1).dxf")].links) == 2
    assert len(catalog[("伍菱", "400_140X257_107(1).dxf")].links) == 1
    assert all(link.row_number >= 2 for source in index.sources for link in source.links)


def test_case_insensitive_dedupe_only_within_same_brand(tmp_path):
    path = tmp_path / "開關索引.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as fp:
        writer = csv.writer(fp)
        writer.writerow(("圖塊名稱", "士林", "深", "東元", "深", "伍菱", "深"))
        writer.writerow(("M1", "A.dxf", "1", "A.DXF", "2", "", ""))
        writer.writerow(("M2", "a.DXF", "1", "", "", "", ""))
    result = unique_nfb_dxfs_from_switch_index(path)
    assert len(result.sources) == 2
    assert [(r.brand, r.filename, len(r.links)) for r in result.sources] == [
        ("士林", "A.dxf", 2),
        ("東元", "A.DXF", 1),
    ]


def test_no_directory_traversal_and_unrecognized_cells_are_diagnostic(tmp_path):
    path = tmp_path / "開關索引.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as fp:
        writer = csv.writer(fp)
        writer.writerow(("圖塊名稱", "士林", "深", "東元", "深", "伍菱", "深"))
        writer.writerow(("M1", "../evil.dxf", "", "N/A", "", "該型號無檔", ""))
        writer.writerow(("M2", "safe.dxf", "", "path\\evil.dxf", "", "", ""))
    result = unique_nfb_dxfs_from_switch_index(path)
    assert len(result.sources) == 1
    assert result.sources[0].filename == "safe.dxf"
    assert any("UNSAFE_DXF_FILENAME" in d for d in result.diagnostics)
    assert any("NON_DXF_SOURCE_VALUE" in d for d in result.diagnostics)


def test_batch_actual_source_is_read_once_and_missing_is_unknown(tmp_path, monkeypatch):
    from ae_engine import receiving_nfb_dxf_source

    path = _index(tmp_path)
    root = tmp_path / "NFB"
    (root / "士林").mkdir(parents=True)
    (root / "伍菱").mkdir(parents=True)
    (root / "東元").mkdir(parents=True)
    doc = ezdxf.new("R2010")
    doc.layers.new("MID_OPEN", dxfattribs={"color": 150})
    doc.modelspace().add_lwpolyline(
        [(0, 0), (57, 0), (57, 96), (0, 96)],
        close=True, dxfattribs={"layer": "MID_OPEN"},
    )
    filename = "400_140X257_107(1).dxf"
    doc.saveas(root / "士林" / filename)
    calls = []
    original = receiving_nfb_dxf_source.inspect_nfb_dxf_source

    def counting_parser(dxf_path):
        calls.append(str(dxf_path))
        return original(dxf_path)

    monkeypatch.setattr(receiving_nfb_dxf_source, "inspect_nfb_dxf_source", counting_parser)
    index, audited = audit_unique_nfb_index_sources(path, nfb_root=root)
    assert len(index.sources) == len(audited) == 5
    assert calls == [str(root / "士林" / filename)]
    by_path = {(item.source.brand, item.source.filename): item for item in audited}
    found = by_path[("士林", filename)]
    assert found.status == "SOURCE_OBSERVED_UNCERTIFIED"
    assert found.source_sha256 is not None
    assert dict(found.process_color_entity_counts)[150] == 1
    assert found.inventory.approved_manufacturing_rule_revision is None
    assert found.inventory.main_hole_source_id is None
    assert len(found.source.links) == 2
    # Same filename under 伍菱 must remain independent (currently missing).
    missing = by_path[("伍菱", filename)]
    assert missing.status == "SOURCE_MISSING_UNKNOWN"
    assert missing.process_color_entity_counts is None
    assert missing.source_sha256 is None
    # Existing but unclassified upper source must never imply a real CUTTING.


def test_brand_columns_required_and_no_metadata_column_interpreted_as_dxf(tmp_path):
    path = tmp_path / "開關索引.csv"
    path.write_text("圖塊名稱,士林,深,東元,深\nM400,file.dxf,100,other.dxf,150\n",
                    encoding="utf-8-sig")
    with pytest.raises(ValueError, match="伍菱"):
        unique_nfb_dxfs_from_switch_index(path)



REAL_INDEX_WITNESS = (
    Path(__file__).resolve().parent
    / "fixtures" / "receiving_nfb_real_switch_index_manifest.json"
)


def _real_index_witness():
    return json.loads(REAL_INDEX_WITNESS.read_text(encoding="utf-8"))


def test_real_uploaded_42_row_index_golden_manifest_is_consistent():
    witness = _real_index_witness()
    assert witness["source_sha256"] == (
        "d6638de4dc204de5a9c465359ab6f051033ef505eab1382ae9234e68b5134321"
    )
    assert witness["source_format"] == "UTF-8-BOM, 7 columns"
    assert witness["records"] == 42
    assert witness["totals"] == {
        "references": 64, "unique_brand_filenames": 24,
        "no_matching_file_cells": 62,
    }
    total_refs = 0
    total_unique = 0
    total_missing = 0
    for brand, expected in witness["by_brand"].items():
        assert brand in ("士林", "東元", "伍菱")
        refs = expected["source_reference_counts"]
        assert len(refs) == 8
        assert len(refs) == len({name.casefold() for name in refs})
        assert all(filename.lower().endswith(".dxf") for filename in refs)
        assert sum(refs.values()) == expected["references"]
        assert expected["missing"] + expected["references"] == witness["records"]
        total_refs += expected["references"]
        total_unique += len(refs)
        total_missing += expected["missing"]
    assert total_refs == 64
    assert total_unique == 24
    assert total_missing == 62
    source = witness["verified_attachment"]
    assert source["indexed_filename"] == "400_140X257_107.dxf"
    assert source["attachment_file"] == "400_140X257_107(1).dxf"
    assert source["name_equivalence"] == "NOT_PROVEN_BY_FILENAME_ALONE"
    assert source["lower_region_ignored"] is True


def test_actual_original_switch_index_roundtrip_when_available():
    """CI need not bundle user original, but source-present replay must match."""
    source = os.environ.get("WHD_NFB_SWITCH_INDEX_CSV")
    if not source:
        pytest.skip("Original index not bundled in Git; supply WHD_NFB_SWITCH_INDEX_CSV")
    from hashlib import sha256

    path = Path(source)
    expected = _real_index_witness()
    assert sha256(path.read_bytes()).hexdigest() == expected["source_sha256"]
    catalog = unique_nfb_dxfs_from_switch_index(path)
    assert catalog.records_read == expected["records"]
    assert catalog.index_sha256 == expected["source_sha256"]
    assert catalog.diagnostics == ()
    assert len(catalog.sources) == expected["totals"]["unique_brand_filenames"]
    sources = {(entry.brand, entry.filename): entry for entry in catalog.sources}
    for brand, values in expected["by_brand"].items():
        found = {(item.filename): len(item.links) for item in catalog.sources if item.brand == brand}
        assert found == values["source_reference_counts"]
        assert all(entry.brand == brand for (b, _), entry in sources.items() if b == brand)
    assert sum(len(s.links) for s in catalog.sources) == 64


def test_no_matching_file_is_sentinel_not_corrupt_dxf_filename(tmp_path):
    path = tmp_path / "開關索引.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(("圖塊名稱", "士林", "深", "東元", "深", "伍菱", "深"))
        writer.writerow(("K1", "無對應檔案", "", "無對應檔案", "", "無對應檔案", ""))
        writer.writerow(("K2", "Example.DXF", "", "無對應檔案", "", "無對應檔案", ""))
    result = unique_nfb_dxfs_from_switch_index(path)
    assert result.records_read == 2
    assert len(result.sources) == 1
    assert result.sources[0].brand == "士林"
    assert result.sources[0].filename == "Example.DXF"
    assert result.diagnostics == ()
