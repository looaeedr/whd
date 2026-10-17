# -*- coding: utf-8 -*-
"""V5 numeric hole pattern on an explicitly supplied, real panel-local UV datum.

This is a panel-neutral geometric *preview* only.  The consuming inner door,
middle plate, base plate or other part must first resolve its own physical
unfolded face origin and orientation; this module neither infers that datum
from an NFB model name nor emits a manufactured/certified CUTTING primitive.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from .receiving_nfb_numeric_catalog import model_spec

ROLES = frozenset(("inner-door", "middle-plate", "base-plate", "other"))
FEATURES = frozenset(("opening", "screws", "both"))
STATUS = "NFB_V5_PANEL_UV_GEOMETRY_UNVERIFIED"


def _xy(value, description):
    if (not isinstance(value, (tuple, list)) or len(value) != 2
            or any(type(v) not in (int, float) or not isfinite(float(v)) for v in value)):
        raise ValueError(f"{description} 必須是兩個有效座標")
    return float(value[0]), float(value[1])


@dataclass(frozen=True)
class NfbPanelDatum:
    """External canonical panel's candidate UV centre and two planar axes.

    No default axes: an inner door's flat UV is not the middle divider's UV.
    Axes must be a right-handed orthogonal unit basis (quarter-turn) so
    accidental mirroring or scaling never silently changes physical holes.
    """
    part_id: str
    role: str
    uv_centre_mm: tuple[float, float]
    uv_axis_x: tuple[int, int]
    uv_axis_y: tuple[int, int]

    def validate(self):
        if not isinstance(self.part_id, str) or not self.part_id.strip():
            raise ValueError("NFB 板件缺少實際 Part ID")
        if self.role not in ROLES:
            raise ValueError("NFB 未知板件用途")
        _xy(self.uv_centre_mm, "NFB 板件中心")
        x = _xy(self.uv_axis_x, "NFB 板件局部 X 軸")
        y = _xy(self.uv_axis_y, "NFB 板件局部 Y 軸")
        if (x not in ((1., 0.), (0., 1.), (-1., 0.), (0., -1.))
                or y not in ((1., 0.), (0., 1.), (-1., 0.), (0., -1.))
                or x[0]*y[0]+x[1]*y[1] != 0.0
                or x[0]*y[1]-x[1]*y[0] != 1.0):
            raise ValueError("NFB 板件座標必須為正向直角基底，禁止鏡射／縮放")
        return self

    def map_xy(self, xy: tuple[float, float]) -> tuple[float, float]:
        u,v=_xy(xy, "NFB 來源孔位")
        x,y=self.uv_centre_mm
        ax,ay=self.uv_axis_x
        bx,by=self.uv_axis_y
        return (float(x)+u*ax+v*bx, float(y)+u*ay+v*by)


@dataclass(frozen=True)
class NfbV5PanelPattern:
    brand: str
    model: str
    datum: NfbPanelDatum
    feature: str
    opening_uv_mm: tuple[tuple[float, float], ...] | None
    screw_centres_uv_mm: tuple[tuple[float, float], ...] | None
    screw_diameter_mm: float | None
    status: str = STATUS
    manufacturing_ready: bool = False


def project_nfb_v5_to_panel(
    brand: str, model: str, datum: NfbPanelDatum, *, feature: str,
) -> NfbV5PanelPattern:
    """Place requested local V5 contours on an explicitly given panel UV.

    The requested output is only a candidate. Calling code must independently
    prove physical part transform, face, clearance, 3D/collision and all
    manufacturing gates. Missing dimensions raise, not zero holes.
    """
    if not isinstance(datum, NfbPanelDatum):
        raise TypeError("NFB V5 必須有實際板件中心及座標")
    datum.validate()
    if feature not in FEATURES:
        raise ValueError("NFB 必須明確指定開孔、螺絲孔或兩者")
    spec=model_spec(brand, model)
    if spec is None or spec.opening_corners_xy_mm is None:
        raise ValueError("NFB V5 開孔尺寸缺失或型號不存在，不能定位")
    need_opening=feature in ("opening", "both")
    need_screws=feature in ("screws", "both")
    if need_screws and spec.screw_centers_xy_mm is None:
        raise ValueError("NFB V5 螺絲孔中心距／孔徑不足，不能定位")
    opening=(tuple(datum.map_xy(p) for p in spec.opening_corners_xy_mm)
             if need_opening else None)
    screws=(tuple(datum.map_xy(p) for p in spec.screw_centers_xy_mm)
            if need_screws else None)
    return NfbV5PanelPattern(
        brand=brand, model=model, datum=datum, feature=feature,
        opening_uv_mm=opening, screw_centres_uv_mm=screws,
        screw_diameter_mm=spec.screw_diameter_mm if need_screws else None,
    )
