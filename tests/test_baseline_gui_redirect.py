# -*- coding: utf-8 -*-
from pathlib import Path


def test_baseline_gui_is_only_a_redirect_to_authoritative_root_gui():
    source = (Path(__file__).parents[1] / "基準檔" / "gui.py").read_text(encoding="utf-8")

    assert len(source.splitlines()) < 100
    assert "runpy.run_path" in source
    assert "PROJECT_ROOT" in source
    assert "os.chdir(PROJECT_ROOT)" in source
