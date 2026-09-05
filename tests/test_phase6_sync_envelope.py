from __future__ import annotations

import tkinter as tk

import fold_designer_bridge as bridge
from test_phase6_settings_center_bridge import _snapshot


def _make_app(monkeypatch, published):
    monkeypatch.setattr(bridge, "project_features_to_original_holes", lambda *a, **k: [])
    root = tk.Tk(); root.withdraw()
    win = tk.Toplevel(root); win.withdraw()
    app = bridge.Phase6FoldDesignerApp(win, _snapshot(), on_live_sync=lambda payload: published.append(payload))
    root.update_idletasks()
    published.clear()
    return root, win, app


def test_equivalent_external_envelope_does_not_write_tk_var_or_echo(monkeypatch):
    published = []
    root, win, app = _make_app(monkeypatch, published)
    try:
        writes = {"count": 0}
        var = app.left_global_vars["w"]
        var.trace_add("write", lambda *_: writes.__setitem__("count", writes["count"] + 1))
        current = float(app._settings_values["w"])
        envelope = {
            "origin": "main_gui",
            "revision": 1,
            "transaction_id": "main:1",
            "delta": {"settings": {"w": current}},
            "fingerprint": "equivalent",
        }

        result = app.apply_external_sync(envelope)
        root.update_idletasks()

        assert result == {}
        assert writes["count"] == 0
        assert published == []
    finally:
        root.destroy()


def test_stale_external_revision_cannot_overwrite_newer_state(monkeypatch):
    published = []
    root, win, app = _make_app(monkeypatch, published)
    try:
        start = float(app._settings_values["w"])
        fresh = {
            "origin": "main_gui",
            "revision": 2,
            "transaction_id": "main:2",
            "delta": {"settings": {"w": start + 10.0}},
            "fingerprint": "fresh",
        }
        stale = {
            "origin": "main_gui",
            "revision": 1,
            "transaction_id": "main:1",
            "delta": {"settings": {"w": start + 20.0}},
            "fingerprint": "stale",
        }

        app.apply_external_sync(fresh)
        app.apply_external_sync(stale)

        assert float(app._settings_values["w"]) == start + 10.0
        assert published == []
    finally:
        root.destroy()


def test_true_3d_edit_publishes_one_revisioned_envelope(monkeypatch):
    published = []
    root, win, app = _make_app(monkeypatch, published)
    try:
        app.left_global_vars["w"].set("640")
        app.flush_pending_settings()
        root.update_idletasks()

        assert len(published) == 1
        envelope = published[0]
        assert envelope["origin"] == "fold_designer"
        assert envelope["revision"] >= 1
        assert envelope["transaction_id"]
        assert isinstance(envelope["delta"], dict) and envelope["delta"]
        assert len(envelope["fingerprint"]) == 64
        assert envelope["settings"]["w"] == 640.0
    finally:
        root.destroy()


def test_force_publish_does_not_echo_equivalent_state_or_bump_revision(monkeypatch):
    published = []
    root, win, app = _make_app(monkeypatch, published)
    try:
        app.left_global_vars["w"].set("640")
        app.flush_pending_settings()
        root.update_idletasks()
        assert published
        revision = published[-1]["revision"]
        published.clear()

        assert app._phase6_publish_live_state(force=True) is False
        assert published == []
        assert app._phase6_sync_revision == revision
    finally:
        root.destroy()


def test_force_publish_syncs_stale_host_relief_even_when_live_fingerprint_is_current(monkeypatch):
    published = []
    root, win, app = _make_app(monkeypatch, published)
    try:
        # Initialization may solve/normalize canonical relief while live publish
        # is suppressed.  The local last-live fingerprint can therefore already
        # describe the canonical state while the host snapshot still carries an
        # older relief contract.  A force publish must sync that real host delta
        # exactly once without weakening the equivalent-state anti-echo rule.
        app._phase6_input_snapshot["assembly_relief"] = {
            "enabled": True,
            "source": {"legacy_contract": True},
            "parts": {},
        }
        published.clear()

        assert app._phase6_publish_live_state(force=True) is True
        assert len(published) == 1
        assert "assembly_relief" in published[0]["delta"]
        assert app._phase6_publish_live_state(force=True) is False
        assert len(published) == 1
    finally:
        root.destroy()


def test_initialization_is_atomic_and_does_not_publish_intermediate_snapshot(monkeypatch):
    published = []
    monkeypatch.setattr(bridge, "project_features_to_original_holes", lambda *a, **k: [])
    root = tk.Tk(); root.withdraw()
    win = tk.Toplevel(root); win.withdraw()
    try:
        app = bridge.Phase6FoldDesignerApp(
            win,
            _snapshot(),
            on_live_sync=lambda payload: published.append(payload),
        )
        root.update_idletasks()

        assert app._phase6_sync_ready is True
        assert published == []
        assert app._phase6_publish_live_state(force=True) is False
        assert published == []
        assert app._phase6_sync_revision == 0
    finally:
        root.destroy()


def test_initialization_prefers_authoritative_current_dimensions_over_persisted_settings(monkeypatch):
    published = []
    snapshot = _snapshot()
    snapshot["w"] = 777
    snapshot["h"] = 888
    snapshot["d"] = 333
    snapshot["settings"] = dict(snapshot["settings"])
    snapshot["settings"].update({"w": 500.0, "h": 600.0, "d": 200.0})
    monkeypatch.setattr(bridge, "project_features_to_original_holes", lambda *a, **k: [])
    root = tk.Tk(); root.withdraw()
    win = tk.Toplevel(root); win.withdraw()
    try:
        app = bridge.Phase6FoldDesignerApp(
            win,
            snapshot,
            on_live_sync=lambda payload: published.append(payload),
        )
        root.update_idletasks()

        assert app._settings_values["w"] == 777
        assert app._settings_values["h"] == 888
        assert app._settings_values["d"] == 333
        assert app.left_global_vars["w"].get() == "777"
        assert app.left_global_vars["h"].get() == "888"
        assert app.left_global_vars["d"].get() == "333"
        assert published == []
    finally:
        root.destroy()


def test_initialization_resolves_manufacturing_at_most_once(monkeypatch):
    published = []
    counts = {"manufacturing": 0}
    monkeypatch.setattr(bridge, "project_features_to_original_holes", lambda *a, **k: [])
    original_resolve = bridge._phase6_resolve_manufacturing_geometry

    def counted_resolve(app, *args, **kwargs):
        signature = bridge._phase6_manufacturing_state_signature(app)
        cached = getattr(app, "_phase6_last_resolved_manufacturing_geometry", None)
        cached_signature = getattr(app, "_phase6_last_resolved_manufacturing_signature", None)
        if cached is None or cached_signature != signature:
            counts["manufacturing"] += 1
        return original_resolve(app, *args, **kwargs)

    monkeypatch.setattr(bridge, "_phase6_resolve_manufacturing_geometry", counted_resolve)
    root = tk.Tk(); root.withdraw()
    win = tk.Toplevel(root); win.withdraw()
    try:
        bridge.Phase6FoldDesignerApp(
            win,
            _snapshot(),
            on_live_sync=lambda payload: published.append(payload),
        )
        root.update_idletasks()

        assert counts["manufacturing"] <= 1
        assert published == []
    finally:
        root.destroy()
