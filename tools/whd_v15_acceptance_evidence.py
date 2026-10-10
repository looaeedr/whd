"""Bind all v1.5 CPR/AC rows to fresh, successful Product Regression cases."""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "docs/superpowers/verification/issue1469-v15-acceptance-matrix.json"
LIBRARY = ROOT / "個人AI檔案庫/第二層_專案與SOP"


def verify(junit_path):
    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
    spec = ROOT / matrix["spec"]
    if hashlib.sha256(spec.read_bytes()).hexdigest() != matrix["spec_sha256"]:
        raise ValueError("v1.5 spec changed; requirement mapping needs review")
    expected = {f"{kind}-{n:02}" for kind, size in (("CPR", 20), ("AC", 32)) for n in range(1, size+1)}
    ids = [row["id"] for row in matrix["rows"]]
    if set(ids) != expected or len(ids) != len(expected):
        raise ValueError("CPR/AC mapping is incomplete or duplicated")
    cases = ET.parse(junit_path).findall(".//testcase")
    if not cases or any(c.find(tag) is not None for c in cases for tag in ("failure", "error", "skipped")):
        raise ValueError("fresh JUnit must contain successful cases only")
    # Compare the full canonical collection, including every parameterized
    # case. One passing family/anchor cannot stand in for the whole matrix.
    sys.path.insert(0, str(ROOT))
    from tools.product_ci_regression import PYTEST_PATHS
    collected = subprocess.check_output([sys.executable, "-m", "pytest", "--collect-only", "-q", *PYTEST_PATHS],
        cwd=ROOT, text=True)
    expected_cases = {line.strip() for line in collected.splitlines() if line.startswith("tests/") and "::" in line}
    actual_cases = [case.get("classname", "").replace(".", "/") + ".py::" + case.get("name", "") for case in cases]
    if set(actual_cases) != expected_cases or len(actual_cases) != len(expected_cases):
        raise ValueError("JUnit is not the full canonical parameterized collection")
    results = {}
    for row in matrix["rows"]:
        if not row["tests"]:
            raise ValueError(f"missing tests for {row['id']}")
        matches = []
        for nodeid in row["tests"]:
            path, function = nodeid.split("::")
            classname = path.removesuffix(".py").replace("/", ".")
            found = [case for case in cases if case.get("classname") == classname
                and case.get("name", "").split("[", 1)[0] == function]
            if not found:
                raise ValueError(f"{row['id']} has no fresh case for {nodeid}")
            matches.extend(f"{path}::{case.get('name')}" for case in found)
        results[row["id"]] = sorted(set(matches))
    authority = (LIBRARY / "09_WHD_Canonical_Authority_Map.md").read_text(encoding="utf-8")
    current = Counter(re.findall(r"WHD_AUTHORITY contract=(\S+) role=CURRENT", authority))
    if any(count != 1 for count in current.values()):
        raise ValueError("duplicate CURRENT authority contract")
    required = {"quantity-version-state", "receiving-mode-session", "receiving-quantity-common-box",
        "custom-part-identity", "quantity-physical-bom", "manufacturing-equivalence", "quantity-check-annotation"}
    if not required.issubset(current):
        raise ValueError("missing durable v1.5 authority contracts")
    ledger = LIBRARY / "06_踩坑記錄與防錯經驗庫.md"
    if "ISSUE1469_V15_INTEGRATION_PITFALL" not in ledger.read_text(encoding="utf-8"):
        raise ValueError("missing durable v1.5 pitfall writeback")
    dependency_path = ROOT / "docs/superpowers/verification/issue1469-child-delivery-readback.json"
    dependencies = json.loads(dependency_path.read_text(encoding="utf-8"))
    children = dependencies["children"]
    if len(children) != 9 or {row["issue"] for row in children} != set(range(1460, 1469)):
        raise ValueError("missing child delivery receipts")
    for row in children:
        if not row["merged"] or row["base"] != "localX" or not row["merge_sha"]:
            raise ValueError("child PR is not merged to localX")
        if not any(ci["queried_head"] == row["head"] and ci["status"] == "completed"
            and ci["conclusion"] == "success" for ci in row["ci"]):
            raise ValueError("child required exact-head CI is not successful")
    sources = {matrix["spec"], MATRIX.relative_to(ROOT).as_posix(),
        dependency_path.relative_to(ROOT).as_posix(),
        (LIBRARY / "09_WHD_Canonical_Authority_Map.md").relative_to(ROOT).as_posix(),
        ledger.relative_to(ROOT).as_posix(), "phase6_settings_contracts.py"}
    sources.update(nodeid.split("::")[0] for row in matrix["rows"] for nodeid in row["tests"])
    profiles = []
    for case in cases:
        output = case.findtext("system-out", "")
        for label in ("QUANTITY_UI_STRESS", "QUANTITY_BOM_PERFORMANCE", "RECEIVING_COMMON_BOX_PROFILE", "V15_ACTUAL_MULTIBAY_2D_PROFILE"):
            marker = label + "="
            if marker in output:
                value, _ = json.JSONDecoder().raw_decode(output.split(marker, 1)[1])
                profiles.append(dict(case=case.get("name"), metric=label, values=value))
    multi_profiles = [p["values"] for p in profiles if p["metric"] == "V15_ACTUAL_MULTIBAY_2D_PROFILE"]
    if len(multi_profiles) != 1 or any(value != 0 for key, value in multi_profiles[0].items() if key != "wall_seconds"):
        raise ValueError("missing or nonzero actual GUI overlay-only profile")
    return dict(schema="WHD_V15_ACCEPTANCE_RESULT_V1", result="GREEN",
        passed_cases=len(cases), requirements=results, gui_profiles=profiles,
        junit_sha256=hashlib.sha256(Path(junit_path).read_bytes()).hexdigest(),
        source_sha256={name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in sorted(sources)})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--junit", required=True, type=Path)
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()
    receipt = verify(args.junit)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(receipt, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(f"WHD_V15_ACCEPTANCE_GREEN requirements={len(receipt['requirements'])} passed_cases={receipt['passed_cases']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
