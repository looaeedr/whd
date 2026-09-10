from types import SimpleNamespace

import fold_designer_bridge as bridge


class _Var:
    def __init__(self, value=""):
        self.value = value

    def set(self, value):
        self.value = value

    def get(self):
        return self.value


class _Host:
    def __init__(self):
        self.visible = True
        self.pack_calls = []

    def pack(self, *args, **kwargs):
        self.visible = True
        self.pack_calls.append((args, kwargs))

    def pack_forget(self):
        self.visible = False


class _Workspace:
    def __init__(self):
        self.available_parts = ("box_body", "head", "tail")
        self.active_part = "head"
        self.selected_part = "head"


def _fake_designer():
    return SimpleNamespace(
        part_var=_Var("組合體"),
        _phase6_3d_display_mode="assembly",
        designer_workspace=_Workspace(),
        fold_editor_host=_Host(),
        assembly_parts_panel=_Host(),
        corner_data_panel=_Host(),
        _phase6_pending_settings={},
        available_parts=("box_body", "head", "tail"),
        active_part_key="head",
    )


def test_corner_data_mode_api_exists():
    assert callable(getattr(bridge, "_phase6_show_corner_data", None)), (
        "T1 requires a dedicated Fold Designer corner-data navigation mode"
    )


def test_corner_data_mode_is_view_only_and_not_a_fake_part(monkeypatch):
    fn = getattr(bridge, "_phase6_show_corner_data", None)
    assert callable(fn), "corner-data mode API missing"
    app = _fake_designer()
    before = (
        app.designer_workspace.available_parts,
        app.designer_workspace.active_part,
        app.designer_workspace.selected_part,
        app.available_parts,
    )

    publish_calls = []
    monkeypatch.setattr(bridge, "_phase6_publish_live_state", lambda *_: publish_calls.append(True))

    fn(app)

    after = (
        app.designer_workspace.available_parts,
        app.designer_workspace.active_part,
        app.designer_workspace.selected_part,
        app.available_parts,
    )
    assert after == before
    assert publish_calls == []
    assert "截角資料" not in app.available_parts
    assert "截角資料" not in app.designer_workspace.available_parts
    assert app.part_var.get() == "截角資料"
    assert app._phase6_3d_display_mode == "corner_data"


def test_corner_data_mode_switching_is_idempotent(monkeypatch):
    fn = getattr(bridge, "_phase6_show_corner_data", None)
    assert callable(fn), "corner-data mode API missing"
    app = _fake_designer()
    monkeypatch.setattr(bridge, "_phase6_publish_live_state", lambda *_: (_ for _ in ()).throw(AssertionError("view switch published production state")))

    fn(app)
    first = (
        app.part_var.get(),
        app._phase6_3d_display_mode,
        app.designer_workspace.active_part,
        app.designer_workspace.selected_part,
    )
    fn(app)
    second = (
        app.part_var.get(),
        app._phase6_3d_display_mode,
        app.designer_workspace.active_part,
        app.designer_workspace.selected_part,
    )
    assert second == first
