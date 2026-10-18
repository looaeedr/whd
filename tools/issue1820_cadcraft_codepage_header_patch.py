"""#1820 CADCraft v0.8.0 DXF read→save codepage provenance probe.

Official v0.8 writes ANSI_1252 unconditionally for R2007+ DXF even if an
imported R2018 file declares a valid ANSI_950. Post-2007 DXF *text bytes* are
UTF-8 irrespective of the legacy codepage declaration. Preserve a valid
declaration as metadata, but never transcode Unicode text to legacy CP950.

Only patch isolated pinned CADCraft v0.8.0 source and test-only native binaries.
Do not change WHD manufacturing DXF or the installed CADCraft application.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

import ezdxf
from ezdxf.lldxf.encoding import decode_dxf_unicode

UPSTREAM = Path("crates/io/src/dxf_write.rs")
BEFORE = (
    "/// `$DWGCODEPAGE`: before 2007 the code page read from the file when CADCraft knows it (the text\n"
    "/// is ASCII with `\\U+XXXX` escapes, right in any code page, but the file keeps its declared one);\n"
    "/// otherwise, and from 2007 (UTF-8 text), `ANSI_1252`.\n"
    "fn code_page(d: &Drawing, version: Version) -> String {\n"
    '    let read = d.header.get("DWGCODEPAGE").and_then(HVal::as_str).map(str::trim).unwrap_or_default();\n'
    '    let known = read.is_ascii() && read.len() <= 32 && cadcraft_dxf::decode_code_page(b"", read).is_some();\n'
    '    if version < Version::R2007 && known { read.to_string() } else { "ANSI_1252".into() }\n'
    "}"
)
AFTER = (
    "/// `$DWGCODEPAGE`: preserve a known ASCII codepage label from imported DXF.\n"
    "/// In R2007+ the text payload is still encoded as UTF-8; the header label\n"
    "/// remains provenance metadata and must not be rewritten unrequested.\n"
    "/// Newly created drawings or invalid labels keep the ANSI_1252 fallback.\n"
    "fn code_page(d: &Drawing, _version: Version) -> String {\n"
    '    let read = d.header.get("DWGCODEPAGE").and_then(HVal::as_str).map(str::trim).unwrap_or_default();\n'
    '    let known = read.is_ascii() && read.len() <= 32 && cadcraft_dxf::decode_code_page(b"", read).is_some();\n'
    '    if known { read.to_string() } else { "ANSI_1252".into() }\n'
    "}"
)
CASES = {
    "r2018_ansi950": ("R2018", "ANSI_950"),
    "r2010_ansi950": ("R2010", "ANSI_950"),
    "r2018_ansi1252": ("R2018", "ANSI_1252"),
}
TEXT = "繁體測試尺寸AB12"


def patch_upstream(root: Path) -> dict:
    file = Path(root) / UPSTREAM
    content = file.read_text(encoding="utf-8")
    if content.count(BEFORE) != 1 or AFTER in content:
        raise ValueError("OFFICIAL_V080_CODEPAGE_SOURCE_ANCHOR_MISMATCH")
    output = content.replace(BEFORE, AFTER, 1)
    file.write_text(output, encoding="utf-8")
    return {"target":str(UPSTREAM),
            "original_sha256":hashlib.sha256(content.encode()).hexdigest(),
            "patched_sha256":hashlib.sha256(output.encode()).hexdigest()}


def fixture(directory: Path) -> dict:
    directory.mkdir(parents=True, exist_ok=True)
    created = {}
    for name,(version,codepage) in CASES.items():
        doc=ezdxf.new(version,units=ezdxf.units.MM)
        doc.modelspace().add_text(TEXT,dxfattribs={"height":2.5})
        path=directory/(name+".dxf")
        doc.saveas(path)
        b=path.read_bytes()
        if b.count(b"ANSI_1252")!=1:
            raise ValueError("UNEXPECTED_EZDXF_HEADER_LAYOUT")
        if codepage!="ANSI_1252":
            b=b.replace(b"ANSI_1252",codepage.encode("ascii"),1)
            path.write_bytes(b)
        loaded=ezdxf.readfile(path)
        if loaded.header.get("$DWGCODEPAGE")!=codepage:
            raise ValueError("CODEPAGE_SOURCE_FIXTURE_MISMATCH")
        actual=next(iter(loaded.modelspace().query("TEXT"))).dxf.text
        if decode_dxf_unicode(actual)!=TEXT:
            raise ValueError("SOURCE_TEXT_DECODE_MISMATCH")
        created[name]={"ACADVER":loaded.header.get("$ACADVER"),
                       "DWGCODEPAGE":loaded.header.get("$DWGCODEPAGE"),
                       "source_sha256":hashlib.sha256(path.read_bytes()).hexdigest()}
    return created


def verify(cli:Path,directory:Path,expected:str,evidence:Path)->bool:
    items=[]
    for name,(_version,codepage) in CASES.items():
        source=directory/(name+".dxf")
        target=directory/(name+"_"+expected+"_resaved.dxf")
        before=hashlib.sha256(source.read_bytes()).hexdigest()
        p=subprocess.run([str(cli),"run",str(source),"--save",str(target)],
                         capture_output=True,text=True,timeout=90)
        row={"case":name,"source_declared_codepage":codepage,"cli_exit":p.returncode}
        if p.returncode!=0 or not target.exists():
            row["error"]=p.stderr[-450:]
        else:
            a=ezdxf.readfile(source)
            b=ezdxf.readfile(target)
            ax=next(iter(a.modelspace().query("TEXT")))
            bx=next(iter(b.modelspace().query("TEXT")))
            row.update(saved_codepage=b.header.get("$DWGCODEPAGE"),
                       original_version=a.header.get("$ACADVER"),
                       saved_version=b.header.get("$ACADVER"),
                       text_equal=decode_dxf_unicode(ax.dxf.text)==decode_dxf_unicode(bx.dxf.text)==TEXT,
                       source_hash_unchanged=hashlib.sha256(source.read_bytes()).hexdigest()==before)
        items.append(row)
    if expected=="baseline":
        ok=all(row.get("cli_exit")==0 and row.get("text_equal") and row.get("source_hash_unchanged") for row in items)
        ok=ok and items[0].get("saved_codepage")=="ANSI_1252" and items[1].get("saved_codepage")=="ANSI_1252"
    elif expected=="patched":
        ok=all(row.get("cli_exit")==0 and row.get("text_equal") and row.get("source_hash_unchanged")
               and row.get("saved_codepage")==row.get("source_declared_codepage")
               and row.get("original_version")==row.get("saved_version") for row in items)
    else:raise ValueError("INVALID_EXPECTATION")
    result={"kind":"CADCRAFT_V080_VALID_CODEPAGE_METADATA_NATIVE_RED_GREEN",
            "expectation":expected,"status":"PASS" if ok else "FAIL","cases":items,
            "note":"R2010/R2018 Unicode text and declared codepage preservation; not DXF R12 support or visual font parity."}
    evidence.parent.mkdir(parents=True,exist_ok=True)
    evidence.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False))
    return ok


def main():
    parser=argparse.ArgumentParser()
    sub=parser.add_subparsers(dest="mode",required=True)
    p=sub.add_parser("patch");p.add_argument("root",type=Path)
    p=sub.add_parser("fixture");p.add_argument("directory",type=Path)
    p=sub.add_parser("verify");p.add_argument("cli",type=Path);p.add_argument("directory",type=Path)
    p.add_argument("--expect",choices=("baseline","patched"),required=True)
    p.add_argument("--json",type=Path,required=True)
    args=parser.parse_args()
    if args.mode=="patch":print(json.dumps(patch_upstream(args.root),ensure_ascii=False))
    elif args.mode=="fixture":print(json.dumps(fixture(args.directory),ensure_ascii=False))
    else:raise SystemExit(0 if verify(args.cli,args.directory,args.expect,args.json) else 2)


if __name__=="__main__":
    main()
