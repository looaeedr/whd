# -*- coding: utf-8 -*-
"""#2382 actual project source for packaged GUI Windows acceptance."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import sys

import pytest

from tools.issue2382_packaged_gui_open_probe import _make_real_gui_project


@pytest.mark.skipif(
    sys.platform != "win32" and not os.environ.get("DISPLAY"),
    reason="real Tk display required for the GUI Save action",
)
def test_packaged_gui_probe_source_is_real_gui_saved_valid_project(tmp_path):
    from phase6_project_file import read_project

    project = tmp_path / "已儲存 專案.p6fold"
    result = _make_real_gui_project(project)
    original = project.read_bytes()
    assert project.is_file()
    assert len(original) > 100
    assert result["sha256"] == hashlib.sha256(original).hexdigest()
    loaded = read_project(project)
    assert result["schema"] == loaded["schema"]
    assert result["model"] == loaded["snapshot"]["model"]
    assert "workspace" in loaded["snapshot"]
    assert loaded["final_geometry"] == {}
    assert project.read_bytes() == original


def test_packaged_gui_probe_rejects_wrong_platform_without_launch(monkeypatch, tmp_path):
    # Fail-closed: Linux product CI cannot pretend it ran Windows EXE.
    import tools.issue2382_packaged_gui_open_probe as probe
    if os.name == "nt":
        pytest.skip("non-Windows refusal contract")
    monkeypatch.setattr(sys, "argv", [
        "issue2382_packaged_gui_open_probe.py",
        "--exe", str(tmp_path / "fake-WHD.exe"),
        "--out", str(tmp_path),
    ])
    with pytest.raises(RuntimeError, match="W07_REQUIRES_ACTUAL_WINDOWS_EXE"):
        probe.main()
