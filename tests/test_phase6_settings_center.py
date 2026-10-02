import configparser
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import pytest

from phase6_settings_center import (
    GLOBAL_CONTEXT,
    load_settings_from_ae,
    save_defaults_to_ini,
    settings_for_context,
)


@dataclass(frozen=True)
class Relief:
    top_secondary_x_factor: float = 0.5
    top_secondary_depth_factor: float = 2.0
    bottom_x_factor: float = 0.5
    bottom_y_factor: float = 0.5


def _fake_ae(tmp_path: Path):
    ini = tmp_path / "config.ini"
    ini.write_text(
        "[DEFAULT_SIZES]\nW = 400\nH = 600\nD = 250\nT = 2\nFW = 25\n\n"
        "[BASE_PLATE]\nshrink = 55\nbend = 15\n\n"
        "[DOOR]\ndoor_gap_w = 3.5\ndoor_gap_h = 3.5\ndoor_fold_left = 19\ndoor_fold_right = 15\ndoor_fold_top = 15\ndoor_fold_bottom = 15\n\n"
        "[BOX_BODY_Z]\nzl1 = 15\nzl2 = 20\nzr1 = 15\nzr2 = 20\nz_comp = 3\n\n"
        "[END_CAP_Y]\nyl1 = 15\nyr1 = 15\nytop1 = 16\nybottom1 = 15\n\n"
        "[OUTPUT]\ndraw_stock = false\n\n"
        "[CUSTOM_KEEP]\nfoo = bar\n",
        encoding="utf-8",
    )
    cfg = configparser.ConfigParser(); cfg.read(ini, encoding="utf-8")
    return SimpleNamespace(
        INI_PATH=str(ini), config=cfg,
        W=400.0, H=600.0, D=250.0, T=2.0, FW=25.0, DRAW_STOCK=False,
        zl1_def=15.0, zl2_def=20.0, zr1_def=15.0, zr2_def=20.0, z_comp_def=3.0,
        yl1_def=15.0, yr1_def=15.0, ytop1_def=16.0, ybottom1_def=15.0,
        door_gap_w_def=3.5, door_gap_h_def=3.5,
        door_fold_left_def=19.0, door_fold_right_def=15.0,
        door_fold_top_def=15.0, door_fold_bottom_def=15.0,
        base_plate_shrink_def=55.0, base_plate_bend_def=15.0,
        indicator_box_fold_def=49.0,
        hang_hole_r=3.2, hang_hole_x=35.5, hang_hole_y_up=6.0,
        sq_x_left=3.0, sq_width=4.0, sq_y_bottom=18.0, sq_height=4.0,
        bottom_hole_r=2.5, bottom_hole_y=5.0,
        notch_bottom_gap=0.5, notch_sub_x_half=0.5, notch_sub_y_factor=2.0,
        RELIEF_CONFIG=Relief(),
    )


def test_contexts_classify_global_and_part_specific_values():
    global_keys = {spec.key for spec in settings_for_context(GLOBAL_CONTEXT)}
    assert {"w", "h", "d", "t", "fw", "draw_stock"} <= global_keys
    assert "zl1" not in global_keys
    assert "door_fold_l" not in global_keys

    box_keys = {spec.key for spec in settings_for_context("box_body")}
    assert {"zl1", "zl2", "zr1", "zr2", "z_comp"} <= box_keys

    tail_keys = {spec.key for spec in settings_for_context("tail")}
    assert {"yl1", "yr1", "ytop1", "ybottom1", "hang_hole_r", "bottom_hole_r"} <= tail_keys


def test_load_uses_legacy_base_shrink_for_all_four_sides_and_small_door_fallback(tmp_path):
    ae = _fake_ae(tmp_path)
    values = load_settings_from_ae(ae)
    assert values["base_plate_shrink_top"] == 55.0
    assert values["base_plate_shrink_bottom"] == 55.0
    assert values["base_plate_shrink_left"] == 55.0
    assert values["base_plate_shrink_right"] == 55.0
    assert values["indicator_door_fold"] == 19.0


def test_save_part_defaults_preserves_unknown_ini_content_and_writes_specific_shrink_keys(tmp_path):
    ae = _fake_ae(tmp_path)
    values = load_settings_from_ae(ae)
    values.update({
        "base_plate_shrink_top": 50.0,
        "base_plate_shrink_bottom": 51.0,
        "base_plate_shrink_left": 52.0,
        "base_plate_shrink_right": 53.0,
        "base_plate_bend": 18.0,
    })

    save_defaults_to_ini(ae, values, context="base_plate")

    cfg = configparser.ConfigParser(); cfg.read(ae.INI_PATH, encoding="utf-8")
    assert cfg["CUSTOM_KEEP"]["foo"] == "bar"
    assert cfg.getfloat("BASE_PLATE", "shrink_top") == 50.0
    assert cfg.getfloat("BASE_PLATE", "shrink_bottom") == 51.0
    assert cfg.getfloat("BASE_PLATE", "shrink_left") == 52.0
    assert cfg.getfloat("BASE_PLATE", "shrink_right") == 53.0
    assert cfg.getfloat("BASE_PLATE", "bend") == 18.0


def test_save_global_defaults_updates_runtime_ae_and_relief_without_touching_part_values(tmp_path):
    ae = _fake_ae(tmp_path)
    values = load_settings_from_ae(ae)
    values.update({
        "w": 888.0,
        "t": 2.3,
        "draw_stock": True,
        "relief_top_secondary_x_factor": 0.75,
        "zl1": 99.0,
    })

    save_defaults_to_ini(ae, values, context=GLOBAL_CONTEXT)

    assert ae.W == 888.0
    assert ae.T == 2.3
    assert ae.DRAW_STOCK is True
    assert ae.RELIEF_CONFIG.top_secondary_x_factor == pytest.approx(0.75)
    assert ae.zl1_def == 15.0
    cfg = configparser.ConfigParser(); cfg.read(ae.INI_PATH, encoding="utf-8")
    assert cfg.getfloat("DEFAULT_SIZES", "W") == 888.0
    assert cfg.getfloat("RELIEF", "top_secondary_x_factor") == 0.75
    assert cfg.getfloat("BOX_BODY_Z", "zl1") == 15.0


def test_corner_defaults_round_trip_per_part_without_touching_other_ini(tmp_path):
    from phase6_settings_center import load_corner_defaults_from_ini, save_corner_defaults_to_ini
    ae = _fake_ae(tmp_path)
    state = {
        "door": {
            "top_left": {"type_id": "C04", "rotation_quadrants": 0},
            "top_right": {"type_id": "C02", "rotation_quadrants": 1},
            "bottom_left": {"type_id": "C01", "rotation_quadrants": 0},
            "bottom_right": {"type_id": "C03", "rotation_quadrants": 0},
        }
    }
    pairs = {"door": {"top": False, "bottom": True}}

    save_corner_defaults_to_ini(ae, state, pairs, context="door")
    loaded_state, loaded_pairs = load_corner_defaults_from_ini(ae)

    assert loaded_pairs["door"] == {"top": False, "bottom": True}
    assert loaded_state["door"]["top_left"] == {"type_id": "C04", "rotation_quadrants": 0}
    assert loaded_state["door"]["top_right"] == {"type_id": "C02", "rotation_quadrants": 1}
    cfg = configparser.ConfigParser(); cfg.read(ae.INI_PATH, encoding="utf-8")
    assert cfg["CUSTOM_KEEP"]["foo"] == "bar"
    assert cfg["CORNER_DOOR"]["top_right"] == "C02"
    assert cfg.getint("CORNER_DOOR", "top_right_rotation") == 1


@dataclass(frozen=True)
class FixedHolePolicy:
    hanging_hole_radius: float = 3.2
    hanging_hole_y_from_top_bend: float = 6.0
    square_hole_origin: object = (3.0, 18.0)
    square_hole_size: object = (4.0, 4.0)
    tail_bottom_hole_radius: float = 2.5
    tail_bottom_hole_y: float = 5.0
    hanging_hole_offset_from_primary: float = 10.5


def test_live_fixed_hole_settings_rebuild_vault_feature_policy(tmp_path):
    from phase6_settings_center import apply_settings_to_ae
    ae = _fake_ae(tmp_path)
    ae.VAULT_ENDCAP_FEATURE_POLICY = FixedHolePolicy()
    apply_settings_to_ae(ae, {
        "hang_hole_r": 4.1,
        "hang_hole_y_up": 8.0,
        "sq_x_left": 5.0,
        "sq_y_bottom": 21.0,
        "sq_width": 6.0,
        "sq_height": 7.0,
        "bottom_hole_r": 3.0,
        "bottom_hole_y": 9.0,
    })
    policy = ae.VAULT_ENDCAP_FEATURE_POLICY
    assert policy.hanging_hole_radius == 4.1
    assert policy.hanging_hole_y_from_top_bend == 8.0
    assert tuple(policy.square_hole_origin) == (5.0, 21.0)
    assert tuple(policy.square_hole_size) == (6.0, 7.0)
    assert policy.tail_bottom_hole_radius == 3.0
    assert policy.tail_bottom_hole_y == 9.0
