"""#1820 regress source-level DIMENSION midpoint/measurement patch behavior."""
from pathlib import Path

import ezdxf
import pytest

from tools.issue1820_cadcraft_dimension_import_patch import (
    MEASURE_AFTER, MEASURE_BEFORE, SOURCE_REL, TEXT_AFTER, TEXT_BEFORE,
    generate_fixture, patch_upstream,
)


def test_source_patch_surgical_and_does_not_double_apply(tmp_path):
    p = tmp_path / SOURCE_REL
    p.parent.mkdir(parents=True)
    text = "fn dimension() {\n" + TEXT_BEFORE + "\n" + MEASURE_BEFORE + "\n}\n"
    p.write_text(text, encoding="utf-8")
    patch_upstream(tmp_path)
    updated = p.read_text(encoding="utf-8")
    assert updated == text.replace(TEXT_BEFORE, TEXT_AFTER).replace(MEASURE_BEFORE, MEASURE_AFTER)
    with pytest.raises(ValueError, match="PATCH_ALREADY_PRESENT"):
        patch_upstream(tmp_path)


def test_reject_unknown_upstream_or_partial_patch(tmp_path):
    p = tmp_path / SOURCE_REL
    p.parent.mkdir(parents=True)
    p.write_text(TEXT_BEFORE, encoding="utf-8")
    with pytest.raises(ValueError, match="WRITER_ANCHOR_MISMATCH"):
        patch_upstream(tmp_path)
    assert p.read_text(encoding="utf-8") == TEXT_BEFORE


def test_real_dxf_style_fixture_preserves_original_group_11_and_42(tmp_path):
    info = generate_fixture(tmp_path)
    source = Path(info["path"])
    doc = ezdxf.readfile(source)
    dims = list(doc.modelspace().query("DIMENSION"))
    assert len(dims) == 1
    entity = dims[0]
    assert entity.dxf.get("geometry")
    assert entity.dxf.actual_measurement == -1
    assert tuple(entity.dxf.text_midpoint) == (80.0, 55.0, 0.0)
