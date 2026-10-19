"""#1820: codepage metadata must survive save without changing Unicode text."""
import ezdxf
import pytest

from tools.issue1820_cadcraft_codepage_header_patch import (
    BEFORE, AFTER, TEXT, UPSTREAM, CASES,
    fixture, patch_upstream,
)


def test_codepage_patch_exact_source_guard(tmp_path):
    target=tmp_path/UPSTREAM
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text("fn marker() {}\n"+BEFORE+"\n",encoding="utf-8")
    before=target.read_text(encoding="utf-8")
    report=patch_upstream(tmp_path)
    assert target.read_text(encoding="utf-8")==before.replace(BEFORE,AFTER)
    assert report["original_sha256"]!=report["patched_sha256"]
    with pytest.raises(ValueError,match="ANCHOR_MISMATCH"):
        patch_upstream(tmp_path)


def test_unexpected_upstream_source_fails_without_write(tmp_path):
    target=tmp_path/UPSTREAM
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text("DIFFERENT UPSTREAM VERSION",encoding="utf-8")
    with pytest.raises(ValueError,match="ANCHOR_MISMATCH"):
        patch_upstream(tmp_path)
    assert target.read_text(encoding="utf-8")=="DIFFERENT UPSTREAM VERSION"


def test_codepage_fixture_preserves_2010_2018_chinese_text(tmp_path):
    made=fixture(tmp_path)
    assert set(made)==set(CASES)
    for name,(_version,codepage) in CASES.items():
        doc=ezdxf.readfile(tmp_path/(name+".dxf"))
        assert doc.header.get("$DWGCODEPAGE")==codepage
        assert doc.header.get("$ACADVER")==made[name]["ACADVER"]
        texts=list(doc.modelspace().query("TEXT"))
        assert len(texts)==1
        assert texts[0].dxf.text==TEXT
