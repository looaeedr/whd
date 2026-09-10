from types import SimpleNamespace

import fold_designer_bridge as bridge


class _Workspace:
    def __init__(self, parts):
        self.available_parts = tuple(parts)


class _App(SimpleNamespace):
    pass


def _app(parts, *, stale_mirror=()):
    return _App(
        designer_workspace=_Workspace(parts),
        available_parts=tuple(stale_mirror),
    )


def test_corner_data_part_projection_api_exists():
    assert callable(getattr(bridge, "_phase6_corner_data_part_keys", None)), (
        "T2 requires an authoritative corner-data part projection API"
    )


def test_projection_uses_workspace_authority_not_stale_ui_mirror():
    fn = getattr(bridge, "_phase6_corner_data_part_keys", None)
    assert callable(fn), "corner-data authoritative projection API missing"
    authoritative = (
        "box_body",
        "box_body:left_side",
        "box_body:back",
        "box_body:right_side",
        "box_body:divider:1",
        "head",
        "tail",
        "door_c1_r1",
        "door_c1_r2",
        "base_plate_c1_r1",
        "base_plate_c1_r2",
        "indicator_box",
        "indicator_door",
        "inner_door:main",
    )
    app = _app(authoritative, stale_mirror=("box_body", "head"))

    assert fn(app) == authoritative


def test_projection_tracks_dynamic_topology_without_fixed_whitelist():
    fn = getattr(bridge, "_phase6_corner_data_part_keys", None)
    assert callable(fn), "corner-data authoritative projection API missing"
    app = _app(("box_body", "head", "door_c1_r1"))

    assert fn(app) == ("box_body", "head", "door_c1_r1")

    app.designer_workspace.available_parts = (
        "box_body",
        "box_body:left_side",
        "box_body:back",
        "box_body:right_side",
        "head",
        "door_c1_r1",
        "door_c2_r1",
        "base_plate_c1_r1",
        "box_body:divider:7",
    )
    assert fn(app) == app.designer_workspace.available_parts

    app.designer_workspace.available_parts = ("box_body", "head")
    assert fn(app) == ("box_body", "head")


def test_projection_never_invents_corner_data_as_a_part_and_preserves_stable_keys():
    fn = getattr(bridge, "_phase6_corner_data_part_keys", None)
    assert callable(fn), "corner-data authoritative projection API missing"
    parts = ("box_body", "door_c9_r3", "inner_door:aux", "custom_physical:42")
    result = fn(_app(parts))

    assert result == parts
    assert "截角資料" not in result
    assert all(isinstance(key, str) for key in result)
