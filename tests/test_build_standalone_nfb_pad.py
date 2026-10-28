# -*- coding: utf-8 -*-
"""The distributable is independent of the WHD checkout after extraction."""
import os
import subprocess
import sys
from zipfile import ZipFile

from tools.build_standalone_nfb_pad import SOURCE_FILES, make_archive


def test_portable_package_keeps_one_authoritative_source_and_no_gui_main(tmp_path):
    bundle = make_archive(tmp_path / "portable.zip")
    with ZipFile(bundle) as archive:
        names = set(archive.namelist())
        assert set(SOURCE_FILES).issubset(names)
        assert "ae_engine/__init__.py" in names
        assert "README_獨立工具.txt" in names
        assert "啟動_NFB墊高片.bat" in names
        assert "gui.py" not in names
        assert "config.ini" not in names
        assert "ae_engine/receiving_base_plate_config.py" not in names
        extraction = tmp_path / "extracted"
        archive.extractall(extraction)
    verify = extraction / "verify_standalone.py"
    verify.write_text(
        "from ae_engine.receiving_nfb_pad_standalone import PadSelection, build_pad_preview\n"
        "p = build_pad_preview([PadSelection(1, '士林', '3P400SN'), "
        "PadSelection(1, '士林', '100HN-s')], plate_thickness_mm=2)\n"
        "assert len(p.jobs) == 1\n"
        "assert p.jobs[0].pattern.rise_mm == 39\n"
        "print('PORTABLE_PAD_OK')\n", encoding="utf-8",
    )
    env = {**os.environ, "PYTHONPATH": str(extraction)}
    run = subprocess.run(
        [sys.executable, str(verify)],
        cwd=extraction, env=env, capture_output=True, text=True,
        check=False, timeout=20,
    )
    assert run.returncode == 0, run.stderr
    assert "PORTABLE_PAD_OK" in run.stdout


def test_portable_package_refuses_overwrite(tmp_path):
    from pytest import raises
    path = tmp_path / "portable.zip"
    make_archive(path)
    with raises(FileExistsError):
        make_archive(path)
