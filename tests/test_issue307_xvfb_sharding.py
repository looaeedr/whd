from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

import pytest

from tools import xvfb_shard_execution as execution
from tools.phase6_release_test_runner import ProcessResult, XvfbSession


def _manifest() -> dict[str, object]:
    return {
        "schema": "WHD_TEST_SHARD_MANIFEST_V1",
        "source_sha": "accepted-t2",
        "shards": {
            "unit": {
                "s00": {"count": 1, "nodes": ["tests/u.py::test_u"]},
            },
            "xvfb_ui": {
                "s00": {"count": 1, "nodes": ["tests/x.py::test_a"]},
                "s01": {"count": 1, "nodes": ["tests/x.py::test_b"]},
                "s02": {"count": 1, "nodes": ["tests/x.py::test_c"]},
                "s03": {"count": 1, "nodes": ["tests/x.py::test_d"]},
            },
        },
    }


def test_xvfb_matrix_is_exactly_four_way_and_uses_ci_budget() -> None:
    plan = execution.build_xvfb_matrix(_manifest(), concurrency_budget=4)
    assert plan.max_parallel == 4
    assert [(entry["lane"], entry["shard_id"], entry["node_count"]) for entry in plan.matrix] == [
        ("xvfb_ui", "s00", 1),
        ("xvfb_ui", "s01", 1),
        ("xvfb_ui", "s02", 1),
        ("xvfb_ui", "s03", 1),
    ]
    assert all("nodes" not in entry for entry in plan.matrix)


def test_xvfb_matrix_fails_closed_if_authoritative_manifest_is_not_four_way() -> None:
    manifest = _manifest()
    del manifest["shards"]["xvfb_ui"]["s03"]  # type: ignore[index]
    with pytest.raises(execution.ExecutionError, match="XVFB_SHARD_COUNT_MISMATCH"):
        execution.build_xvfb_matrix(manifest, concurrency_budget=4)


def test_xvfb_exact_node_selection_comes_only_from_manifest() -> None:
    assert execution.select_shard_nodes(
        _manifest(), "xvfb_ui", "s02", allow_xvfb=True
    ) == ["tests/x.py::test_c"]


@pytest.mark.parametrize(
    "args",
    [
        ["-n", "auto"],
        ["-nauto"],
        ["-n", "4"],
        ["--numprocesses=auto"],
        ["--numprocesses", "4"],
    ],
)
def test_gui_pytest_parallelism_is_fail_closed(args: list[str]) -> None:
    with pytest.raises(execution.ExecutionError, match="XVFB_PARALLEL_PYTEST_FORBIDDEN"):
        execution.validate_gui_pytest_args(args)


def test_serial_gui_pytest_args_are_allowed() -> None:
    assert execution.validate_gui_pytest_args(["-q", "-ra", "--tb=short", "--durations=30"]) is None


def test_rc1_without_classifier_start_is_not_hang() -> None:
    classification = execution.resolve_xvfb_terminal_state(
        child_rc=1,
        timed_out=False,
        classifier_started=False,
        classifier_rc=None,
        classifier_classification=None,
    )
    assert classification == "CLASSIFICATION_NOT_RUN"
    assert "HANG" not in classification
    assert "TIMEOUT" not in classification


def test_true_timeout_requires_no_terminal_child_rc() -> None:
    assert execution.resolve_xvfb_terminal_state(
        child_rc=None,
        timed_out=True,
        classifier_started=False,
        classifier_rc=None,
        classifier_classification=None,
    ) == "HANG_TIMEOUT"


def test_missing_child_terminal_without_timeout_fails_closed() -> None:
    assert execution.resolve_xvfb_terminal_state(
        child_rc=None,
        timed_out=False,
        classifier_started=False,
        classifier_rc=None,
        classifier_classification=None,
    ) == "CHILD_TERMINAL_MISSING"


def test_classifier_started_without_terminal_result_is_infrastructure_red() -> None:
    assert execution.resolve_xvfb_terminal_state(
        child_rc=1,
        timed_out=False,
        classifier_started=True,
        classifier_rc=None,
        classifier_classification=None,
    ) == "CLASSIFIER_INFRA_FAILURE"


def test_rc1_reaches_classifier_and_preserves_inherited_baseline_semantics() -> None:
    classifier_rc, classifier_classification = execution.classify_xvfb_failed_nodes(
        child_rc=1,
        failed_nodes=["tests/x.py::test_a"],
        expected_failed_nodes=["tests/x.py::test_a"],
    )
    assert classifier_rc == 0
    assert classifier_classification == "INHERITED_BASELINE_RED"
    assert execution.resolve_xvfb_terminal_state(
        child_rc=1,
        timed_out=False,
        classifier_started=True,
        classifier_rc=classifier_rc,
        classifier_classification=classifier_classification,
    ) == "INHERITED_BASELINE_RED"


def test_unexpected_rc1_failure_remains_unclassified_red() -> None:
    classifier_rc, classifier_classification = execution.classify_xvfb_failed_nodes(
        child_rc=1,
        failed_nodes=["tests/x.py::test_new"],
        expected_failed_nodes=["tests/x.py::test_a"],
    )
    assert classifier_rc == 1
    assert classifier_classification == "UNCLASSIFIED_RED"


def test_execute_xvfb_shard_owns_display_process_and_emits_terminal_proof(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    seen: dict[str, object] = {}

    @contextmanager
    def fake_xvfb():
        yield XvfbSession(display=":177", pid=4242)

    def fake_run_process_group(command, *, timeout_seconds, cwd=None, env=None):
        seen["command"] = list(command)
        seen["env"] = dict(env or {})
        seen["timeout_seconds"] = timeout_seconds
        return ProcessResult(
            returncode=1,
            stdout="FAILED tests/x.py::test_a - AssertionError\n1 failed in 0.10s\n",
            timed_out=False,
            elapsed_seconds=0.10,
        )

    monkeypatch.setattr(execution, "managed_xvfb", fake_xvfb, raising=False)
    monkeypatch.setattr(execution, "run_process_group", fake_run_process_group, raising=False)

    payload = execution.execute_xvfb_shard(
        nodes=["tests/x.py::test_a"],
        shard_id="s00",
        expected_failed_nodes=["tests/x.py::test_a"],
        result_json=tmp_path / "result.json",
        log_path=tmp_path / "pytest.log",
        basetemp=tmp_path / "pytest-tmp",
        timeout_seconds=12.0,
        pytest_args=["-q", "-ra", "--tb=short", "--durations=30"],
    )

    command = seen["command"]
    assert isinstance(command, list)
    assert "-n" not in command
    assert "-nauto" not in command
    assert all(not str(arg).startswith("--numprocesses") for arg in command)
    assert command[-1] == "tests/x.py::test_a"
    assert seen["env"]["DISPLAY"] == ":177"  # type: ignore[index]
    assert payload["xvfb_display"] == ":177"
    assert payload["xvfb_pid"] == 4242
    assert payload["child_rc"] == 1
    assert payload["timed_out"] is False
    assert payload["classifier_started"] is True
    assert payload["classifier_rc"] == 0
    assert payload["classification"] == "INHERITED_BASELINE_RED"
    assert payload["child_started_epoch"] <= payload["child_ended_epoch"]
    assert payload["log_path"] == str(tmp_path / "pytest.log")
    assert (tmp_path / "result.json").is_file()
    assert (tmp_path / "pytest.log").is_file()
