from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / ".scratch" / "issue304"
OUT.mkdir(parents=True, exist_ok=True)

BASE_SHA = os.environ.get("BASE_SHA", "3b59cb7bcc8ee5dc649924d17b164a55ec10f821")
EXPECTED_XVFB = {
    "tests/test_phase6_gui_3d_integrity_20260830.py::test_real_box_body_2d_annotations_do_not_overlap_each_other_or_material",
    "tests/test_phase6_receiving_edge_controls_gui.py::test_base_plate_edge_shrink_commit_uses_canonical_settings_transaction_and_updates_dimensions",
    "tests/test_phase6_receiving_edge_controls_gui.py::test_base_plate_four_shrinks_live_on_drawing_edges_and_bend_stays_in_settings_panel",
    "tests/test_phase6_receiving_edge_controls_gui.py::test_endcap_four_edge_controls_live_on_drawing_edges_even_when_parameters_locked",
    "tests/test_phase6_t02_endcap_edge_controls.py::test_head_settings_publish_four_edge_controls_directly_from_registry",
    "tests/test_phase6_t08_ui_text_and_edge_selectors.py::test_endcap_four_direction_edge_selectors_are_narrowed_and_preserve_semantics",
    "tests/test_phase6_t08_ui_text_and_edge_selectors.py::test_fold_designer_controls_and_edge_selectors_update_on_text_size_changed",
    "tests/test_phase6_t22_settings_vertical_scroll.py::test_medium_unlocked_settings_uses_real_vertical_scroll_owner_and_scrollable_viewport",
    "tests/test_phase6_t23_bottom_edge_visibility.py::test_medium_unlocked_endcap_edge_hosts_are_fully_inside_canvas[head]",
    "tests/test_phase6_t23_bottom_edge_visibility.py::test_medium_unlocked_endcap_edge_hosts_are_fully_inside_canvas[tail]",
    "tests/test_phase6_t24_edge_selector_width.py::test_endcap_four_direction_selectors_are_width_5_or_less_and_semantics_still_apply[head]",
    "tests/test_phase6_t24_edge_selector_width.py::test_endcap_four_direction_selectors_are_width_5_or_less_and_semantics_still_apply[tail]",
    "tests/test_phase6_t25_combined_receiving_acceptance.py::test_combined_receiving_operator_path_from_live_family_switch",
}


def run_capture(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)


def run_tee(cmd: list[str], log_path: Path) -> int:
    with log_path.open("w", encoding="utf-8") as log:
        proc = subprocess.Popen(
            cmd,
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=1,
        )
        assert proc.stdout is not None
        for line in proc.stdout:
            sys.stdout.write(line)
            sys.stdout.flush()
            log.write(line)
            log.flush()
        return proc.wait()


def canonical_nodes(output: str) -> list[str]:
    return sorted({
        line.strip()
        for line in output.splitlines()
        if line.startswith("tests/") and "::" in line
    })


def collect(expr: str | None) -> list[str]:
    cmd = [sys.executable, "-m", "pytest", "--collect-only", "-q", "tests"]
    if expr:
        cmd.extend(["-m", expr])
    proc = run_capture(cmd)
    if proc.returncode != 0:
        raise RuntimeError(f"COLLECTION_FAILED expr={expr!r} rc={proc.returncode}\n{proc.stdout}")
    return canonical_nodes(proc.stdout)


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def tracked_hashes() -> dict[str, str]:
    proc = subprocess.run(
        ["git", "ls-files", "-z"], cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True
    )
    files = [p.decode("utf-8") for p in proc.stdout.split(b"\0") if p]
    return {rel: file_sha256(ROOT / rel) for rel in sorted(files)}


def config_dxf_hashes() -> dict[str, str]:
    result: dict[str, str] = {}
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(ROOT).as_posix()
        if rel.startswith(".git/") or rel.startswith(".scratch/"):
            continue
        if path.name == "config.ini" or path.suffix.lower() == ".dxf":
            result[rel] = file_sha256(path)
    return dict(sorted(result.items()))


def write_json(name: str, payload: object) -> None:
    (OUT / name).write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def workflow_identity() -> dict[str, object]:
    token = os.environ["GH_TOKEN"]
    repo = os.environ["GITHUB_REPOSITORY"]
    run_id = os.environ["GITHUB_RUN_ID"]
    req = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/actions/runs/{run_id}",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(req) as response:
        payload = json.load(response)
    created_at = payload["created_at"]
    run_started_at = payload.get("run_started_at") or created_at
    parse = lambda value: datetime.fromisoformat(value.replace("Z", "+00:00"))
    return {
        "run_id": int(run_id),
        "workflow_sha": os.environ["GITHUB_SHA"],
        "ref_name": os.environ["GITHUB_REF_NAME"],
        "created_at": created_at,
        "run_started_at": run_started_at,
        "queue_delay_seconds": (parse(run_started_at) - parse(created_at)).total_seconds(),
        "job_start_epoch": int(os.environ["JOB_START_EPOCH"]),
        "job_start_iso": os.environ["JOB_START_ISO"],
    }


def scope_gate() -> list[str]:
    proc = run_capture(["git", "-c", "core.quotepath=false", "diff", "--name-only", BASE_SHA, os.environ["GITHUB_SHA"]])
    if proc.returncode != 0:
        raise RuntimeError(proc.stdout)
    changed = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    allowed = {
        ".github/workflows/issue304-t0-baseline.yml",
        ".github/workflows/issue304-t0-baseline-v2.yml",
        "docs/superpowers/plans/2026-09-16-issue304-t0-baseline.md",
        "tools/issue304_t0_baseline.py",
    }
    bad = [path for path in changed if path not in allowed]
    if bad:
        raise RuntimeError(f"T0_SOURCE_DRIFT={bad}")
    (OUT / "changed.txt").write_text("\n".join(changed) + "\n", encoding="utf-8")
    return changed


def parse_junit(path: Path) -> dict[str, int]:
    counts = {"tests": 0, "failures": 0, "errors": 0, "skipped": 0}
    if not path.is_file():
        return counts
    tree = ET.parse(path)
    root = tree.getroot()
    suites = list(root) if root.tag == "testsuites" else [root]
    for suite in suites:
        for key in counts:
            counts[key] += int(suite.attrib.get(key, 0) or 0)
    return counts


def parse_failed_nodes(path: Path) -> list[str]:
    if not path.is_file():
        return []
    nodes: set[str] = set()
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("FAILED ") or line.startswith("ERROR "):
            parts = line.split(None, 2)
            if len(parts) >= 2:
                nodes.add(parts[1])
    return sorted(nodes)


def main() -> int:
    from tools.test_lane_policy import LANE_EXPRESSIONS, XVFB_UI_EXPRESSION

    identity = workflow_identity()
    write_json("run-identity.json", identity)
    print(json.dumps(identity, indent=2, sort_keys=True))

    changed = scope_gate()
    print(f"T0_SOURCE_DRIFT=0 changed={changed}")

    tracked_before = tracked_hashes()
    config_before = config_dxf_hashes()
    write_json("tracked-before.json", tracked_before)
    write_json("config-dxf-before.json", config_before)

    full = collect(None)
    lane_exprs = dict(LANE_EXPRESSIONS)
    lane_exprs["xvfb_ui"] = XVFB_UI_EXPRESSION
    lanes = {name: collect(expr) for name, expr in lane_exprs.items()}
    union = sorted(set().union(*(set(nodes) for nodes in lanes.values())))
    missing = sorted(set(full) - set(union))
    extra = sorted(set(union) - set(full))
    (OUT / "full-collection.txt").write_text("\n".join(full) + "\n", encoding="utf-8")
    for name, nodes in lanes.items():
        (OUT / f"collection-{name}.txt").write_text("\n".join(nodes) + "\n", encoding="utf-8")
    membership = {
        "full_count": len(full),
        "union_count": len(union),
        "missing_from_union": missing,
        "extra_in_union": extra,
        "lane_expressions": lane_exprs,
        "lanes": {name: {"count": len(nodes), "nodes": nodes} for name, nodes in lanes.items()},
    }
    write_json("lane-membership.json", membership)
    print(f"FULL_COUNT={len(full)} UNION_COUNT={len(union)} missing={len(missing)} extra={len(extra)}")
    if missing or extra:
        raise RuntimeError("LANE_UNION_MISMATCH")

    order = ["governance", "unit", "geometry", "projection", "persistence", "dxf", "architecture", "ui", "integration", "xvfb_ui"]
    result_lanes: dict[str, object] = {}
    timing_rows: list[dict[str, object]] = []

    for name in order:
        expr = lane_exprs[name]
        report_name = "ui_headless" if name == "ui" else name
        start_epoch = time.time()
        start_iso = datetime.now(timezone.utc).isoformat()
        cmd = [sys.executable, "-m", "pytest", "-q", "-ra", "--tb=short", "--durations=30", f"--junitxml={OUT / (report_name + '.xml')}", "-m", expr, "tests"]
        if name == "xvfb_ui":
            cmd = ["xvfb-run", "-a", *cmd]
        print(f"===== LANE {report_name} :: {expr} =====")
        rc = run_tee(cmd, OUT / f"{report_name}.log")
        end_epoch = time.time()
        end_iso = datetime.now(timezone.utc).isoformat()
        elapsed = end_epoch - start_epoch
        failed = parse_failed_nodes(OUT / f"{report_name}.log")
        counts = parse_junit(OUT / f"{report_name}.xml")
        result_lanes[report_name] = {"returncode": rc, **counts, "failed_nodes": failed}
        timing_rows.append({
            "lane": report_name,
            "expr": expr,
            "start": start_iso,
            "end": end_iso,
            "elapsed_seconds": elapsed,
            "returncode": rc,
        })
        print(f"LANE_TERMINAL name={report_name} rc={rc} elapsed_seconds={elapsed:.3f}")

    classifier_started = True
    required_non_xvfb = ["governance", "unit", "geometry", "projection", "persistence", "dxf", "architecture", "ui_headless", "integration"]
    missing_status = [name for name in required_non_xvfb + ["xvfb_ui"] if name not in result_lanes]
    non_xvfb_red = {name: result_lanes[name]["returncode"] for name in required_non_xvfb if result_lanes.get(name, {}).get("returncode") != 0}
    actual_xvfb = set(result_lanes.get("xvfb_ui", {}).get("failed_nodes", []))
    xvfb_rc = result_lanes.get("xvfb_ui", {}).get("returncode")
    if xvfb_rc is None:
        xvfb_classification = "CLASSIFICATION_NOT_RUN"
    elif xvfb_rc == 0 and not actual_xvfb:
        xvfb_classification = "GREEN"
    elif actual_xvfb == EXPECTED_XVFB:
        xvfb_classification = "INHERITED_BASELINE_RED"
    else:
        xvfb_classification = "UNCLASSIFIED_RED"

    classifier_ok = not missing_status and not non_xvfb_red and xvfb_classification in {"GREEN", "INHERITED_BASELINE_RED"}
    classification = {
        "classifier_started": classifier_started,
        "classifier_rc": 0 if classifier_ok else 1,
        "classifier_terminal": "GREEN" if classifier_ok else "RED",
        "missing_lane_status": missing_status,
        "non_xvfb_red": non_xvfb_red,
        "xvfb_child_rc": xvfb_rc,
        "xvfb_failed_nodes": sorted(actual_xvfb),
        "xvfb_expected_inherited_nodes": sorted(EXPECTED_XVFB),
        "xvfb_missing_expected": sorted(EXPECTED_XVFB - actual_xvfb),
        "xvfb_extra_failed": sorted(actual_xvfb - EXPECTED_XVFB),
        "xvfb_classification": xvfb_classification,
        "lanes": result_lanes,
    }
    write_json("lane-summary.json", classification)
    write_json("lane-timing.json", timing_rows)
    (OUT / "classifier-state.txt").write_text(
        f"classifier_started=true\nclassifier_rc={classification['classifier_rc']}\nclassifier_terminal={classification['classifier_terminal']}\n",
        encoding="utf-8",
    )

    tracked_after = tracked_hashes()
    config_after = config_dxf_hashes()
    write_json("tracked-after.json", tracked_after)
    write_json("config-dxf-after.json", config_after)
    tracked_ok = tracked_before == tracked_after
    config_ok = config_before == config_after
    git_diff = run_capture(["git", "diff", "--exit-code"])
    worktree_ok = git_diff.returncode == 0
    invariant = {
        "tracked_authority_invariant": "GREEN" if tracked_ok else "RED",
        "config_dxf_invariant": "GREEN" if config_ok else "RED",
        "tracked_worktree_clean": "GREEN" if worktree_ok else "RED",
    }
    write_json("invariant-status.json", invariant)
    if not worktree_ok:
        (OUT / "tracked-worktree.diff").write_text(git_diff.stdout, encoding="utf-8")

    now = datetime.now(timezone.utc)
    created = datetime.fromisoformat(str(identity["created_at"]).replace("Z", "+00:00"))
    final = {
        **identity,
        "execution_wall_clock_seconds": time.time() - int(identity["job_start_epoch"]),
        "end_to_end_wall_clock_seconds": (now - created).total_seconds(),
        "collection": {
            "full_count": len(full),
            "union_count": len(union),
            "missing_from_union": missing,
            "extra_in_union": extra,
            "lane_counts": {name: data["count"] for name, data in membership["lanes"].items()},
        },
        "lane_timings": timing_rows,
        "xvfb_child_rc": xvfb_rc,
        "xvfb_classification": xvfb_classification,
        "classifier_started": classifier_started,
        "classifier_rc": classification["classifier_rc"],
        "invariants": invariant,
    }
    write_json("timing-summary.json", final)
    print(json.dumps(final, ensure_ascii=False, indent=2, sort_keys=True))

    accepted = (
        classifier_ok
        and tracked_ok
        and config_ok
        and worktree_ok
        and not missing
        and not extra
    )
    print("ISSUE304_T0_BASELINE=GREEN" if accepted else "ISSUE304_T0_BASELINE=RED")
    return 0 if accepted else 1


if __name__ == "__main__":
    raise SystemExit(main())
