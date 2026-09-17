from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
GATE = ROOT / "tools/task_chain_integration_readiness_gate.py"
CONTRACT = ROOT / "docs/governance/issue269-t6-integration-readiness-contract.json"
MASTER_TASK_ID = "262"
MASTER_BASE_SHA = "0e20662d4e36907d5e529346cccb2a5cafbf4f72"
TASK_FINAL_SHA = "89d1f304036937d2a5cfd24ccbfdff2b8dee26b1"
CURRENT_X_SHA = "269a2972f0f88ffc7085ee3f1483a57145d8b2e8"
TARGET = "X"
TARGET_BRANCH = "cleanup/2d-3d-sync"

TASK_PATHS = [
    ".github/workflows/issue268-t5-atomic-chain-acceptance.yml",
    "docs/governance/issue262-task-chain-contract.json",
    "docs/governance/issue263-t0-inventory.md",
    "docs/governance/issue265-t2-parent-contract.json",
    "docs/governance/issue266-t3-isolation-contract.json",
    "docs/governance/issue267-t4-dispatch-run-contract.json",
    "docs/governance/issue268-t5-atomic-chain-contract.json",
    "tests/process/test_issue264_frozen_base_guard.py",
    "tests/process/test_issue265_parent_contract.py",
    "tests/process/test_issue266_cross_chain_isolation.py",
    "tests/process/test_issue267_dispatch_run_identity.py",
    "tests/process/test_issue268_atomic_chain_acceptance.py",
    "tools/task_chain_atomic_acceptance_gate.py",
    "tools/task_chain_dispatch_run_guard.py",
    "tools/task_chain_guard.py",
    "tools/task_chain_isolation_guard.py",
]

X_PATHS = [
    ".agents/skills/engineering/寫成規格書/SKILL.md",
    ".agents/skills/engineering/派工/SKILL.md",
    "AGENTS.md",
    "docs/superpowers/plans/2026-09-14-gui-layout-presentation-move.md",
    "docs/superpowers/plans/2026-09-14-gui-pure-drawing-move.md",
    "docs/superpowers/plans/2026-09-14-issue212-final-integration.md",
    "docs/superpowers/specs/2026-09-14-issue212-final-integration-design.md",
    "gui.py",
    "gui_modules/__init__.py",
    "gui_modules/drawing.py",
    "gui_modules/layout.py",
    "gui_modules/part_panels.py",
    "gui_modules/project_actions.py",
    "gui_modules/render_2d.py",
    "tests/test_issue111_corner_data_grid_isolation.py",
    "tests/test_issue123_ui_foundation.py",
    "tests/test_issue206_gui_modularization_characterization.py",
    "tests/test_issue209_part_panel_projection.py",
    "tests/test_issue210_project_actions_move_contract.py",
    "tests/test_issue211_renderer_dependency_gate.py",
    "tests/test_phase6_linked_fold_chain_and_parts.py",
    "個人AI檔案庫/第二層_專案與SOP/09_X第二主分支與獨立工單鏈治理規格.md",
    "個人AI檔案庫/踩坑庫/long_log_context_safe_execution.md",
]


def _load_gate():
    assert GATE.is_file(), "#269 requires tools/task_chain_integration_readiness_gate.py"
    spec = importlib.util.spec_from_file_location("task_chain_integration_readiness_issue269", GATE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _manifest() -> dict:
    return {
        "schema_version": 1,
        "master_task_id": MASTER_TASK_ID,
        "master_base_sha": MASTER_BASE_SHA,
        "target": TARGET,
        "target_branch": TARGET_BRANCH,
        "task_final_sha": TASK_FINAL_SHA,
        "current_x_before": CURRENT_X_SHA,
        "current_x_after": CURRENT_X_SHA,
        "task_acceptance": {
            "status": "ACCEPTED",
            "code": "ELIGIBLE_FOR_INTEGRATION_ACCEPTANCE_CONSIDERATION",
            "evidence": "#268 accepted; run 34979004488 success at exact task-final head",
        },
        "base_to_task": {
            "status": "ahead",
            "merge_base_sha": MASTER_BASE_SHA,
            "ahead_by": 9,
            "behind_by": 0,
            "changed_paths": list(TASK_PATHS),
        },
        "base_to_x": {
            "status": "ahead",
            "merge_base_sha": MASTER_BASE_SHA,
            "ahead_by": 116,
            "behind_by": 0,
            "changed_paths": list(X_PATHS),
        },
        "task_to_x": {
            "status": "diverged",
            "merge_base_sha": MASTER_BASE_SHA,
            "task_only_commits": 9,
            "x_only_commits": 116,
        },
        "conflict_audit": {
            "status": "CLEAN",
            "method": "three_way_merge_tree",
            "evidence": "three-way merge-tree proof is clean for the frozen task-final/current-X pair",
        },
    }


def _write_json(tmp_path: Path, payload: dict) -> Path:
    path = tmp_path / "readiness.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _evaluate(gate, tmp_path: Path, payload: dict):
    return gate.evaluate_readiness(_write_json(tmp_path, payload), CONTRACT)


def test_clean_frozen_divergence_is_integration_readiness_eligible_only(tmp_path: Path) -> None:
    gate = _load_gate()
    decision = _evaluate(gate, tmp_path, _manifest())
    assert decision.eligible is True
    assert decision.code == "INTEGRATION_READINESS_ELIGIBLE"
    assert decision.task_acceptance == "ACCEPTED"
    assert decision.integration_acceptance == "NOT_PERFORMED"
    assert decision.current_x_sha == CURRENT_X_SHA


def test_task_acceptance_is_required_but_never_misreported_as_integration_acceptance(tmp_path: Path) -> None:
    gate = _load_gate()
    payload = _manifest()
    payload["task_acceptance"]["status"] = "PENDING"
    with pytest.raises(gate.IntegrationReadinessError, match="Task Acceptance|ACCEPTED"):
        _evaluate(gate, tmp_path, payload)


@pytest.mark.parametrize("field", ["current_x_before", "current_x_after"])
def test_current_x_identity_is_frozen_to_contract(tmp_path: Path, field: str) -> None:
    gate = _load_gate()
    payload = _manifest()
    payload[field] = "f" * 40
    with pytest.raises(gate.IntegrationReadinessError, match="current-X|current_x|identity|drift"):
        _evaluate(gate, tmp_path, payload)


def test_x_drift_during_audit_is_denied(tmp_path: Path) -> None:
    gate = _load_gate()
    payload = _manifest()
    payload["current_x_after"] = "e" * 40
    with pytest.raises(gate.IntegrationReadinessError, match="drift|current-X"):
        _evaluate(gate, tmp_path, payload)


@pytest.mark.parametrize("section", ["base_to_task", "base_to_x", "task_to_x"])
def test_all_three_lineage_comparisons_must_share_frozen_base(tmp_path: Path, section: str) -> None:
    gate = _load_gate()
    payload = _manifest()
    payload[section]["merge_base_sha"] = "d" * 40
    with pytest.raises(gate.IntegrationReadinessError, match="merge-base|merge_base|frozen base"):
        _evaluate(gate, tmp_path, payload)


def test_overlapping_changed_path_is_denied_even_if_conflict_evidence_claims_clean(tmp_path: Path) -> None:
    gate = _load_gate()
    payload = _manifest()
    payload["base_to_x"]["changed_paths"].append(TASK_PATHS[0])
    with pytest.raises(gate.IntegrationReadinessError, match="overlap|path"):
        _evaluate(gate, tmp_path, payload)


def test_unclean_conflict_probe_is_denied(tmp_path: Path) -> None:
    gate = _load_gate()
    payload = _manifest()
    payload["conflict_audit"]["status"] = "CONFLICT"
    with pytest.raises(gate.IntegrationReadinessError, match="conflict|CLEAN"):
        _evaluate(gate, tmp_path, payload)


def test_conflict_probe_requires_three_way_merge_tree_method(tmp_path: Path) -> None:
    gate = _load_gate()
    payload = _manifest()
    payload["conflict_audit"]["method"] = "path_overlap_only"
    with pytest.raises(gate.IntegrationReadinessError, match="three_way_merge_tree|method"):
        _evaluate(gate, tmp_path, payload)


def test_wrong_task_final_or_master_identity_is_denied(tmp_path: Path) -> None:
    gate = _load_gate()
    for field, value in [
        ("master_task_id", "999"),
        ("master_base_sha", "c" * 40),
        ("task_final_sha", "b" * 40),
        ("target", "main"),
        ("target_branch", "main"),
    ]:
        payload = _manifest()
        payload[field] = value
        with pytest.raises(gate.IntegrationReadinessError, match="identity|base|task-final|TARGET|branch"):
            _evaluate(gate, tmp_path, payload)


def test_compare_counts_must_prove_real_divergence(tmp_path: Path) -> None:
    gate = _load_gate()
    payload = _manifest()
    payload["task_to_x"]["task_only_commits"] = 0
    with pytest.raises(gate.IntegrationReadinessError, match="diverg|commit"):
        _evaluate(gate, tmp_path, payload)


def test_cli_green_says_readiness_only_and_never_claims_merge_or_integration_acceptance(tmp_path: Path) -> None:
    _load_gate()
    result = subprocess.run(
        [sys.executable, str(GATE), "--manifest", str(_write_json(tmp_path, _manifest())), "--contract", str(CONTRACT)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "INTEGRATION_READINESS_GREEN" in result.stdout
    assert "INTEGRATION_READINESS_ELIGIBLE" in result.stdout
    assert "integration_acceptance=NOT_PERFORMED" in result.stdout
    assert "merged" not in result.stdout.lower()


def test_malformed_or_ambiguous_json_fails_closed(tmp_path: Path) -> None:
    gate = _load_gate()
    malformed = tmp_path / "malformed.json"
    malformed.write_text('{"schema_version": 1,', encoding="utf-8")
    with pytest.raises(gate.IntegrationReadinessError, match="malformed"):
        gate.evaluate_readiness(malformed, CONTRACT)

    duplicate = tmp_path / "duplicate.json"
    duplicate.write_text(json.dumps(_manifest())[:-1] + ', "target": "main"}', encoding="utf-8")
    with pytest.raises(gate.IntegrationReadinessError, match="duplicate|ambiguous"):
        gate.evaluate_readiness(duplicate, CONTRACT)
