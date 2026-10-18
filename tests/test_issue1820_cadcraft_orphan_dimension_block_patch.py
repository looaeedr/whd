"""#1820: protect orphan *D dimension graphics while still saving attached ones."""
from pathlib import Path
import ezdxf
import pytest
from tools.issue1820_cadcraft_orphan_dimension_block_patch import (
    BEFORE, AFTER, ORPHAN_NAME, UPSTREAM_RELATIVE,
    _block_signature, fixture, patch_upstream,
)


def test_patch_is_exact_narrow_fail_closed(tmp_path):
    source = tmp_path / UPSTREAM_RELATIVE
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("fn dim_block_plan() {\n" + BEFORE + "\n}\n", encoding="utf-8")
    before = source.read_text(encoding="utf-8")
    report = patch_upstream(tmp_path)
    assert source.read_text(encoding="utf-8") == before.replace(BEFORE, AFTER)
    assert report["original_sha256"] != report["patched_sha256"]
    with pytest.raises(ValueError, match="ANCHOR_MISMATCH"):
        patch_upstream(tmp_path)


def test_source_mismatch_does_not_modify_file(tmp_path):
    source = tmp_path / UPSTREAM_RELATIVE
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("no valid CADCraft source anchor", encoding="utf-8")
    with pytest.raises(ValueError, match="ANCHOR_MISMATCH"):
        patch_upstream(tmp_path)
    assert source.read_text(encoding="utf-8") == "no valid CADCraft source anchor"


def test_fixture_has_original_orphan_and_real_dimension(tmp_path):
    result = fixture(tmp_path)
    doc = ezdxf.readfile(result["source"])
    assert ORPHAN_NAME in doc.blocks
    assert _block_signature(doc.blocks[ORPHAN_NAME]) == (
        ("LINE", (2.0, 4.0, 0.0), (37.0, 41.0, 0.0)),
        ("CIRCLE", (7.0, 11.0, 0.0), 3.25),
    )
    assert result["attached_dimension_blocks"]
    assert ORPHAN_NAME not in result["attached_dimension_blocks"]
    assert result["attached_dimension_blocks"] == sorted(
        {d.dxf.geometry.upper() for d in doc.modelspace().query("DIMENSION")}
    )
