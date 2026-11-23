"""#3415 diagnostics ONLY: same original native Windows Tk button E2E with A/B.

B replaces only tools.issue1959_whd_cadcraft_command_draw.verify_dxf
in the *test interpreter*. Its child executes the original Engine verify_dxf
unchanged; no GC suppression, fake CADCraft, skipped checks or altered UI.
All real GUI, Button.invoke, Tk poll, Session, Confirm, Cancel, Undo assertions
are literally the original #1959 Windows E2E test function.
"""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import ezdxf
import pytest

from ae_engine.cadcraft_exchange_proof import CadcraftCommandProofError, DrawInstruction
from tools import issue1959_whd_cadcraft_command_draw as command_draw
from test_issue1959_native_windows_whd_button_e2e import (
    test_whd_real_tk_button_opens_real_native_cadcraft_and_returns_unsaved_hole
    as unmodified_native_test,
)


def _full_engine_proof_in_child(path: Path, expected: tuple[DrawInstruction, ...]) -> dict:
    """Only move complete Engine proof read/verification into child process."""
    data = json.dumps(
        [{"kind": item.kind,
          "points": [list(point) for point in item.points],
          "radius": item.radius}
         for item in expected],
        ensure_ascii=True, allow_nan=False,
    )
    print("WHD_3415_CHILD_BEFORE:", str(path), len(expected), flush=True)
    proc = subprocess.run(
        [sys.executable, "-m", "tools.issue3415_native_windows_proof_child", str(path)],
        input=data, capture_output=True, text=True, timeout=120, check=False,
    )
    if proc.returncode != 0:
        raise CadcraftCommandProofError(
            f"WHD_3415_CHILD_FULL_PROOF_RED:{proc.returncode}:"
            + proc.stderr[-1500:]
        )
    try:
        result = json.loads(proc.stdout)
    except (ValueError, TypeError) as exc:
        raise CadcraftCommandProofError("WHD_3415_CHILD_PROOF_INVALID_JSON") from exc
    if result.get("status") != "PASS" or result.get("entity_count") != len(expected):
        raise CadcraftCommandProofError("WHD_3415_CHILD_FULL_PROOF_NOT_PASS")
    print("WHD_3415_CHILD_VERIFIED_PASS:", result["entity_count"], flush=True)
    return result


def test_child_proof_rejects_real_wrong_units(tmp_path):
    target = tmp_path / "bad_inches.dxf"
    doc = ezdxf.new("R2010", units=ezdxf.units.IN)
    doc.modelspace().add_circle((40, 40), 5)
    doc.saveas(target)
    with pytest.raises(CadcraftCommandProofError, match="CHILD_FULL_PROOF_RED"):
        _full_engine_proof_in_child(
            target, (DrawInstruction("circle", ((40., 40.),), 5.),)
        )


@pytest.mark.parametrize("confirmed", [True, False], ids=["confirm", "cancel"])
def test_real_native_button_same_all_checks_only_proof_in_child(monkeypatch, confirmed):
    print("WHD_3415_B_ORIGINAL_E2E_BEGIN", "confirm" if confirmed else "cancel", flush=True)
    monkeypatch.setattr(command_draw, "verify_dxf", _full_engine_proof_in_child)
    # This calls the real original #1959 test, with every GUI, TCP, Session,
    # geometry, provenance, Undo and untouched-file assertion intact.
    unmodified_native_test(monkeypatch, confirmed)
    print("WHD_3415_B_ORIGINAL_E2E_GREEN", "confirm" if confirmed else "cancel", flush=True)
