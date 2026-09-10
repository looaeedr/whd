from types import SimpleNamespace

import fold_designer_bridge as bridge


def _owner(*, mode="corner_data", revision=0):
    return SimpleNamespace(
        _phase6_3d_display_mode=mode,
        corner_data_canvas=object(),
        _phase6_last_external_revision=revision,
        _phase6_last_external_transaction_id="",
    )


def _envelope(revision, *, value=900.0):
    return {
        "origin": "main_gui",
        "revision": revision,
        "transaction_id": f"tx-{revision}",
        "delta": {"settings": {"w": value}},
    }


def test_authoritative_external_sync_refreshes_visible_corner_data_view_after_apply(monkeypatch):
    owner = _owner()
    calls = []

    monkeypatch.setattr(
        bridge,
        "_phase6_apply_external_settings",
        lambda target, settings: calls.append(("apply", target, dict(settings))) or dict(settings),
    )
    monkeypatch.setattr(
        bridge,
        "_phase6_refresh_corner_data_unfold_view",
        lambda target: calls.append(("refresh", target)) or "refreshed",
    )

    result = bridge._phase6_apply_external_sync(owner, _envelope(1))

    assert result == {"w": 900.0}
    assert calls == [
        ("apply", owner, {"w": 900.0}),
        ("refresh", owner),
    ]


def test_authoritative_external_sync_does_not_refresh_hidden_corner_data_view(monkeypatch):
    owner = _owner(mode="assembly")
    calls = []

    monkeypatch.setattr(
        bridge,
        "_phase6_apply_external_settings",
        lambda target, settings: calls.append(("apply", target, dict(settings))) or dict(settings),
    )
    monkeypatch.setattr(
        bridge,
        "_phase6_refresh_corner_data_unfold_view",
        lambda target: calls.append(("refresh", target)) or "refreshed",
    )

    result = bridge._phase6_apply_external_sync(owner, _envelope(1))

    assert result == {"w": 900.0}
    assert calls == [("apply", owner, {"w": 900.0})]


def test_replayed_external_revision_is_noop_and_cannot_refresh_view(monkeypatch):
    owner = _owner(revision=3)
    calls = []

    monkeypatch.setattr(
        bridge,
        "_phase6_apply_external_settings",
        lambda target, settings: calls.append(("apply", target, dict(settings))) or dict(settings),
    )
    monkeypatch.setattr(
        bridge,
        "_phase6_refresh_corner_data_unfold_view",
        lambda target: calls.append(("refresh", target)) or "refreshed",
    )

    assert bridge._phase6_apply_external_sync(owner, _envelope(3)) == {}
    assert calls == []
    assert owner._phase6_last_external_revision == 3


def test_repeated_authoritative_revisions_refresh_visible_view_once_per_commit(monkeypatch):
    owner = _owner()
    calls = []

    monkeypatch.setattr(
        bridge,
        "_phase6_apply_external_settings",
        lambda target, settings: calls.append(("apply", dict(settings))) or dict(settings),
    )
    monkeypatch.setattr(
        bridge,
        "_phase6_refresh_corner_data_unfold_view",
        lambda target: calls.append(("refresh", target._phase6_last_external_revision)),
    )

    bridge._phase6_apply_external_sync(owner, _envelope(1, value=900.0))
    bridge._phase6_apply_external_sync(owner, _envelope(2, value=910.0))

    assert calls == [
        ("apply", {"w": 900.0}),
        ("refresh", 1),
        ("apply", {"w": 910.0}),
        ("refresh", 2),
    ]
