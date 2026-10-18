"""#1820 CADCraft v0.8.0 unedited dimension DXF field-preservation probe.

Patches only an external pinned CADCraft upstream source checkout.
This DOES NOT approve reimport of CADCraft DXF into WHD manufacturing.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import ezdxf

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SOURCE_REL = Path("crates/io/src/dxf_write.rs")
TEXT_BEFORE = "w.p(11, if dm.user_text_pos { dm.text_mid } else { g.text_pos.to3(0.0) });"
TEXT_AFTER = (
    "w.p(11, if dm.user_text_pos || dm.block.is_some() "
    "{ dm.text_mid } else { g.text_pos.to3(0.0) });"
)
MEASURE_BEFORE = "w.f(42, g.measurement);"
MEASURE_AFTER = "w.f(42, if dm.block.is_some() { dm.measurement } else { g.measurement });"


def patch_upstream(root: Path) -> dict:
    path = root / SOURCE_REL
    text = path.read_text(encoding="utf-8")
    if TEXT_AFTER in text or MEASURE_AFTER in text:
        raise ValueError("DIMENSION_PATCH_ALREADY_PRESENT_OR_PARTIAL")
    if text.count(TEXT_BEFORE) != 1 or text.count(MEASURE_BEFORE) != 1:
        raise ValueError("CADCRAFT_V080_DIMENSION_WRITER_ANCHOR_MISMATCH")
    updated = text.replace(TEXT_BEFORE, TEXT_AFTER, 1)
    updated = updated.replace(MEASURE_BEFORE, MEASURE_AFTER, 1)
    path.write_text(updated, encoding="utf-8")
    return {
        "path": str(path),
        "before_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "after_sha256": hashlib.sha256(updated.encode()).hexdigest(),
        "scope": "Only group 11/42 of still-linked original DIMENSIONs; new/edited dims still derived",
    }


def generate_fixture(folder: Path) -> dict:
    folder.mkdir(parents=True, exist_ok=True)
    file = folder / "unaltered_dimension_source.dxf"
    doc = ezdxf.new("R2010", units=ezdxf.units.MM)
    dim = doc.modelspace().add_linear_dim(
        base=(80, 22), p1=(0, 0), p2=(180, 0), angle=0,
    )
    dim.render()
    entity = dim.dimension
    entity.dxf.text_midpoint = (80, 55, 0)
    entity.dxf.actual_measurement = -1.0
    doc.saveas(file)
    check = ezdxf.readfile(file)
    actual = next(e for e in check.modelspace() if e.dxftype() == "DIMENSION")
    if (float(actual.dxf.actual_measurement) != -1
            or abs(float(actual.dxf.text_midpoint.y) - 55) > 1e-6
            or not actual.dxf.get("geometry")):
        raise ValueError("DIMENSION_FIXTURE_NOT_AS_STORED")
    return {"path": str(file), "source_sha256": hashlib.sha256(file.read_bytes()).hexdigest()}


def verify(cli: Path, folder: Path, expected: str, output: Path):
    source = folder / "unaltered_dimension_source.dxf"
    target = folder / f"dimension_{expected}_save.dxf"
    before_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    p = subprocess.run(
        [str(cli), "run", str(source), "--save", str(target)],
        capture_output=True, text=True, check=False, timeout=80,
    )
    row = {
        "cli_returncode": p.returncode,
        "source_sha256": before_hash,
        "source_unchanged": hashlib.sha256(source.read_bytes()).hexdigest() == before_hash,
        "status": "FAIL",
    }
    if p.returncode == 0 and target.exists():
        original = ezdxf.readfile(source)
        saved = ezdxf.readfile(target)
        a = next(e for e in original.modelspace() if e.dxftype() == "DIMENSION")
        b = next(e for e in saved.modelspace() if e.dxftype() == "DIMENSION")
        amid, bmid = a.dxf.text_midpoint, b.dxf.text_midpoint
        position_preserved = all(abs(float(x) - float(y)) <= 1e-6 for x, y in zip(amid, bmid))
        measure_preserved = abs(float(a.dxf.actual_measurement) - float(b.dxf.actual_measurement)) <= 1e-6
        row["position_preserved"] = position_preserved
        row["measurement_preserved"] = measure_preserved
        row["source_text_midpoint"] = list(amid)
        row["saved_text_midpoint"] = list(bmid)
        row["source_actual_measurement"] = float(a.dxf.actual_measurement)
        row["saved_actual_measurement"] = float(b.dxf.actual_measurement)
        row["same_model_entity_count"] = len(original.modelspace()) == len(saved.modelspace())
        if expected == "official":
            row["status"] = "PASS" if (
                (not position_preserved or not measure_preserved)
                and row["same_model_entity_count"] and row["source_unchanged"]
            ) else "FAIL"
        elif expected == "patched":
            row["status"] = "PASS" if (
                position_preserved and measure_preserved
                and row["same_model_entity_count"] and row["source_unchanged"]
            ) else "FAIL"
    else:
        row["stderr_tail"] = p.stderr[-400:]
    row["expected"] = expected
    row["caution"] = "Only DIMENSION group 11/42 behavior, not whole DXF fidelity."
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(row, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(row, ensure_ascii=False))
    return row["status"] == "PASS"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("patch")
    p.add_argument("upstream_tree", type=Path)
    p = sub.add_parser("fixture")
    p.add_argument("outdir", type=Path)
    p = sub.add_parser("verify")
    p.add_argument("cli", type=Path)
    p.add_argument("fixture_dir", type=Path)
    p.add_argument("--expect", choices=("official", "patched"), required=True)
    p.add_argument("--json", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "patch":
        print(json.dumps(patch_upstream(args.upstream_tree)))
    elif args.command == "fixture":
        print(json.dumps(generate_fixture(args.outdir)))
    else:
        raise SystemExit(0 if verify(args.cli, args.fixture_dir, args.expect, args.json) else 2)


if __name__ == "__main__":
    main()
