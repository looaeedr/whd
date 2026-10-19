"""#1820 group42 absence: fail closed on absent-vs-explicit zero/negative one."""
from pathlib import Path

import ezdxf
import pytest

from tools.issue1820_cadcraft_dimension42_absence_patch import (
    ANCHORS, FIELD, default_constructors, fixtures, patch,
)


def test_dimension_constructor_marker_without_rewriting_other_structs():
    rust = (
        "pub struct Dimension {\n    pub measurement: f64,\n}\n"
        "impl Dimension {\n    fn getter(&self) -> f64 { self.measurement }\n}\n"
        "fn build() -> Dimension {\n"
        "    Dimension {\n        measurement: 0.0,\n        text: String::new(),\n"
        "    }\n}\n"
    )
    changed, n = default_constructors(rust)
    assert n == 1
    assert changed.count(FIELD) == 1
    assert "measurement: 0.0,\n        imported_group42_absent: false," in changed
    assert "pub measurement: f64,\n}" in changed


def test_patch_all_constructor_sites_without_touching_unknown_sources(tmp_path):
    for relative, (before, _after) in ANCHORS.items():
        p = tmp_path / relative
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(before, encoding="utf-8")
    # The patcher must successfully update new dimensions as false while
    # the imported dimension receives the actual source group's presence.
    for idx in range(9):
        p = tmp_path / "crates" / f"dummy_{idx}.rs"
        p.write_text("fn d() -> Dimension {\n  Dimension {\n    measurement: 0.0,\n  }\n}\n",encoding="utf-8")
    result = patch(tmp_path)
    assert result["updated_constructor_count"] == 9
    assert FIELD in (tmp_path / "crates/io/src/dxf_read.rs").read_text()
    assert FIELD in (tmp_path / "crates/io/src/dxf_write.rs").read_text()
    with pytest.raises(ValueError,match="ALREADY_PATCHED"):
        patch(tmp_path)


def test_absent_and_explicit_zero_are_not_conflated(tmp_path):
    result=fixtures(tmp_path)
    assert set(result)=={"absent","explicit_zero","explicit_negative_one"}
    for case, expected in (("absent",None),("explicit_zero",0),("explicit_negative_one",-1)):
        doc=ezdxf.readfile(tmp_path/(case+".dxf"))
        dimensions=list(doc.modelspace().query("DIMENSION"))
        assert len(dimensions)==1
        dim=dimensions[0]
        assert dim.dxf.get("actual_measurement")==expected
        assert tuple(dim.dxf.text_midpoint)==(80,55,0)
        assert dim.dxf.geometry.startswith("*D")
