from __future__ import annotations

import os

import pytest

from ae_engine.door_dividers import derive_box_body_dividers
from tests.test_issue39_divider_relief import _snapshot, _body_part, _divider_part


def _profile_band(profile, phase6_key: str) -> tuple[float, float]:
    cursor = 0.0
    for row in tuple(profile or ()):
        length = float(getattr(row, "length", 0.0))
        if str(getattr(row, "phase6_key", "") or "") == str(phase6_key):
            return cursor, cursor + length
        cursor += length
    raise AssertionError(f"missing profile band {phase6_key!r}")


def _skin_planes_for_band(skins, start: float, end: float, *, tol: float = 1e-6) -> tuple[float, ...]:
    planes = []
    for skin in tuple(skins or ()):
        cx = sum(float(point[0]) for point in skin.flat) / 3.0
        if not (float(start) + tol < cx < float(end) - tol):
            continue
        zs = tuple(float(point[2]) for point in skin.world)
        # The FW band is a formed planar flange. Ignore triangles from another
        # flat band rather than inventing a world-coordinate oracle.
        if max(zs) - min(zs) > tol:
            continue
        planes.append(sum(zs) / len(zs))
    if not planes:
        raise AssertionError(f"no planar skin triangles in flat band {start}..{end}")
    unique = []
    for value in sorted(planes):
        if not unique or abs(value - unique[-1]) > 1e-5:
            unique.append(value)
    return tuple(unique)


def _fw_plane_evidence(overrides=None):
    import fold_designer_bridge as bridge

    snapshot = _snapshot()
    snapshot.update(dict(overrides or {}))
    body = _body_part(snapshot)
    divider, divider_part = _divider_part(snapshot)
    world = bridge._phase6_build_joint_world_geometry(
        (body, divider_part),
        (snapshot["w"], snapshot["h"], snapshot["d"]),
        snapshot["t"],
    )

    piece_by_role = {
        str(piece.role): piece
        for piece in tuple(body.render_data.pieces or ())
    }
    left_piece = piece_by_role["left_side"]
    right_piece = piece_by_role["right_side"]

    left_band = _profile_band(left_piece.fold_profile, "fw_left")
    right_band = _profile_band(right_piece.fold_profile, "fw_right")

    # Receiving Divider 18/FW/106/17: second band is the shared FW band.
    divider_fw_key = str(divider.fold_profile[1].phase6_key)
    divider_band = _profile_band(divider.fold_profile, divider_fw_key)

    left_planes = _skin_planes_for_band(
        world["mapped_skin_triangles_by_part"]["box_body:left_side"], *left_band
    )
    right_planes = _skin_planes_for_band(
        world["mapped_skin_triangles_by_part"]["box_body:right_side"], *right_band
    )
    divider_planes = _skin_planes_for_band(
        world["mapped_skin_triangles_by_part"][divider.stable_id], *divider_band
    )
    return snapshot, body, divider, divider_part, left_planes, right_planes, divider_planes


def _assert_same_plane_set(actual, expected, *, abs_tol=1e-5):
    assert len(actual) == len(expected), (actual, expected)
    for got, want in zip(actual, expected):
        assert got == pytest.approx(want, abs=abs_tol)


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="requires Tk display")
def test_r1_exact_3d_user_path_auto_builds_three_receiving_box_body_input_sections():
    import tkinter as tk
    import gui

    root = tk.Tk()
    root.withdraw()
    designer = None
    try:
        app = gui.BoxCalculatorGUI(root)
        app.baseline_var.set("金庫型")
        root.update_idletasks(); root.update()

        designer = app.open_original_fold_designer()
        designer.root.deiconify()
        designer.root.geometry("1120x720+0+0")
        root.update_idletasks(); root.update()

        # Exact user path: switch Family, activate Box Body, then inspect what
        # the 3D input area built by itself. No manual invalidate/render helper.
        designer.baseline_model_var.set("受電箱")
        root.update_idletasks(); root.update()
        designer.activate_part("box_body")
        root.update_idletasks(); root.update()

        assert tuple(designer.box_body_piece_input_sections) == (
            "box_body:left_side",
            "box_body:back",
            "box_body:right_side",
        )
        for key in designer.box_body_piece_input_sections:
            section = designer.box_body_piece_input_sections[key]
            assert bool(section.winfo_ismapped()), f"{key} section is not visible"
    finally:
        try:
            if designer is not None:
                designer.root.destroy()
        except Exception:
            pass
        root.destroy()


def test_r2_divider_fw_physical_skins_are_flush_with_both_box_body_fw_skins():
    _snapshot_data, _body, _divider, _divider_part, left, right, divider = _fw_plane_evidence()
    _assert_same_plane_set(left, right)
    _assert_same_plane_set(divider, left)


@pytest.mark.parametrize(
    "overrides",
    (
        {"d": 400.0},
        {"fw": 31.0},
        {"t": 3.0, "fw": 31.0},
    ),
)
def test_r2b_fw_face_flush_survives_dimension_changes(overrides):
    _snapshot_data, _body, _divider, _divider_part, left, right, divider = _fw_plane_evidence(overrides)
    _assert_same_plane_set(left, right)
    _assert_same_plane_set(divider, left)


def test_r3_relief_cannot_be_accepted_as_verified_before_fw_face_flush_is_true():
    import fold_designer_bridge as bridge

    snapshot, body, divider, divider_part, left, right, divider_planes = _fw_plane_evidence()
    body_fw_flush = (
        len(left) == len(right) == len(divider_planes)
        and all(abs(a - b) <= 1e-5 for a, b in zip(left, right))
        and all(abs(a - b) <= 1e-5 for a, b in zip(divider_planes, left))
    )

    solved_parts, _diagnostics, _joints = bridge._phase6_resolve_family_divider_reliefs(
        (body, divider_part),
        finished_dimensions=(snapshot["w"], snapshot["h"], snapshot["d"]),
        sheet_thickness=snapshot["t"],
    )
    solved = next(part for part in solved_parts if part.part_key == divider.stable_id)
    relief = dict(solved.render_data.metadata.get("divider_assembly_relief") or {})

    assert body_fw_flush, (
        "Divider relief is being evaluated before the shared FW formed faces are flush; "
        f"left={left}, right={right}, divider={divider_planes}, relief={relief}"
    )
    assert relief.get("verified") is True



def test_r3b_relief_refuses_verified_when_divider_fw_face_is_displaced():
    from dataclasses import replace
    import fold_designer_bridge as bridge

    snapshot = _snapshot()
    body = _body_part(snapshot)
    divider, divider_part = _divider_part(snapshot)
    x, y, z = (float(v) for v in divider_part.offset)
    displaced = replace(divider_part, offset=(x, y, z + 5.0))

    solved_parts, diagnostics, _joints = bridge._phase6_resolve_family_divider_reliefs(
        (body, displaced),
        finished_dimensions=(snapshot["w"], snapshot["h"], snapshot["d"]),
        sheet_thickness=snapshot["t"],
    )
    solved = next(part for part in solved_parts if part.part_key == divider.stable_id)
    relief = dict(solved.render_data.metadata.get("divider_assembly_relief") or {})

    assert relief.get("verified") is not True
    assert diagnostics
    assert diagnostics[0].candidate_status == "INVALID_DIVIDER_FW_PLACEMENT"
    placement = dict(diagnostics[0].evidence.get("placement") or {})
    assert placement.get("fw_face_flush") is False
