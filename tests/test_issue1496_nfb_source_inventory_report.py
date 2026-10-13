# -*- coding: utf-8 -*-
"""#1496: canonical indexed-source coverage never conflates missing and 0."""
from __future__ import annotations

import csv
from hashlib import sha256
import json
from zipfile import ZipFile

import ezdxf
import pytest

from tools.nfb_source_audit import (
    DEFAULT_INDEX, DEFAULT_PINS, DEFAULT_SOURCE_ROOT,
    build_source_coverage_report, main,
)
from ae_engine.receiving_nfb_index_sources import unique_nfb_dxfs_from_switch_index


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


def test_zip_only_indexed_source_is_audited_in_temporary_tree(tmp_path):
    index, root, pins, original = _case(tmp_path)
    archive = tmp_path / "source-archive.zip"
    replacement = ezdxf.new("R2010")
    replacement.modelspace().add_circle(
        (17, 35), 7, dxfattribs={"color": 212},
    )
    staging = tmp_path / "zip-member.dxf"
    replacement.saveas(staging)
    with ZipFile(archive, "w") as zipfile:
        zipfile.write(staging, "READ_ONLY_DXF_BUNDLE/TECO/C.dxf")
    report = build_source_coverage_report(
        index, source_root=root, pin_path=pins, archive_path=archive,
    )
    by_name = {(row["brand"], row["indexed_filename"]): row
               for row in report["records"]}
    recovered = by_name[("東元", "C.dxf")]
    assert recovered["source_storage"] == "ARCHIVE_SINGLE_EXACT_BASENAME_TEMP"
    assert recovered["status"] == "SOURCE_OBSERVED_UNCERTIFIED"
    assert recovered["source_sha256"] == sha256(staging.read_bytes()).hexdigest()
    assert (recovered["color_30_entities"], recovered["color_150_entities"],
            recovered["color_212_entities"]) == (0, 0, 1)
    assert not (root / "東元" / "C.dxf").exists()
    assert original.is_file()
    assert report["totals"]["observed_uncertified"] == 2
    assert report["totals"]["unknown"] == 2


def test_ambiguous_zip_basenames_do_not_guess_brand(tmp_path):
    index, root, pins, _ = _case(tmp_path)
    source = root / "士林" / "A.dxf"
    with ZipFile(tmp_path / "ambiguous.zip", "w") as z:
        z.write(source, "part-a/TECO/C.dxf")
        z.write(source, "part-b/TECO/C.dxf")
    report = build_source_coverage_report(
        index, source_root=root, pin_path=pins,
        archive_path=tmp_path / "ambiguous.zip",
    )
    row = next(x for x in report["records"]
               if x["brand"] == "東元" and x["indexed_filename"] == "C.dxf")
    assert row["source_storage"] == "ARCHIVE_AMBIGUOUS_UNKNOWN"
    assert row["status"] == "SOURCE_MISSING_UNKNOWN"
    assert row["color_30_entities"] is None
    assert row["color_150_entities"] is None
    assert row["color_212_entities"] is None


def test_24_real_local_dxf_observations_are_traceable_but_not_certified():
    """#1496 local v0.7 source files and v0.6 ZIP are NOT user raw originals.

    The fixed witness carries 24 actual DXF hashes and native observed colors.
    CI verifies the model/index links, not the unavailable original bytes.
    """
    path = (
        DEFAULT_INDEX.parents[3] / "tests" / "fixtures"
        / "receiving_nfb_24_local_native_observations.json"
    )
    receipt = json.loads(path.read_text(encoding="utf-8"))
    index = unique_nfb_dxfs_from_switch_index(DEFAULT_INDEX)
    assert receipt["schema"] == "WHD_NFB_24_LOCAL_NATIVE_SOURCE_OBSERVATIONS_V1"
    assert receipt["index_sha256"] == index.index_sha256
    assert receipt["index_rows"] == index.records_read == 42
    assert receipt["indexed_unique_sources"] == len(index.sources) == 24
    assert receipt["index_references"] == 64
    assert receipt["single_color150_rectangle_count"] == 22
    assert receipt["missing_color150_count"] == 1
    assert receipt["nonrectangle_color150_count"] == 1
    assert receipt["source_pin_sha_mismatch_count"] == 1
    records = {
        (r["brand"], r["indexed_filename"].casefold()): r
        for r in receipt["records"]
    }
    assert len(receipt["records"]) == len(records) == 24
    assert set(records) == {
        (r.brand, r.filename.casefold()) for r in index.sources
    }
    for source in index.sources:
        row = records[source.brand, source.filename.casefold()]
        assert [(x["csv_row"], x["model_key"]) for x in row["model_links"]] == [
            (x.row_number, x.model_key) for x in source.links
        ]
        assert len(row["observed_source_sha256"]) == 64
        assert row["source_parsing_status"] == "SOURCE_OBSERVED_UNCERTIFIED"
        assert row["manufacturing_ready"] is False
        assert row["entity_count"] == sum(row["entity_type_counts"].values())
        for color in ("30", "150", "212"):
            count = row["effective_aci_entity_counts"][color]
            assert type(count) is int and 0 <= count <= row["entity_count"]
        assert len(row["color150_entities"]) == row["effective_aci_entity_counts"]["150"]
        # A sampled 150 contour is a source candidate, not a manufacturing
        # pivot identity or a method for silently flattening 6-vertex shapes.
        if row["candidate_rectangle"] is not None:
            assert row["effective_aci_entity_counts"]["150"] == 1
            assert row["candidate_rectangle"]["size_mm"][0] > 0
            assert row["candidate_rectangle"]["size_mm"][1] > 0
    missing = records[("士林", "bh_25x95.dxf")]
    assert missing["effective_aci_entity_counts"]["150"] == 0
    assert missing["candidate_rectangle"] is None
    complex_source = records[("士林", "bh_25x95_02.dxf")]
    assert complex_source["color150_entities"][0]["vertices"] == 6
    assert complex_source["candidate_rectangle"] is None
    teco = records[("東元", "400_type.dxf")]
    assert teco["source_storage"] == "ARCHIVE_V06_TEMP"
    assert teco["manufacturing_ready"] is False
    # A normalized local file with the same filename does NOT override
    # the separately proven customer byte-original pin in GitHub.
    shihlin400 = records[("士林", "400_140x257_107.dxf")]
    assert shihlin400["pinned_original_matches"] is False
    assert shihlin400["observed_source_sha256"] == (
        "80fd96bf10458b830e049d93c2a259b52aec9dd07d8fc594ff7752ffb47a77ea"
    )
    assert shihlin400["pinned_original_sha256"] == (
        "8daecaacacb9683c1436d29aa75fbba85c09d54536b92945fbaad06e049fadf3"
    )
    assert shihlin400["candidate_rectangle"]["handle"] == "585"
    assert not DEFAULT_SOURCE_ROOT.is_relative_to(DEFAULT_INDEX.parent)
