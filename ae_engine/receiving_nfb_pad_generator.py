# -*- coding: utf-8 -*-
"""Model-independent NFB PAD forming and mating-cut geometry (#1503).

All NFB dimensions come from per-brand NFB數值規格.csv. Tool geometry comes
from ONE editable project tooling rule, not model-specific branches. Generate
per physical tier: its deepest NFB owns the reference mounting face.

This produces dimensioned draft CUTTING outlines and BEND stations, not an
approved manufacturing PartRenderData or a certified folded 3D placement.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from pathlib import Path
import json

TOOLING_RELATIVE_PATH = Path("基準檔/開孔/NFB/墊高片共用加工規則.json")
Point2 = tuple[float, float]
Polygon2 = tuple[Point2, ...]


@dataclass(frozen=True)
class PadToolingRule:
    revision: str
    source_dxf_sha256: str
    tab_projection_mm: float
    tab_height_mm: float
    tab_end_inset_mm: float
    base_square_side_mm: float
    base_square_center_inset_x_mm: float

    def validate(self) -> None:
        values = (self.tab_projection_mm, self.tab_height_mm,
                  self.tab_end_inset_mm, self.base_square_side_mm,
                  self.base_square_center_inset_x_mm)
        if not self.revision or len(self.source_dxf_sha256) != 64:
            raise ValueError("PAD 共用加工規則來源身分不完整")
        if not all(isfinite(v) and v > 0 for v in values):
            raise ValueError("PAD 共用加工規則需要有限正數")


def read_pad_tooling_rule(path: str | Path | None = None) -> PadToolingRule:
    """Load at runtime. There are no brand/model-specific tooling defaults."""
    source = (Path(path) if path is not None else
              Path(__file__).resolve().parents[1] / TOOLING_RELATIVE_PATH)
    record = json.loads(source.read_text(encoding="utf-8"))
    if record.get("schema") != "RECEIVING_NFB_PAD_TOOLING_V1":
        raise ValueError("PAD 共用加工規則格式不正確")
    rule = PadToolingRule(**{name: record[name] for name in
        PadToolingRule.__dataclass_fields__})
    rule.validate()
    return rule


@dataclass(frozen=True)
class PadPattern:
    switch_index: int
    brand: str
    model: str
    formed_width_mm: float
    formed_height_mm: float
    plate_thickness_mm: float
    reference_depth_mm: float
    switch_depth_mm: float
    rise_mm: float
    side_leg_blank_mm: float
    centre_web_blank_mm: float
    blank_width_mm: float
    bend_stations_x_mm: tuple[float, float]
    formed_outline_xy_mm: Polygon2
    unfolded_outline_xy_mm: Polygon2
    pad_screw_centres_xy_mm: tuple[Point2, ...]
    pad_unfolded_screw_centres_xy_mm: tuple[Point2, ...]
    screw_diameter_mm: float
    base_square_holes_xy_mm: tuple[Polygon2, ...]
    base_screw_centres_xy_mm: tuple[Point2, ...]
    tooling_revision: str
    manufacturing_ready: bool = False


def _tongued_outline(width: float, height: float, rule: PadToolingRule,
                      *, min_x: float, min_y: float) -> Polygon2:
    """One parametric 4-tab perimeter for formed and unfolded flat views."""
    a, b = min_x, min_x + width
    l, r = a - rule.tab_projection_mm, b + rule.tab_projection_mm
    y0, y1 = min_y, min_y + height
    lo = y0 + rule.tab_end_inset_mm
    hi = y1 - rule.tab_end_inset_mm - rule.tab_height_mm
    t = rule.tab_height_mm
    if lo + t >= hi:
        raise ValueError("PAD 高度不足以容納上下兩組凸耳")
    return ((a,y0),(a,lo),(l,lo),(l,lo+t),(a,lo+t),
            (a,hi),(l,hi),(l,hi+t),(a,hi+t),(a,y1),
            (b,y1),(b,hi+t),(r,hi+t),(r,hi),(b,hi),
            (b,lo+t),(r,lo+t),(r,lo),(b,lo),(b,y0))


def _base_squares(width: float, height: float,
                  rule: PadToolingRule) -> tuple[Polygon2, ...]:
    cx = width/2 - rule.base_square_center_inset_x_mm
    cy = height/2 - rule.tab_end_inset_mm - rule.tab_height_mm/2
    s = rule.base_square_side_mm/2
    if cx <= s or cy <= s:
        raise ValueError("PAD 來源方孔超出有效裝配間距")
    return tuple(((x-s,y-s),(x+s,y-s),(x+s,y+s),(x-s,y+s))
                 for y in (-cy,cy) for x in (-cx,cx))


def _screws(spec) -> tuple[tuple[Point2, ...], float]:
    pitch = getattr(spec,"screw_pitch_mm",None)
    diameter = getattr(spec,"screw_diameter_mm",None)
    dx = getattr(spec,"screw_offset_x_mm",None)
    dy = getattr(spec,"screw_offset_y_mm",None)
    if (not isinstance(pitch,(tuple,list)) or len(pitch)!=2 or
            diameter is None or dx is None or dy is None):
        raise ValueError("PAD NFB CSV 缺少完整螺絲孔規格")
    px,py,d,ox,oy = map(float,(*pitch,diameter,dx,dy))
    if (not all(isfinite(v) for v in (px,py,d,ox,oy)) or
            min(px,py,d)<=0):
        raise ValueError("PAD NFB CSV 螺絲孔規格不合法")
    return (tuple((ox+x*px/2,oy+y*py/2)
                  for y in (-1,1) for x in (-1,1)),d)


def generate_nfb_pad_patterns(
    selected_nfb, *, plate_thickness_mm: float,
    tooling: PadToolingRule,
) -> tuple[PadPattern, ...]:
    """Generate zero or more PADs for ONE tier, independent of make/model.

    Caller supplies the selected numeric CSV specs in physical unit order.
    All equal-depth units require no PAD. Every shallower unit gets its own
    projected real mounting pattern; missing source measurements are errors.
    """
    tooling.validate()
    selected = tuple(selected_nfb)
    if not selected:
        return ()
    t = float(plate_thickness_mm)
    if not isfinite(t) or t <= 0:
        raise ValueError("PAD 板厚必須為有限正數")
    for spec in selected:
        if any(getattr(spec, name, None) is None for name in (
                "brand","model","width_mm","height_mm","depth_mm")):
            raise ValueError("PAD 所選 NFB 缺少 CSV 寬高深來源")
        if not all(isfinite(float(getattr(spec,n))) and float(getattr(spec,n))>0
                   for n in ("width_mm","height_mm","depth_mm")):
            raise ValueError("PAD 所選 NFB 寬高深不合法")
    deepest = max(float(s.depth_mm) for s in selected)
    results = []
    for index,spec in enumerate(selected):
        width,height,depth = map(float,(spec.width_mm,spec.height_mm,spec.depth_mm))
        rise = deepest - depth
        if rise <= 1e-8:
            continue
        a,b = rise-t,width-2*t
        if a <= 0 or b <= 0:
            raise ValueError("PAD 深度差或成型寬不足以產生 T 板雙側折彎")
        blank_width = 2*a+b
        squares = _base_squares(width,height,tooling)
        screws,diameter = _screws(spec)
        if any(abs(x)+diameter/2 >= b/2 or abs(y)+diameter/2 >= height/2
               for x,y in screws):
            raise ValueError("PAD NFB 螺絲孔超出真實中央折面")
        # A model's screw group may be offset; reject screw-square collisions.
        half = tooling.base_square_side_mm/2
        for hole in squares:
            square_x=(hole[0][0]+hole[2][0])/2
            square_y=(hole[0][1]+hole[2][1])/2
            for x,y in screws:
                dx=max(abs(x-square_x)-half,0.)
                dy=max(abs(y-square_y)-half,0.)
                if dx*dx+dy*dy <= (diameter/2)**2:
                    raise ValueError("PAD NFB 原螺絲孔與底板定位方孔重疊")
        results.append(PadPattern(
            switch_index=index,brand=str(spec.brand),model=str(spec.model),
            formed_width_mm=width,formed_height_mm=height,
            plate_thickness_mm=t,reference_depth_mm=deepest,
            switch_depth_mm=depth,rise_mm=rise,
            side_leg_blank_mm=a,centre_web_blank_mm=b,
            blank_width_mm=blank_width,
            bend_stations_x_mm=(a,a+b),
            formed_outline_xy_mm=_tongued_outline(width,height,tooling,
                min_x=-width/2,min_y=-height/2),
            unfolded_outline_xy_mm=_tongued_outline(blank_width,height,tooling,
                min_x=0,min_y=0),
            pad_screw_centres_xy_mm=screws,
            pad_unfolded_screw_centres_xy_mm=tuple(
                (blank_width/2+x,height/2+y) for x,y in screws),
            screw_diameter_mm=diameter,
            base_square_holes_xy_mm=squares,
            base_screw_centres_xy_mm=screws,
            tooling_revision=tooling.revision,
        ))
    return tuple(results)
