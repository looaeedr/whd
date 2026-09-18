from __future__ import annotations

from types import SimpleNamespace

import gui


class FakeCanvas:
    def __init__(self):
        self.calls = []

    def _record(self, name, *args, **kwargs):
        self.calls.append((name, args, kwargs))
        return len(self.calls)

    def create_rectangle(self, *args, **kwargs):
        return self._record("rectangle", *args, **kwargs)

    def create_line(self, *args, **kwargs):
        return self._record("line", *args, **kwargs)

    def create_text(self, *args, **kwargs):
        return self._record("text", *args, **kwargs)


def test_task4c2_divider_and_frame_overlay_placement_is_stable(monkeypatch):
    import ae_engine.assembly_placement as placement_mod
    import ae_engine.door_dividers as dividers_mod
    import ae_engine.inner_door_frames as frames_mod

    host = gui.Phase6ApplicationHost.__new__(gui.Phase6ApplicationHost)
    canvas = FakeCanvas()
    project_snapshot = {"w": 100.0, "h": 50.0}
    host._compose_phase6_project_snapshot_from_main_gui = lambda: project_snapshot
    host.door_layout_scope = "main"
    host.door_layout_handle_edges = {"0:0": "RIGHT"}

    horizontal = SimpleNamespace(
        stable_id="divider:h",
        axis="HORIZONTAL",
        span=40.0,
        formed_core_depth=12.0,
    )
    vertical = SimpleNamespace(
        stable_id="divider:v",
        axis="VERTICAL",
        span=20.0,
        formed_core_depth=8.0,
    )
    monkeypatch.setattr(
        dividers_mod,
        "derive_box_body_dividers",
        lambda normalized, **kwargs: (horizontal, vertical),
    )

    frame_set = SimpleNamespace(
        inner_door_id="inner-1",
        included_sides=("top", "left", "bottom"),
        spans={"top": 30.0, "left": 20.0, "bottom": 99.0},
    )
    monkeypatch.setattr(
        gui.cabinet_family_policy,
        "has_inner_door_frame_derivation",
        lambda snapshot: True,
    )
    monkeypatch.setattr(
        gui.cabinet_family_policy,
        "derive_inner_door_frame_sets",
        lambda snapshot: (frame_set,),
    )
    monkeypatch.setattr(
        frames_mod,
        "inner_door_frame_stable_id",
        lambda inner_id, side: f"frame:{side}",
    )

    offsets = {
        "divider:h": (0.0, 0.0, 0.0),
        "divider:v": (10.0, 0.0, 0.0),
        "frame:top": (0.0, 10.0, 0.0),
        "frame:left": (-20.0, 0.0, 0.0),
    }
    monkeypatch.setattr(
        placement_mod,
        "resolve_assembly_placement",
        lambda snapshot, stable_id: SimpleNamespace(world_offset=offsets[stable_id]),
    )

    gui.Phase6ApplicationHost._draw_door_layout_dividers_and_frames(
        host,
        canvas,
        2.0,
        100.0,
        200.0,
        [(100.0, (50.0,))],
        [],
        {"t": 2.0, "d": 350.0},
    )

    divider_rects = [
        (args, kwargs)
        for name, args, kwargs in canvas.calls
        if name == "rectangle" and kwargs.get("tags") == ("door_layout_divider",)
    ]
    assert divider_rects == [
        (
            (160.0, 247.0, 240.0, 253.0),
            {
                "fill": "#00d4d4",
                "outline": "#00a3a3",
                "width": 1,
                "tags": ("door_layout_divider",),
            },
        ),
        (
            (217.0, 230.0, 223.0, 270.0),
            {
                "fill": "#00d4d4",
                "outline": "#00a3a3",
                "width": 1,
                "tags": ("door_layout_divider",),
            },
        ),
    ]

    divider_text = next(
        (args, kwargs)
        for name, args, kwargs in canvas.calls
        if name == "text" and kwargs.get("tags") == ("door_layout_divider",)
    )
    assert divider_text == (
        (200.0, 264.0),
        {
            "text": "中隔 W-2T=40.0 mm (成型深=12.0)",
            "fill": "#00d4d4",
            "font": ("Consolas", 9, "bold"),
            "tags": ("door_layout_divider",),
        },
    )

    frame_lines = [
        (args, kwargs)
        for name, args, kwargs in canvas.calls
        if name == "line" and kwargs.get("tags") == ("door_layout_frame",)
    ]
    assert frame_lines == [
        (
            (170.0, 230.0, 230.0, 230.0),
            {
                "fill": "#ff9f0a",
                "width": 2,
                "dash": (6, 3),
                "tags": ("door_layout_frame",),
            },
        ),
        (
            (160.0, 230.0, 160.0, 270.0),
            {
                "fill": "#ff9f0a",
                "width": 2,
                "dash": (6, 3),
                "tags": ("door_layout_frame",),
            },
        ),
    ]

    frame_text = next(
        (args, kwargs)
        for name, args, kwargs in canvas.calls
        if name == "text" and kwargs.get("tags") == ("door_layout_frame",)
    )
    assert frame_text == (
        (200.0, 244.0),
        {
            "text": "內門框 (頂/左/右內縮50mm, 寬=30.0)",
            "fill": "#ff9f0a",
            "font": ("Microsoft JhengHei", 8, "bold"),
            "tags": ("door_layout_frame",),
        },
    )


def test_task4c2_derivation_failures_are_nonfatal(monkeypatch):
    import ae_engine.door_dividers as dividers_mod

    host = gui.Phase6ApplicationHost.__new__(gui.Phase6ApplicationHost)
    canvas = FakeCanvas()
    host._compose_phase6_project_snapshot_from_main_gui = lambda: {"w": 100.0, "h": 50.0}
    host.door_layout_scope = "main"
    host.door_layout_handle_edges = {}

    monkeypatch.setattr(
        dividers_mod,
        "derive_box_body_dividers",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("divider boom")),
    )
    monkeypatch.setattr(
        gui.cabinet_family_policy,
        "has_inner_door_frame_derivation",
        lambda snapshot: (_ for _ in ()).throw(RuntimeError("frame boom")),
    )

    gui.Phase6ApplicationHost._draw_door_layout_dividers_and_frames(
        host,
        canvas,
        1.0,
        0.0,
        0.0,
        [(100.0, (50.0,))],
        [],
        {"t": 2.0},
    )

    assert canvas.calls == []
