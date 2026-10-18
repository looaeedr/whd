"""#1820 experimental CADCraft v0.8.0 DXF DIMENSION group42 absence repair.

Patch a separate, pinned CADCraft checkout AFTER the #1941/#1942 patches.
No modification to the WHD product application or its manufacturing geometry.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import ezdxf

FIELD = "imported_group42_absent"
MODEL = Path("crates/doc/src/entity.rs")
READ = Path("crates/io/src/dxf_read.rs")
WRITE = Path("crates/io/src/dxf_write.rs")
ANCHORS = {
    MODEL: ("    pub measurement: f64,", "    pub measurement: f64,\n    /// The imported DIMENSION omitted DXF group 42.\n    #[serde(default)]\n    pub imported_group42_absent: bool,"),
    READ: ("                measurement: t.fd(42, 0.0),", "                measurement: t.fd(42, 0.0),\n                imported_group42_absent: t.f(42).is_none(),"),
    WRITE: (
        "w.f(42, if dm.block.is_some() { dm.measurement } else { g.measurement });",
        "if !(dm.block.is_some() && dm.imported_group42_absent) {\n                w.f(42, if dm.block.is_some() { dm.measurement } else { g.measurement });\n            }",
    ),
}
RX = re.compile(r"(?<!struct )(?<!impl )\bDimension\s*\{")
FIELD_LINE = re.compile(r"(?m)^([ \t]*)measurement\s*:[^\n]*,[ \t]*$")


def default_constructors(text: str):
    inserts = []
    for m in RX.finditer(text):
        start = m.end()-1
        depth = 0
        end = -1
        for pos in range(start,len(text)):
            if text[pos] == "{": depth += 1
            elif text[pos] == "}":
                depth -= 1
                if depth == 0:
                    end = pos
                    break
        if end == -1:
            raise ValueError("UNMATCHED_DIMENSION_LITERAL_BRACE")
        body = text[start+1:end]
        if FIELD in body: continue
        candidates = list(FIELD_LINE.finditer(body))
        if len(candidates) > 1: raise ValueError("AMBIGUOUS_DIMENSION_LITERAL")
        if candidates:
            hit=candidates[0]
            inserts.append((start+1+hit.end(), "\n"+hit.group(1)+FIELD+": false,"))
    for pos, addition in sorted(inserts,reverse=True):
        text=text[:pos]+addition+text[pos:]
    return text,len(inserts)


def patch(tree: Path):
    tree=Path(tree)
    updates={}
    for name,(old,new) in ANCHORS.items():
        path=tree/name
        content=path.read_text(encoding="utf-8")
        if content.count(old)!=1 or FIELD in content:
            raise ValueError("EXPECTED_UPSTREAM_PATCH_ANCHOR_MISSING_OR_ALREADY_PATCHED: "+str(name))
        updates[path]=content.replace(old,new,1)
    constructors=0
    for folder in ("crates","apps"):
        for file in sorted((tree/folder).rglob("*.rs")):
            before=updates.get(file)
            if before is None: before=file.read_text(encoding="utf-8")
            if "Dimension {" not in before: continue
            after,n=default_constructors(before)
            if n:
                updates[file]=after
                constructors+=n
    if not 8<=constructors<=100:
        raise ValueError("UNEXPECTED_CONSTRUCTOR_COUNT: "+str(constructors))
    # No writes before all expected source anchors and constructors were verified.
    for file,data in updates.items():
        if file.read_text(encoding="utf-8")!=data:
            file.write_text(data,encoding="utf-8")
    return {"patched_sources":[str(p.relative_to(tree)) for p in updates],
            "updated_constructor_count":constructors,
            "source_hashes":{str(p.relative_to(tree)):hashlib.sha256(p.read_bytes()).hexdigest() for p in updates}}


def fixtures(directory: Path):
    directory.mkdir(parents=True,exist_ok=True)
    out={}
    for name,value in (("absent",None),("explicit_zero",0.0),("explicit_negative_one",-1.0)):
        doc=ezdxf.new("R2010",units=ezdxf.units.MM)
        dim=doc.modelspace().add_linear_dim(base=(80,22),p1=(0,0),p2=(180,0),angle=0)
        dim.render()
        d=dim.dimension
        d.dxf.text_midpoint=(80,55,0)
        if value is None:d.dxf.discard("actual_measurement")
        else:d.dxf.actual_measurement=value
        file=directory/(name+".dxf");doc.saveas(file)
        reload=next(iter(ezdxf.readfile(file).modelspace().query("DIMENSION")))
        if reload.dxf.get("actual_measurement")!=value:
            raise ValueError("BROKEN_FIXTURE: "+name)
        out[name]=dict(path=str(file),value=value)
    return out


def verify(cli:Path,folder:Path,expected:str,json_path:Path):
    results=[]
    for name in ("absent","explicit_zero","explicit_negative_one"):
        a=folder/(name+".dxf")
        b=folder/(name+"_"+expected+"_saved.dxf")
        digest=hashlib.sha256(a.read_bytes()).hexdigest()
        p=subprocess.run([str(cli),"run",str(a),"--save",str(b)],capture_output=True,text=True,timeout=90)
        row={"name":name,"exit":p.returncode,"source_unchanged":hashlib.sha256(a.read_bytes()).hexdigest()==digest}
        if p.returncode==0 and b.exists():
            before=next(iter(ezdxf.readfile(a).modelspace().query("DIMENSION")))
            after=next(iter(ezdxf.readfile(b).modelspace().query("DIMENSION")))
            x=before.dxf.get("actual_measurement");y=after.dxf.get("actual_measurement")
            row.update(before=x,after=y,presence_equal=(x is None)==(y is None),value_equal=x==y,
                midpoint_equal=all(abs(float(z)-float(w))<1e-6 for z,w in zip(before.dxf.text_midpoint,after.dxf.text_midpoint)))
        else:row["error"]=p.stderr[-500:]
        results.append(row)
    if expected=="baseline":
        ok=results[0].get("presence_equal") is False and all(x["source_unchanged"] for x in results)
    elif expected=="patched":
        ok=all(x.get("presence_equal") and x.get("value_equal") and x.get("midpoint_equal") and x["source_unchanged"] for x in results)
    else: raise ValueError("EXPECTED_BASELINE_OR_PATCHED")
    report={"status":"PASS" if ok else "FAIL","expectation":expected,"cases":results,
            "scope":"Group42 absent-vs-explicit zero/negative one and group11 midpoint; not full DXF parity"}
    json_path.parent.mkdir(parents=True,exist_ok=True)
    json_path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False))
    return ok


if __name__=="__main__":
    p=argparse.ArgumentParser()
    s=p.add_subparsers(dest="op",required=True)
    c=s.add_parser("patch");c.add_argument("tree",type=Path)
    c=s.add_parser("fixtures");c.add_argument("folder",type=Path)
    c=s.add_parser("verify");c.add_argument("cli",type=Path);c.add_argument("folder",type=Path)
    c.add_argument("--expect",choices=("baseline","patched"),required=True)
    c.add_argument("--json",type=Path,required=True)
    a=p.parse_args()
    if a.op=="patch":print(json.dumps(patch(a.tree),ensure_ascii=False))
    elif a.op=="fixtures":print(json.dumps(fixtures(a.folder),ensure_ascii=False))
    else:raise SystemExit(0 if verify(a.cli,a.folder,a.expect,a.json) else 2)
