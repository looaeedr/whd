"""#1820 CADCraft upstream source-patch safety + synthetic DXF header cases."""
from pathlib import Path

import ezdxf
import pytest

from tools.issue1820_cadcraft_unitless_import_patch import (
    AFTER, BEFORE, MATRIX, UPSTREAM_RELATIVE,
    generate_fixtures, patch_upstream,
)


def test_upstream_patch_changes_only_reader_initialization(tmp_path):
    source = tmp_path / UPSTREAM_RELATIVE
    source.parent.mkdir(parents=True)
    text = "pub fn read() {\n" + BEFORE + "\n}\n"
    source.write_text(text, encoding="utf-8")
    result = patch_upstream(tmp_path)
    assert source.read_text(encoding="utf-8") == text.replace(BEFORE, AFTER)
    assert result["original_sha256"] != result["patched_sha256"]
    with pytest.raises(ValueError, match="PATCH_ALREADY_PRESENT"):
        patch_upstream(tmp_path)


def test_upstream_patch_fails_closed_on_source_mismatch(tmp_path):
    source = tmp_path / UPSTREAM_RELATIVE
    source.parent.mkdir(parents=True)
    source.write_text("pub fn read() {}", encoding="utf-8")
    with pytest.raises(ValueError, match="SOURCE_ANCHOR_MISMATCH"):
        patch_upstream(tmp_path)
    assert source.read_text(encoding="utf-8") == "pub fn read() {}"


def test_fixture_header_matrix_and_geometry_are_independent(tmp_path):
    result = generate_fixtures(tmp_path)
    assert set(result["cases"]) == set(MATRIX)
    for name, expected in MATRIX.items():
        source = tmp_path / f"{name}_source.dxf"
        assert source.is_file()
        doc = ezdxf.readfile(source)
        assert (
            doc.header.get("$INSUNITS"),
            doc.header.get("$MEASUREMENT"),
        ) == expected
        assert sorted(e.dxftype() for e in doc.modelspace()) == [
            "ARC", "CIRCLE", "LWPOLYLINE"
        ]
        assert doc.layers.get("CUTTING").dxf.color == 3
