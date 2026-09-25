# -*- coding: utf-8 -*-
"""Issue #616 / B3 UI-R3 exact visible-scene diagnostic RED."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest


pytestmark = pytest.mark.skipif(
    not (os.name == "nt" or os.environ.get("DISPLAY")),
    reason="#616 UI-R3 requires a real Tk/Xvfb display",
)

_REQUIRED_FIELDS = {
    "transition_id",
    "sequence",
    "scene_fingerprint",
    "cabinet_family",
    "physical_inventory_fingerprint",
    "transition_stage",
}


def _pump(root, count=3):
    for _ in range(count):
        root.update_idletasks()
        root.update()


def _artifact_path() -> Path:
    return Path(
        os.environ.get(
            "WHD_UI_R3_ARTIFACT",
            "/tmp/issue616/visible-scene-diagnostic.json",
        )
    )


def _write_artifact(payload) -> None:
    path = _artifact_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def test_ui_r3_exact_visible_scene_commit_diagnostic_for_vault_to_receiving():
    import tkinter as tk
    import gui

    root = tk.Tk()
    root.withdraw()
    app = gui.BoxCalculatorGUI(root)
    designer = None
    artifact = {
        "schema": "WHD_UI_R3_VISIBLE_SCENE_DIAGNOSTIC_V1",
        "source_family": "金庫型",
        "target_family": "受電箱",
        "records": [],
        "first_bad_visible_commit": None,
        "status": "HARNESS_STARTED",
    }
    try:
        app.baseline_var.set("金庫型")
        _pump(root)
        designer = app.open_original_fold_designer()
        designer.root.deiconify()
        designer.root.geometry("1120x720+0+0")
        _pump(root)

        canvas = designer.renderer.canvas.get_tk_widget()
        assert canvas.winfo_manager(), "UI-R3 harness requires the 3D canvas to be visible"
        assert canvas.winfo_width() > 1 and canvas.winfo_height() > 1

        # Exact user path: a live non-Receiving scene is already visible, then
        # the operator switches family to Receiving.
        designer.baseline_model_var.set("受電箱")
        _pump(root, 6)

        records = getattr(designer, "_phase6_visible_scene_commit_records", None)
        artifact["records"] = list(records or ())
        artifact["status"] = "RECORDED" if records else "INSTRUMENTATION_MISSING"

        assert records, (
            "UI-R3 RED: authoritative Final Scene visible-commit seam exposes no "
            "ordered diagnostic records for the live family switch"
        )

        for index, raw in enumerate(records):
            record = dict(raw)
            missing = sorted(_REQUIRED_FIELDS - set(record))
            assert not missing, (
                f"UI-R3 diagnostic record {index} missing required fields: {missing}"
            )
            assert int(record["sequence"]) == index + 1

        transition_ids = {str(dict(row)["transition_id"]) for row in records}
        assert len(transition_ids) == 1, (
            f"UI-R3 switch must have one transition_id, got {transition_ids!r}"
        )

        # The diagnostic owner, not this test, classifies the first invalid
        # visible commit. B3 only consumes that exact durable observation.
        first_bad = next(
            (
                dict(row)
                for row in records
                if bool(dict(row).get("invalid_visible_commit", False))
            ),
            None,
        )
        artifact["first_bad_visible_commit"] = first_bad

        final = dict(records[-1])
        assert str(final["cabinet_family"]) == "受電箱", (
            f"final authoritative visible commit must be Receiving: {final!r}"
        )
        assert str(final["transition_stage"]) in {"final", "finalize", "committed"}, (
            f"final visible commit is not marked authoritative-final: {final!r}"
        )

        assert first_bad is not None, (
            "UI-R3 RED expectation not reproduced: no invalid intermediate visible "
            "commit was observed on the exact 金庫型→受電箱 3D-visible path"
        )
        artifact["status"] = "FIRST_BAD_VISIBLE_COMMIT_IDENTIFIED"
    finally:
        _write_artifact(artifact)
        if designer is not None:
            try:
                designer.root.destroy()
            except Exception:
                pass
        try:
            root.destroy()
        except Exception:
            pass
