"""#1959: preserve Windows-native CADCraft evidence boundaries in CI.

The official Windows x64 command-line proof is not a local WHD GUI UAT.
These guards prevent regressions to unverified binaries, missing SHA, or
accidental claims that Windows manual acceptance is already complete.
"""
from pathlib import Path


def test_official_cadcraft_win_x64_cli_is_publisher_sha256_verified():
    workflow=Path(".github/workflows/whd-issue1959-cadcraft-command-draw.yml").read_text(
        encoding="utf-8")
    assert "windows-native-cadcraft-commands:" in workflow
    assert "runs-on: windows-2022" in workflow
    assert "cadcraft-0.8.0-windows-x64-portable.zip" in workflow
    assert "SHA256SUMS.txt" in workflow
    assert "Get-FileHash" in workflow
    assert "CADCRAFT_OFFICIAL_WINDOWS_SHA256_MISMATCH" in workflow
    assert "PYTHONIOENCODING: utf-8" in workflow


def test_windows_ci_runs_real_wdh_manufacturing_without_gui_uat_claim():
    workflow=Path(".github/workflows/whd-issue1959-cadcraft-command-draw.yml").read_text(
        encoding="utf-8")
    assert "tools.issue1959_whd_cadcraft_command_draw" in workflow
    assert "tools.issue1959_cadcraft_session_trial" in workflow
    assert "tools.issue1959_whd_real_manufacturing_parity" in workflow
    assert "work/issue1959-win/whd-manufacturing-proof.json" in workflow
    assert 'p["manufacturing_cutting_from_whd"]' in workflow
    assert 'not p["windows_gui_uat_completed"]' in workflow
    assert "issue1959-Windows-x64-native-CADCraft-WHD-manufacturing-TEST-ONLY" in workflow
