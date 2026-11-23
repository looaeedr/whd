"""Isolated #3415 process-boundary candidate tests; no CADCraft binary required.

Original Engine proof remains the truth. Fake CLI writes a *real* disposable
DXF via ezdxf, while the candidate proof is executed by real Python -m child.
No GUI, Session, production DXF, or original native Windows tests are modified.
"""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import ezdxf
import pytest

from ae_engine.cadcraft_exchange_proof import (
    CadcraftCommandProofError, verify_dxf,
)
from tools import issue1959_whd_cadcraft_command_draw as drawing


def _make_native_like_output(target, preview, items, *, units=ezdxf.units.MM,
                             altered_radius=False):
    doc = ezdxf.new("R2010", units=units)
    for item in items:
        if item.kind == "circle":
            doc.modelspace().add_circle(
                item.points[0], item.radius + (1 if altered_radius else 0)
            )
        else:
            doc.modelspace().add_lwpolyline(item.points, close=True)
    doc.saveas(target)
    if preview is not None:
        preview.write_bytes(b"isolated fake PNG only for proof-path test")


def _fake_vendor(monkeypatch, items, *, units=ezdxf.units.MM, altered_radius=False,
                 child_behavior=None):
    real_run = subprocess.run
    seen = []

    def run(args, **kwargs):
        seen.append(tuple(args))
        if args[0] == "candidate-fake-cadcraft-cli":
            assert args[1:3] == ["run", "--metric"]
            target = Path(args[args.index("--save") + 1])
            preview = Path(args[args.index("--export") + 1])
            _make_native_like_output(
                target, preview, items, units=units, altered_radius=altered_radius
            )
            return subprocess.CompletedProcess(args, 0, "", "")
        if child_behavior is not None:
            return child_behavior(args, kwargs, real_run)
        return real_run(args, **kwargs)

    monkeypatch.setattr(drawing.subprocess, "run", run)
    return seen


def _single():
    return drawing.demo_instructions()[:1]


def test_child_output_same_as_unmodified_engine_proof(tmp_path, monkeypatch):
    items = drawing.demo_instructions()
    output, preview = tmp_path/"real_exchange.dxf", tmp_path/"real_preview.png"
    calls = _fake_vendor(monkeypatch, items)
    result = drawing.run_proof("candidate-fake-cadcraft-cli", items, output, preview)
    assert result == verify_dxf(output, items)
    assert output.is_file() and preview.is_file()
    assert len(calls) == 2
    assert calls[1][:3] == (sys.executable, "-m", "tools.issue1959_cadcraft_proof_child")
    assert all("tk" not in word.casefold() for word in calls[1][:3])


@pytest.mark.parametrize("units,altered,code", [
    (ezdxf.units.IN, False, "CADCRAFT_PROOF_CHILD_FAILED"),
    (ezdxf.units.MM, True, "CADCRAFT_PROOF_CHILD_FAILED"),
])
def test_unchanged_engine_refuses_wrong_units_or_geometry_and_cleans(
    tmp_path, monkeypatch, units, altered, code,
):
    items = _single()
    output, preview = tmp_path/"bad.dxf", tmp_path/"bad.png"
    marker = tmp_path/"untouched_project.p6fold"
    marker.write_bytes(b"ORIGINAL_WHD_PROJECT")
    _fake_vendor(monkeypatch, items, units=units, altered_radius=altered)
    with pytest.raises(CadcraftCommandProofError, match=code):
        drawing.run_proof("candidate-fake-cadcraft-cli", items, output, preview)
    assert not output.exists() and not preview.exists()
    assert marker.read_bytes() == b"ORIGINAL_WHD_PROJECT"


@pytest.mark.parametrize("failure", ["crash", "timeout", "bad_json", "forged_pass"])
def test_child_crash_timeout_or_invalid_response_denies_and_cleans(
    tmp_path, monkeypatch, failure,
):
    items = _single()
    output, preview = tmp_path/"transaction.dxf", tmp_path/"transaction.png"
    sentinel = tmp_path/"existing_project.p6fold"
    sentinel.write_bytes(b"KEEP_THIS_PROJECT")
    def invalid_child(args, options, real_run):
        assert args[:3] == [sys.executable, "-m", "tools.issue1959_cadcraft_proof_child"]
        if failure == "timeout":
            raise subprocess.TimeoutExpired(args, options["timeout"])
        if failure == "crash":
            return subprocess.CompletedProcess(args, -1073741819, "", "native crash")
        if failure == "bad_json":
            return subprocess.CompletedProcess(args, 0, "not-json", "")
        return subprocess.CompletedProcess(
            args, 0, json.dumps({"status": "PASS", "entity_count": 1}), ""
        )

    _fake_vendor(monkeypatch, items, child_behavior=invalid_child)
    with pytest.raises(CadcraftCommandProofError, match="CADCRAFT_PROOF_CHILD_"):
        drawing.run_proof("candidate-fake-cadcraft-cli", items, output, preview)
    assert not output.exists() and not preview.exists()
    assert sentinel.read_bytes() == b"KEEP_THIS_PROJECT"


def test_existing_exchange_file_refused_without_any_subprocess_call(
    tmp_path, monkeypatch,
):
    items = _single()
    output, preview = tmp_path/"existing.dxf", tmp_path/"new.png"
    original = b"ORIGINAL_MANUFACTURING_FILE"
    output.write_bytes(original)
    calls = []
    monkeypatch.setattr(drawing.subprocess, "run",
                        lambda *a, **k: calls.append(a) or None)
    with pytest.raises(CadcraftCommandProofError, match="REFUSE_TO_OVERWRITE"):
        drawing.run_proof("candidate-fake-cadcraft-cli", items, output, preview)
    assert output.read_bytes() == original and not preview.exists() and not calls


def test_frozen_interpreter_refuses_proof_before_treating_exe_as_python(
    tmp_path, monkeypatch,
):
    items = _single()
    output, preview = tmp_path/"candidate.dxf", tmp_path/"candidate.png"
    _fake_vendor(monkeypatch, items)
    monkeypatch.setattr(drawing.sys, "frozen", True, raising=False)
    with pytest.raises(CadcraftCommandProofError,
                       match="CADCRAFT_PROOF_PYTHON_RUNTIME_REQUIRED"):
        drawing.run_proof("candidate-fake-cadcraft-cli", items, output, preview)
    assert not output.exists() and not preview.exists()
