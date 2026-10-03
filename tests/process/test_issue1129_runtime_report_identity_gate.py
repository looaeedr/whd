from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from tools.runtime_report_identity import (
    RuntimeReportIdentityError,
    build_runtime_report_identity,
    format_runtime_report_prefix,
)

ROOT = Path(__file__).resolve().parents[2]
EXIT_GATE = ROOT / "tools" / "assistant_turn_exit_gate.py"
REPORT_GATE = ROOT / "tools" / "runtime_report_identity.py"


def test_interactive_report_requires_complete_fresh_identity():
    with pytest.raises(RuntimeReportIdentityError, match="invocation_identity"):
        build_runtime_report_identity(
            handler="工作0",
            owner="chatgpt.flowv2.work0",
            issue=1129,
            slot="worker.slot.0",
            invocation_identity="",
            runtime_kind="INTERACTIVE",
        )


def test_scheduler_report_rejects_work_slot_handler_mismatch():
    with pytest.raises(RuntimeReportIdentityError, match="scheduler handler"):
        build_runtime_report_identity(
            handler="工作0",
            owner="scheduler.6ab13fa557fc8191935c671214b865e2",
            issue=1129,
            slot="worker.slot.0",
            invocation_identity="scheduled:a00:20261002T1000Z",
            runtime_kind="SCHEDULER",
        )


def test_interactive_report_rejects_scheduler_handler_mismatch():
    with pytest.raises(RuntimeReportIdentityError, match="interactive handler"):
        build_runtime_report_identity(
            handler="排程A",
            owner="chatgpt.flowv2.work0",
            issue=1129,
            slot="worker.slot.0",
            invocation_identity="chatgpt.flowv2.work0.issue1129.20261002",
            runtime_kind="INTERACTIVE",
        )


def test_unbound_query_uses_explicit_markers_instead_of_omission():
    identity = build_runtime_report_identity(
        handler="工作0",
        owner="NONE",
        issue="UNBOUND",
        slot="worker.slot.0",
        invocation_identity="chatgpt.flowv2.work0.query.20261002",
        runtime_kind="INTERACTIVE",
    )
    assert format_runtime_report_prefix(identity) == (
        "【處理者：工作0｜owner=NONE｜工單：#UNBOUND｜slot=worker.slot.0"
        "｜invocation_identity=chatgpt.flowv2.work0.query.20261002】"
    )


def test_complete_interactive_report_formats_all_required_fields():
    identity = build_runtime_report_identity(
        handler="工作2",
        owner="chatgpt.flowv2.work2",
        issue=1093,
        slot="worker.slot.2",
        invocation_identity="chatgpt.flowv2.work2.issue1093.20261002T0634Z",
        runtime_kind="INTERACTIVE",
    )
    prefix = format_runtime_report_prefix(identity)
    for expected in (
        "處理者：工作2",
        "owner=chatgpt.flowv2.work2",
        "工單：#1093",
        "slot=worker.slot.2",
        "invocation_identity=chatgpt.flowv2.work2.issue1093.20261002T0634Z",
    ):
        assert expected in prefix


def test_outer_exit_gate_cli_requires_runtime_report_identity_arguments():
    result = subprocess.run(
        [
            sys.executable,
            str(EXIT_GATE),
            "missing-checkpoint.json",
            "missing-receipt.json",
            "--issue",
            "#1129",
            "--branch",
            "x",
            "--head-sha",
            "a" * 40,
            "--census-exhaustive",
            "--executable-leaf-count",
            "0",
            "--census-observed-at",
            "2026-10-02T00:00:00Z",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert result.returncode != 0
    for flag in (
        "--report-handler",
        "--report-owner",
        "--report-issue",
        "--report-slot",
        "--report-invocation-identity",
        "--report-runtime-kind",
    ):
        assert flag in result.stderr


@pytest.mark.parametrize("event", ["PROGRESS", "CHECKPOINT", "TERMINAL", "EXIT", "STATUS"])
def test_report_gate_cli_requires_identity_for_every_visible_report_class(event):
    result = subprocess.run(
        [
            sys.executable,
            str(REPORT_GATE),
            "--event",
            event,
            "--handler",
            "工作0",
            "--owner",
            "chatgpt.flowv2.work0",
            "--issue",
            "1129",
            "--slot",
            "worker.slot.0",
            "--invocation-identity",
            "chatgpt.flowv2.work0.issue1129.test",
            "--runtime-kind",
            "INTERACTIVE",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    assert "invocation_identity=chatgpt.flowv2.work0.issue1129.test" in result.stdout
    assert f"RUNTIME_REPORT_IDENTITY_VALID event={event}" in result.stdout


def test_report_gate_cli_fails_closed_when_owner_is_omitted():
    result = subprocess.run(
        [
            sys.executable,
            str(REPORT_GATE),
            "--event",
            "PROGRESS",
            "--handler",
            "工作0",
            "--issue",
            "1129",
            "--slot",
            "worker.slot.0",
            "--invocation-identity",
            "chatgpt.flowv2.work0.issue1129.test",
            "--runtime-kind",
            "INTERACTIVE",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert result.returncode != 0
    assert "--owner" in result.stderr
