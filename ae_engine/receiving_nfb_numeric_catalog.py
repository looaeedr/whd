# -*- coding: utf-8 -*-
"""Uncertified NFB V5 numeric catalog shared by all receiving panel roles.

Operator-selected identity is (brand, model), NOT an original DXF filename.
These local opening/screw coordinates are input data, not any panel's final
manufacturing or 3D placement. Existing DXF-authoritative workflows remain
unchanged until independently migrated and verified.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from math import isfinite
from pathlib import Path
import re

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RELATIVE_DIRECTORY = Path("基準檔") / "開孔" / "NFB" / "數值規格"
BRANDS = ("士林", "東元", "伍菱")
FILENAME = "NFB數值規格.csv"
HEADER = (
    "型號", "NFB寬_mm", "NFB高_mm", "NFB深_mm",
    "開孔尺寸_mm", "螺絲孔中心距_mm", "螺絲孔徑_mm",
    "螺絲孔群偏移X_mm", "螺絲孔群偏移Y_mm",
)
PAIR = re.compile(r"([0-9]+(?:\.[0-9]+)?)X([0-9]+(?:\.[0-9]+)?)")
NUMERIC_ONLY_UNVERIFIED = "NFB_V5_NUMERIC_SOURCE_UNVERIFIED"


@dataclass(frozen=True)
class NfbNumericSpec:
    brand: str
    model: str
    width_mm: float | None
    height_mm: float | None
    depth_mm: float | None
    opening_mm: tuple[float, float] | None
    screw_pitch_mm: tuple[float, float] | None
    screw_diameter_mm: float | None
    screw_offset_x_mm: float = 0.0
    screw_offset_y_mm: float = 0.0
    status: str = NUMERIC_ONLY_UNVERIFIED

    @property
    def missing_fields(self) -> tuple[str, ...]:
        return tuple(column for column, value in (
            ("NFB寬_mm", self.width_mm),
            ("NFB高_mm", self.height_mm),
            ("NFB深_mm", self.depth_mm),
            ("開孔尺寸_mm", self.opening_mm),
            ("螺絲孔中心距_mm", self.screw_pitch_mm),
            ("螺絲孔徑_mm", self.screw_diameter_mm),
        ) if value is None)

    @property
    def dimensionally_complete(self) -> bool:
        """All required numbers present; NOT a manufacturing approval."""
        return not self.missing_fields

    @property
    def opening_corners_xy_mm(self) -> tuple[tuple[float, float], ...] | None:
        """Local rectangular opening, centred on (0, 0), without any offset."""
        if self.opening_mm is None:
            return None
        w, h = self.opening_mm
        return ((-w / 2, -h / 2), (w / 2, -h / 2),
                (w / 2, h / 2), (-w / 2, h / 2))

    @property
    def screw_centers_xy_mm(self) -> tuple[tuple[float, float], ...] | None:
        """Four hole centres relative to the opening centre; unknown != empty."""
        if (self.opening_mm is None or self.screw_pitch_mm is None
                or self.screw_diameter_mm is None):
            return None
        x, y = self.screw_pitch_mm
        dx, dy = self.screw_offset_x_mm, self.screw_offset_y_mm
        return ((dx - x / 2, dy - y / 2), (dx + x / 2, dy - y / 2),
                (dx - x / 2, dy + y / 2), (dx + x / 2, dy + y / 2))


def brand_csv_path(brand: str) -> Path:
    if brand not in BRANDS:
        raise ValueError("不支援的 NFB 廠牌")
    return PROJECT_ROOT / RELATIVE_DIRECTORY / brand / FILENAME


def _number(raw: str, column: str, *, optional: bool = True,
            zero_allowed: bool = False) -> float | None:
    value = str(raw).strip()
    if not value:
        return None if optional else 0.0
    try:
        number = float(value)
    except ValueError as exc:
        raise ValueError(f"{column} 必須為數字") from exc
    if not isfinite(number) or (number < 0 if zero_allowed else number <= 0):
        raise ValueError(f"{column} 數值無效")
    return number


def _pair(raw: str, column: str) -> tuple[float, float] | None:
    text = str(raw).strip()
    if not text:
        return None
    match = PAIR.fullmatch(text)
    if match is None:
        raise ValueError(f"{column} 必須使用正數寬X高，例如 25X111")
    values = float(match.group(1)), float(match.group(2))
    if any(not isfinite(v) or v <= 0 for v in values):
        raise ValueError(f"{column} 必須是兩個有限正數")
    return values


def _offset(raw: str, column: str) -> float:
    if not str(raw).strip():
        return 0.0
    try:
        value = float(str(raw).strip())
    except ValueError as exc:
        raise ValueError(f"{column} 必須為數字") from exc
    if not isfinite(value):
        raise ValueError(f"{column} 不得為無限值")
    return value


def read_numeric_specs(brand: str, *, path: str | Path | None = None
                       ) -> tuple[NfbNumericSpec, ...]:
    """Read the exact brand CSV fresh each time; missing physical data stays None.

    Reject malformed schema, duplicate models and malformed supplied values.
    Do not infer any geometry from model names or non-V5 DXF sources.
    """
    source = Path(path) if path is not None else brand_csv_path(brand)
    if brand not in BRANDS:
        raise ValueError("不支援的 NFB 廠牌")
    with source.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != HEADER:
            raise ValueError("NFB V5 CSV 欄位與順序不符")
        seen: set[str] = set()
        results: list[NfbNumericSpec] = []
        for line, row in enumerate(reader, start=2):
            if None in row or any(value is None for value in row.values()):
                raise ValueError(f"NFB V5 第 {line} 行欄位數不符")
            model = row["型號"].strip()
            if not model or any(char in model for char in ("/", "\\", "\x00")):
                raise ValueError(f"NFB V5 第 {line} 行型號不合法")
            identity = model.casefold()
            if identity in seen:
                raise ValueError(f"NFB V5 第 {line} 行型號重複：{model}")
            seen.add(identity)
            try:
                spec = NfbNumericSpec(
                    brand=brand,
                    model=model,
                    width_mm=_number(row["NFB寬_mm"], "NFB寬_mm"),
                    height_mm=_number(row["NFB高_mm"], "NFB高_mm"),
                    depth_mm=_number(row["NFB深_mm"], "NFB深_mm"),
                    opening_mm=_pair(row["開孔尺寸_mm"], "開孔尺寸_mm"),
                    screw_pitch_mm=_pair(row["螺絲孔中心距_mm"], "螺絲孔中心距_mm"),
                    screw_diameter_mm=_number(row["螺絲孔徑_mm"], "螺絲孔徑_mm"),
                    screw_offset_x_mm=_offset(row["螺絲孔群偏移X_mm"], "螺絲孔群偏移X_mm"),
                    screw_offset_y_mm=_offset(row["螺絲孔群偏移Y_mm"], "螺絲孔群偏移Y_mm"),
                )
            except ValueError as exc:
                raise ValueError(f"NFB V5 {brand}/{model} 第 {line} 行：{exc}") from exc
            results.append(spec)
    return tuple(results)


def model_choices(brand: str, *, path: str | Path | None = None) -> tuple[str, ...]:
    """The V5 GUI selection source; values are readable model names."""
    if brand not in BRANDS:
        return ()
    return tuple(spec.model for spec in read_numeric_specs(brand, path=path))


def model_spec(brand: str, model: str, *, path: str | Path | None = None
               ) -> NfbNumericSpec | None:
    """Look up brand+model; unknown model returns None, never a sibling default."""
    if brand not in BRANDS or not isinstance(model, str):
        return None
    return next((spec for spec in read_numeric_specs(brand, path=path)
                 if spec.model == model), None)
