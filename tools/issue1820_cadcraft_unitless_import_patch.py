"""#1820 CADCraft v0.8.0 imported-DXF header preservation probe.

Experimental upstream source patch, never a patch to WHD manufacturing code.
Only operate on a separately checked-out CADCraft v0.8.0 source tree.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import ezdxf

# CLI entrypoint also runs as python tools/...py outside a python -m package.
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from tools.issue1820_cadcraft_dxf_fidelity_gate import audit

UPSTREAM_RELATIVE = Path("crates/io/src/dxf_read.rs")
BEFORE = "    let mut d = Drawing::new_imperial();\n    d.layouts.clear();"
AFTER = (
    "    let mut d = Drawing::new_imperial();\n"
    "    // Imported DXF header values must not inherit New Drawing's inch defaults.\n"
    "    // The HEADER parser restores explicit values, including zero, below.\n"
    "    // Keep absent INSUNITS / MEASUREMENT absent in a read-then-save roundtrip.\n"
    '    d.header.vars.remove("INSUNITS");\n'
    '    d.header.vars.remove("MEASUREMENT");\n'
    "    d.layouts.clear();"
)
MATRIX = {
    "absent_both": (None, None),
    "absent_units_explicit_metric": (None, 1),
    "explicit_unitless": (0, 0),
    "explicit_inch": (1, 0),
    "explicit_mm": (4, 1),
    "explicit_mm_no_measurement": (4, None),
}


def patch_upstream(source_tree: Path) -> dict:
    source = source_tree / UPSTREAM_RELATIVE
    data = source.read_text(encoding="utf-8")
    if AFTER in data:
        raise ValueError("CADCRAFT_UPSTREAM_PATCH_ALREADY_PRESENT")
    if data.count(BEFORE) != 1:
        raise ValueError("CADCRAFT_V080_SOURCE_ANCHOR_MISMATCH")
    updated = data.replace(BEFORE, AFTER, 1)
    source.write_text(updated, encoding="utf-8")
    return {
        "patched_path": str(source),
        "original_sha256": hashlib.sha256(data.encode()).hexdigest(),
        "patched_sha256": hashlib.sha256(updated.encode()).hexdigest(),
        "scope": "CADCraft external DXF read initialization, not new-drawing defaults",
    }


def _set_or_remove_header(doc, name: str, value: int | None):
    key = "$" + name
    if value is None:
        if doc.header.get(key) is not None:
            del doc.header[key]
    else:
        doc.header[key] = value


def generate_fixtures(folder: Path):
    folder.mkdir(parents=True, exist_ok=True)
    for name, (units, measurement) in MATRIX.items():
        doc = ezdxf.new("R2010", units=ezdxf.units.MM)
        doc.layers.new("CUTTING", dxfattribs={"color": 3})
        model = doc.modelspace()
        model.add_lwpolyline(
            [(0, 0), (100, 0), (100, 80), (0, 80)],
            close=True, dxfattribs={"layer": "CUTTING"},
        )
        model.add_circle((25, 30), radius=3.2, dxfattribs={"layer": "CUTTING"})
        model.add_arc((65, 30), radius=7, start_angle=15, end_angle=120)
        _set_or_remove_header(doc, "INSUNITS", units)
        _set_or_remove_header(doc, "MEASUREMENT", measurement)
        path = folder / f"{name}_source.dxf"
        doc.saveas(path)
        actual = ezdxf.readfile(path)
        if (actual.header.get("$INSUNITS"),
                actual.header.get("$MEASUREMENT")) != (units, measurement):
            raise AssertionError(f"FIXTURE_HEADER_MISMATCH:{name}")
    return {"cases": sorted(MATRIX), "location": str(folder)}


def exercise(cli: Path, folder: Path, expectation: str, evidence: Path):
    observations = []
    for name, (units, measurement) in MATRIX.items():
        source = folder / f"{name}_source.dxf"
        target = folder / f"{name}_{expectation}_saved.dxf"
        before = hashlib.sha256(source.read_bytes()).hexdigest()
        result = subprocess.run(
            [str(cli), "run", str(source), "--save", str(target)],
            capture_output=True, text=True, timeout=90, check=False,
        )
        row = {"case": name, "original_units": units, "original_measurement": measurement,
               "cli_returncode": result.returncode}
        if result.returncode != 0 or not target.is_file():
            row["failure"] = "CADCRAFT_CLI_FAILED"
            row["stderr_tail"] = result.stderr[-500:]
        else:
            diff = audit(source, target)
            row["fidelity"] = diff["result"]
            row["failures"] = diff["failures"]
            row["saved_headers"] = diff["header"]
        row["source_unchanged"] = hashlib.sha256(source.read_bytes()).hexdigest() == before
        observations.append(row)

    if expectation == "patched":
        passed = all(
            row.get("fidelity") == "PASS" and row["source_unchanged"]
            for row in observations
        )
    elif expectation == "baseline":
        # v0.8.0 RED evidence: absent header gets synthetic inch unit.
        absent = next(row for row in observations if row["case"] == "absent_both")
        passed = (
            "$INSUNITS_DRIFT" in absent.get("failures", [])
            and absent["saved_headers"]["$INSUNITS"]["resaved"] == 1
            and all(row["source_unchanged"] for row in observations)
            and all(row.get("cli_returncode") == 0 for row in observations)
        )
    else:
        raise ValueError("INVALID_EXPECTATION")

    report = {
        "kind": "CADCRAFT_V080_UNIT_HEADER_NATIVE_CLI_RED_GREEN",
        "upstream_tag": "v0.8.0",
        "expectation": expectation,
        "status": "PASS" if passed else "FAIL",
        "rows": observations,
        "scope": "Header absence/value and geometry/blocks/layers. Not real customer DXF full parity.",
    }
    evidence.parent.mkdir(parents=True, exist_ok=True)
    evidence.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return passed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    patch = commands.add_parser("patch")
    patch.add_argument("source_tree", type=Path)
    fixture = commands.add_parser("fixtures")
    fixture.add_argument("directory", type=Path)
    verify = commands.add_parser("verify")
    verify.add_argument("cli", type=Path)
    verify.add_argument("directory", type=Path)
    verify.add_argument("--expect", choices=("baseline", "patched"), required=True)
    verify.add_argument("--json", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "patch":
        print(json.dumps(patch_upstream(args.source_tree), ensure_ascii=False))
    elif args.command == "fixtures":
        print(json.dumps(generate_fixtures(args.directory), ensure_ascii=False))
    else:
        raise SystemExit(0 if exercise(args.cli, args.directory, args.expect, args.json) else 2)


if __name__ == "__main__":
    main()
