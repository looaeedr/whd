from types import SimpleNamespace

import fold_designer_bridge as bridge


def _app(parts, selected):
    workspace = SimpleNamespace(
        available_parts=tuple(parts),
        active_part="door_c1_r1",
        selected_part="door_c1_r1",
    )
    return SimpleNamespace(
        designer_workspace=workspace,
        _phase6_corner_data_selected_part_key=selected,
        _phase6_box_body_active_piece_key=None,
    )


def _projection(app):
    adapter = getattr(bridge, "_phase6_corner_data_unfold_projection", None)
    assert callable(adapter), "T4 requires the authoritative corner-data unfold adapter"
    return adapter(app)


def test_regular_part_projection_reuses_existing_authoritative_render_data_sink(monkeypatch):
    app = _app(("box_body", "head", "tail"), "head")
    sentinel = object()
    calls = []

    monkeypatch.setattr(
        bridge,
        "_phase6_render_data_for_blank",
        lambda owner, key: calls.append(("blank", owner, key)) or sentinel,
    )
    monkeypatch.setattr(
        bridge,
        "_phase6_box_body_piece_render_data",
        lambda *_args: (_ for _ in ()).throw(AssertionError("wrong multipart sink")),
    )
    before = (app.designer_workspace.active_part, app.designer_workspace.selected_part)

    result = _projection(app)

    assert result.part_key == "head"
    assert result.render_data is sentinel
    assert calls == [("blank", app, "head")]
    assert (app.designer_workspace.active_part, app.designer_workspace.selected_part) == before


def test_multipart_physical_child_projection_reuses_resolved_aggregate_piece_sink(monkeypatch):
    app = _app(
        ("box_body", "box_body:left_side", "box_body:back", "box_body:right_side", "head"),
        "box_body:back",
    )
    sentinel = object()
    calls = []

    monkeypatch.setattr(
        bridge,
        "_phase6_box_body_piece_render_data",
        lambda owner, key: calls.append(("piece", owner, key)) or sentinel,
    )
    monkeypatch.setattr(
        bridge,
        "_phase6_render_data_for_blank",
        lambda *_args: (_ for _ in ()).throw(AssertionError("aggregate/regular sink used for physical child")),
    )

    result = _projection(app)

    assert result.part_key == "box_body:back"
    assert result.render_data is sentinel
    assert calls == [("piece", app, "box_body:back")]


def test_multipart_aggregate_parent_reuses_authoritative_aggregate_render_data_sink(monkeypatch):
    app = _app(
        ("box_body", "box_body:left_side", "box_body:back", "box_body:right_side", "head"),
        "box_body",
    )
    sentinel = object()
    calls = []
    before = (app.designer_workspace.active_part, app.designer_workspace.selected_part)

    monkeypatch.setattr(
        bridge,
        "_phase6_render_data_for_blank",
        lambda owner, key: calls.append(("blank", owner, key)) or sentinel,
    )
    monkeypatch.setattr(
        bridge,
        "_phase6_box_body_piece_render_data",
        lambda *_args: (_ for _ in ()).throw(AssertionError("aggregate parent used child sink")),
    )

    result = _projection(app)

    assert result is not None
    assert result.part_key == "box_body"
    assert result.render_data is sentinel
    assert calls == [("blank", app, "box_body")]
    assert (app.designer_workspace.active_part, app.designer_workspace.selected_part) == before


def test_stale_selected_identity_fails_closed_without_querying_render_data(monkeypatch):
    app = _app(("box_body", "head", "tail"), "door_c1_r2")

    monkeypatch.setattr(
        bridge,
        "_phase6_render_data_for_blank",
        lambda *_args: (_ for _ in ()).throw(AssertionError("stale key queried")),
    )
    monkeypatch.setattr(
        bridge,
        "_phase6_box_body_piece_render_data",
        lambda *_args: (_ for _ in ()).throw(AssertionError("stale key queried")),
    )

    assert _projection(app) is None


def test_missing_selection_returns_no_projection(monkeypatch):
    app = _app(("box_body", "head", "tail"), None)

    monkeypatch.setattr(
        bridge,
        "_phase6_render_data_for_blank",
        lambda *_args: (_ for _ in ()).throw(AssertionError("missing selection queried")),
    )
    monkeypatch.setattr(
        bridge,
        "_phase6_box_body_piece_render_data",
        lambda *_args: (_ for _ in ()).throw(AssertionError("missing selection queried")),
    )

    assert _projection(app) is None


def test_adapter_does_not_use_display_label_or_mutate_manufacturing_selection(monkeypatch):
    app = _app(("box_body", "head", "tail"), "tail")
    sentinel = object()
    before = (app.designer_workspace.active_part, app.designer_workspace.selected_part)

    monkeypatch.setattr(bridge, "_phase6_part_label", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("display label used as authority")))
    monkeypatch.setattr(bridge, "_phase6_render_data_for_blank", lambda _owner, key: sentinel if key == "tail" else None)

    result = _projection(app)

    assert result.part_key == "tail"
    assert result.render_data is sentinel
    assert (app.designer_workspace.active_part, app.designer_workspace.selected_part) == before
