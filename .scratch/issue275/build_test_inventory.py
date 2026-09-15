from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path

import pytest

CLASSIFICATIONS = {
    "KEEP_CURRENT_CONTRACT",
    "REWRITE_SUPERSEDED_CONTRACT",
    "MERGE_DUPLICATE_COVERAGE",
    "RETIRE_CHARACTERIZATION",
    "MOVE_TO_GOVERNANCE_LANE",
    "MOVE_TO_UI_LANE",
    "INHERITED_BASELINE_REQUIRES_SEPARATE_FIX",
}

STALE_SEMANTIC_NODE = (
    "tests/test_phase6_semantic_doc_status.py::"
    "test_current_overlay_docs_point_to_v3_standard_plus_semantic_delta"
)


def load_inherited(path: Path) -> set[str]:
    return {
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }


def issue_provenance(path: str) -> str:
    m = re.search(r"test_issue(\d+)", path)
    if m:
        return f"issue-{m.group(1)}"
    m = re.search(r"test_phase6_t(\d+)", path)
    if m:
        return f"phase6-t{m.group(1)}"
    m = re.search(r"_t(\d+)(?:\.|_)", path)
    if m:
        return f"t{m.group(1)}"
    return ""


def marker_requires_display(item) -> bool:  # noqa: ANN001
    for mark in item.iter_markers():
        if mark.name in {"requires_tk_display", "xvfb"}:
            return True
        if mark.name == "skipif":
            reason = str(mark.kwargs.get("reason", "")).lower()
            condition = bool(mark.args[0]) if mark.args else False
            if condition and any(token in reason for token in ("display", "tk", "xvfb")):
                return True
    return False


def classify_lane(path: str, requires_display: bool) -> str:
    low = path.lower()
    if path.startswith("tests/knowledge/") or path.startswith("tests/process/"):
        return "governance"
    if requires_display:
        return "ui"
    if any(token in low for token in ("architecture", "dependency", "module_ownership")):
        return "architecture"
    if any(token in low for token in ("dxf", "export")):
        return "dxf"
    if any(token in low for token in ("2d_3d", "projection", "render", "drawing")):
        return "projection"
    if any(token in low for token in ("geometry", "relief", "divider", "corner", "mesh")):
        return "geometry"
    if any(token in low for token in ("persist", "reload", "project_io", "save")):
        return "persistence"
    return "regression"


def contract_for(path: str) -> str:
    if path.startswith("tests/knowledge/"):
        return "knowledge-governance"
    if path.startswith("tests/process/"):
        return "process-governance"
    special = {
        "tests/test_phase6_semantic_doc_status.py": "document-authority-metadata",
        "tests/test_issue76_box_body_subtabs_2d_3d.py": "box-body-physical-part-navigation",
        "tests/test_box_body_single_source_t3.py": "box-body-single-source-projection",
        "tests/test_issue206_gui_modularization_characterization.py": "gui-modularization-characterization",
        "tests/test_issue209_part_panel_projection.py": "physical-part-projection",
        "tests/test_issue210_project_actions_move_contract.py": "project-actions-module-ownership",
        "tests/test_issue211_renderer_dependency_gate.py": "renderer-dependency-boundary",
    }
    if path in special:
        return special[path]
    return Path(path).stem.removeprefix("test_").replace("_", "-")


def authority_for(path: str, contract: str) -> str:
    if path.startswith("tests/knowledge/"):
        return "AGENTS.md + Canonical Authority Map + governed metadata"
    if path.startswith("tests/process/"):
        return "CURRENT process Skill / executable process owner"
    if contract == "document-authority-metadata":
        return "WHD_DOC_META_V1 + Canonical Authority Map"
    if contract in {"box-body-single-source-projection", "physical-part-projection", "box-body-physical-part-navigation"}:
        return "authoritative render/projection state + current physical-part contract"
    if contract in {"project-actions-module-ownership", "renderer-dependency-boundary", "gui-modularization-characterization"}:
        return "current architecture/module ownership contract"
    return "current product contract / canonical domain authority"


def classification_for(nodeid: str, path: str, requires_display: bool, inherited: set[str]) -> tuple[str, str]:
    # Current authority beats historical baseline classification when the contract itself is superseded.
    if nodeid == STALE_SEMANTIC_NODE:
        return "REWRITE_SUPERSEDED_CONTRACT", "HISTORICALLY_INHERITED_RED_CURRENT_CONTRACT_DRIFT"
    if nodeid in inherited:
        return "INHERITED_BASELINE_REQUIRES_SEPARATE_FIX", "KNOWN_INHERITED_EVIDENCE"
    if path.startswith("tests/knowledge/") or path.startswith("tests/process/"):
        return "MOVE_TO_GOVERNANCE_LANE", "CURRENT_CONTRACT_REHOME"
    if requires_display:
        return "MOVE_TO_UI_LANE", "CURRENT_CONTRACT_REHOME"
    if path == "tests/test_issue206_gui_modularization_characterization.py":
        return "KEEP_CURRENT_CONTRACT", "REVIEW_CHARACTERIZATION_PROMOTE_OR_RETIRE"
    return "KEEP_CURRENT_CONTRACT", "COLLECTED"


class InventoryPlugin:
    def __init__(self, inherited: set[str], mode: str):
        self.inherited = inherited
        self.mode = mode
        self.rows: list[dict[str, object]] = []

    def pytest_collection_modifyitems(self, session, config, items):  # noqa: ANN001
        for item in items:
            nodeid = item.nodeid.replace("\\", "/")
            path = nodeid.split("::", 1)[0]
            markers = {mark.name for mark in item.iter_markers()}
            requires_display = marker_requires_display(item)
            classification, status = classification_for(nodeid, path, requires_display, self.inherited)
            lane = classify_lane(path, requires_display)
            contract = contract_for(path)
            self.rows.append(
                {
                    "path": path,
                    "test_node": nodeid,
                    "lane": lane,
                    "contract": contract,
                    "authority": authority_for(path, contract),
                    "classification": classification,
                    "replacement": "",
                    "status": status,
                    "requires_display": requires_display,
                    "issue_provenance": issue_provenance(path),
                    "collection_mode": self.mode,
                    "markers": sorted(markers),
                }
            )
            assert classification in CLASSIFICATIONS


def collect(mode: str, inherited_path: Path, output: Path) -> int:
    inherited = load_inherited(inherited_path)
    plugin = InventoryPlugin(inherited, mode)
    rc = pytest.main(["--collect-only", "-q", "tests"], plugins=[plugin])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps({"mode": mode, "pytest_rc": rc, "count": len(plugin.rows), "rows": plugin.rows}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    if rc != pytest.ExitCode.OK:
        raise SystemExit(int(rc))
    return 0


def merge(headless_path: Path, xvfb_path: Path, inherited_path: Path, out_dir: Path) -> int:
    headless = json.loads(headless_path.read_text(encoding="utf-8"))
    xvfb = json.loads(xvfb_path.read_text(encoding="utf-8"))
    inherited = load_inherited(inherited_path)
    hm = {row["test_node"]: row for row in headless["rows"]}
    xm = {row["test_node"]: row for row in xvfb["rows"]}
    all_nodes = sorted(set(hm) | set(xm))
    rows: list[dict[str, object]] = []
    for node in all_nodes:
        source = dict(xm.get(node) or hm[node])
        source["collected_headless"] = node in hm
        source["collected_xvfb"] = node in xm
        source["requires_display"] = bool(hm.get(node, {}).get("requires_display")) or bool(xm.get(node, {}).get("requires_display"))
        if source["requires_display"] and source["classification"] == "KEEP_CURRENT_CONTRACT":
            source["lane"] = "ui"
            source["classification"] = "MOVE_TO_UI_LANE"
            source["status"] = "CURRENT_CONTRACT_REHOME"
        source.pop("collection_mode", None)
        rows.append(source)

    missing_inherited = sorted(inherited - set(all_nodes))
    if missing_inherited:
        raise SystemExit(f"known inherited nodeids missing from current collection: {missing_inherited}")

    # The superseded semantic-doc node remains represented even though it has historical inherited-red evidence.
    semantic = next(row for row in rows if row["test_node"] == STALE_SEMANTIC_NODE)
    if semantic["classification"] != "REWRITE_SUPERSEDED_CONTRACT":
        raise SystemExit(f"semantic-doc classification drift: {semantic}")

    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "test_inventory.json"
    csv_path = out_dir / "test_inventory.csv"
    md_path = out_dir / "test_inventory.md"

    summary = {
        "total_nodes": len(rows),
        "headless_nodes": len(hm),
        "xvfb_nodes": len(xm),
        "known_inherited_nodes": len(inherited),
        "lane_counts": dict(sorted(Counter(str(r["lane"]) for r in rows).items())),
        "classification_counts": dict(sorted(Counter(str(r["classification"]) for r in rows).items())),
    }
    json_path.write_text(json.dumps({"summary": summary, "rows": rows}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    fields = [
        "path", "test_node", "lane", "contract", "authority", "classification",
        "replacement", "status", "requires_display", "issue_provenance",
        "collected_headless", "collected_xvfb",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    lines = [
        "# WHD TEST Inventory — Issue #275 / T0",
        "",
        "This is an inventory/classification artifact only. It does not change production or test contracts.",
        "",
        f"- Total collected nodes: {summary['total_nodes']}",
        f"- Headless collection: {summary['headless_nodes']}",
        f"- Xvfb collection: {summary['xvfb_nodes']}",
        f"- Historical inherited evidence nodeids represented: {summary['known_inherited_nodes']}",
        "",
        "## Lane counts",
    ]
    lines.extend(f"- `{key}`: {value}" for key, value in summary["lane_counts"].items())
    lines += ["", "## Classification counts"]
    lines.extend(f"- `{key}`: {value}" for key, value in summary["classification_counts"].items())
    lines += ["", "## First cleanup candidates", ""]
    candidates = [
        r for r in rows
        if r["classification"] != "KEEP_CURRENT_CONTRACT"
        or r["status"] == "REVIEW_CHARACTERIZATION_PROMOTE_OR_RETIRE"
    ]
    for row in candidates:
        lines.append(f"- `{row['test_node']}` — `{row['classification']}` — {row['status']}")
    lines += [
        "", "## Safety boundary", "",
        "- No production files are modified by T0.",
        "- No failing test is deleted merely because it is red.",
        "- Unknown cases default to `KEEP_CURRENT_CONTRACT`.",
        "- Historical inherited-red evidence is annotation only; current canonical authority still decides whether a test contract is superseded.",
    ]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps(summary, sort_keys=True))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    pc = sub.add_parser("collect")
    pc.add_argument("--mode", choices=("headless", "xvfb"), required=True)
    pc.add_argument("--inherited", type=Path, required=True)
    pc.add_argument("--output", type=Path, required=True)
    pm = sub.add_parser("merge")
    pm.add_argument("--headless", type=Path, required=True)
    pm.add_argument("--xvfb", type=Path, required=True)
    pm.add_argument("--inherited", type=Path, required=True)
    pm.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.cmd == "collect":
        return collect(args.mode, args.inherited, args.output)
    return merge(args.headless, args.xvfb, args.inherited, args.out_dir)


if __name__ == "__main__":
    raise SystemExit(main())
