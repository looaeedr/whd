# -*- coding: utf-8 -*-
from __future__ import annotations

import configparser
from pathlib import Path
from types import SimpleNamespace

import pytest

import phase6_settings_center as settings


class FakeAE:
    def __init__(self, ini_path: Path):
        self.INI_PATH = str(ini_path)
        self.config = configparser.ConfigParser()
        self.default_config = {
            "DEFAULT_SIZES": {"W": 350, "H": 550, "D": 200, "T": 2, "FW": 25},
            "OUTPUT": {"draw_stock": False},
            "UI": {"text_size": "small"},
        }
        self.RELIEF_CONFIG = SimpleNamespace(
            top_secondary_x_factor=0.5,
            top_secondary_depth_factor=2.0,
            bottom_x_factor=0.5,
            bottom_y_factor=0.5,
        )


@pytest.fixture
def fake_ae(tmp_path):
    ini_path = tmp_path / "config.ini"
    parser = configparser.ConfigParser()
    parser["DEFAULT_SIZES"] = {"W": "400", "H": "600", "D": "250", "T": "2", "FW": "25"}
    parser["OUTPUT"] = {"draw_stock": "false"}
    parser["UI"] = {"text_size": "small"}
    with ini_path.open("w", encoding="utf-8") as fh:
        parser.write(fh)
    return FakeAE(ini_path)


def read_ini_w(path) -> float:
    parser = configparser.ConfigParser()
    parser.read(path, encoding="utf-8")
    return parser.getfloat("DEFAULT_SIZES", "W")


def test_settings_service_snapshot_is_defensive(fake_ae):
    service = settings.SettingsService(fake_ae)
    snapshot = service.snapshot()
    copied = snapshot.as_dict()
    copied["w"] = 999

    assert snapshot["w"] == pytest.approx(400.0)
    assert service.snapshot()["w"] == pytest.approx(400.0)


def test_update_changes_runtime_and_ae_without_persisting(fake_ae):
    service = settings.SettingsService(fake_ae)

    service.update({"w": 450})

    assert service.snapshot()["w"] == pytest.approx(450.0)
    assert fake_ae.W == pytest.approx(450.0)
    assert read_ini_w(fake_ae.INI_PATH) == pytest.approx(400.0)


def test_persist_explicit_draft_does_not_commit_runtime(fake_ae):
    service = settings.SettingsService(fake_ae)
    service.update({"w": 450})

    service.persist_defaults(values={"w": 500}, keys=("w",))

    assert read_ini_w(fake_ae.INI_PATH) == pytest.approx(500.0)
    assert service.snapshot()["w"] == pytest.approx(450.0)
    assert fake_ae.W == pytest.approx(450.0)


def test_factory_snapshot_ignores_persisted_and_runtime_changes(fake_ae):
    service = settings.SettingsService(fake_ae)
    assert service.factory_snapshot()["w"] == pytest.approx(350.0)

    service.update({"w": 450})
    service.persist_defaults(values={"w": 500}, keys=("w",))

    assert service.factory_snapshot()["w"] == pytest.approx(350.0)
    assert service.snapshot()["w"] == pytest.approx(450.0)


def test_new_service_uses_newly_persisted_defaults(fake_ae):
    service = settings.SettingsService(fake_ae)
    service.persist_defaults(values={"w": 500}, keys=("w",))

    restarted = settings.SettingsService(fake_ae)

    assert restarted.snapshot()["w"] == pytest.approx(500.0)
    assert fake_ae.W == pytest.approx(500.0)


def test_main_gui_setting_edit_updates_service_and_ae():
    import os
    if not os.environ.get("DISPLAY"):
        pytest.skip("需要 Tk 顯示環境")
    import tkinter as tk
    import gui
    from ae_engine import ae

    original_w = float(getattr(ae, "W", 400.0))
    root = tk.Tk()
    root.withdraw()
    app = None
    try:
        app = gui.BoxCalculatorGUI(root)
        app.w_var.set("451")
        root.update_idletasks()
        root.update()

        assert app.settings_service.snapshot()["w"] == pytest.approx(451.0)
        assert ae.W == pytest.approx(451.0)
    finally:
        if app is not None and hasattr(app, "settings_service"):
            app.settings_service.update({"w": original_w})
        root.destroy()


def test_main_gui_save_3d_draft_as_defaults_does_not_commit_runtime(fake_ae, monkeypatch):
    import gui

    app = object.__new__(gui.BoxCalculatorGUI)
    app.settings_service = settings.SettingsService(fake_ae)
    monkeypatch.setattr(gui, "ae", fake_ae)
    monkeypatch.setattr(gui, "save_corner_defaults_to_ini", lambda *args, **kwargs: None)

    app._save_fold_designer_defaults(
        settings.GLOBAL_CONTEXT,
        {"w": 500.0},
        corner_state={},
        corner_pair_same={},
    )

    assert read_ini_w(fake_ae.INI_PATH) == pytest.approx(500.0)
    assert app.settings_service.snapshot()["w"] == pytest.approx(400.0)
    assert fake_ae.W == pytest.approx(400.0)


def test_3d_draft_cancel_keeps_committed_settings_service_and_ae():
    import os
    if not os.environ.get("DISPLAY"):
        pytest.skip("需要 Tk 顯示環境")
    import tkinter as tk
    import gui
    from ae_engine import ae

    original_w = float(getattr(ae, "W", 400.0))
    root = tk.Tk(); root.withdraw()
    app = None
    try:
        app = gui.BoxCalculatorGUI(root)
        app.w_var.set("400")
        designer = app.open_original_fold_designer()
        root.update_idletasks(); root.update()

        designer._settings_values["w"] = 500.0
        designer._phase6_input_snapshot["w"] = 500.0

        assert app.settings_service.snapshot()["w"] == pytest.approx(400.0)
        assert ae.W == pytest.approx(400.0)

        designer.cancel_corner_transaction()
        root.update_idletasks(); root.update()

        assert app.settings_service.snapshot()["w"] == pytest.approx(400.0)
        assert ae.W == pytest.approx(400.0)
    finally:
        if app is not None and hasattr(app, "settings_service"):
            app.settings_service.update({"w": original_w})
        try:
            if app is not None and app.fold_designer_window is not None:
                app.fold_designer_window.destroy()
        except Exception:
            pass
        root.destroy()


def test_3d_live_setting_edit_commits_settings_service_and_ae_without_confirm():
    import os
    if not os.environ.get("DISPLAY"):
        pytest.skip("需要 Tk 顯示環境")
    import tkinter as tk
    import gui
    from ae_engine import ae

    original_w = float(getattr(ae, "W", 400.0))
    root = tk.Tk(); root.withdraw()
    app = None
    try:
        app = gui.BoxCalculatorGUI(root)
        app.w_var.set("400")
        designer = app.open_original_fold_designer()
        root.update_idletasks(); root.update()

        designer.left_global_vars["w"].set("500")
        designer.flush_pending_settings()
        for _ in range(4):
            root.update_idletasks(); root.update()

        assert app.settings_service.snapshot()["w"] == pytest.approx(500.0)
        assert ae.W == pytest.approx(500.0)
    finally:
        if app is not None and hasattr(app, "settings_service"):
            app.settings_service.update({"w": original_w})
        try:
            if app is not None and app.fold_designer_window is not None:
                app.fold_designer_window.destroy()
        except Exception:
            pass
        root.destroy()
