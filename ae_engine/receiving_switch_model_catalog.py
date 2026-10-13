# -*- coding: utf-8 -*-
"""Runtime authority for Receiving inner-door NFB model choices.

Only the operator-editable repository CSV supplies model filenames. This module
does not resolve NFB geometry or manufacture a DXF from an unverified mapping.
"""
from __future__ import annotations

import csv
from pathlib import Path

# A single relative source location under the checked-out WHD project.
# Resolve from this module, never the shell working directory or device drive.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
INDEX_RELATIVE_PATH = Path("基準檔") / "開孔" / "NFB" / "開關索引.csv"
INDEX_PATH = PROJECT_ROOT / INDEX_RELATIVE_PATH
HEADER = ("圖塊名稱", "士林", "深", "東元", "深", "伍菱", "深")
BRANDS = ("士林", "東元", "伍菱")
UNMAPPED = "無對應檔案"


def display_model(filename: str) -> str:
    """Hide only the final .dxf extension; retain filename as the identity."""
    value = str(filename).strip()
    if not value.lower().endswith(".dxf"):
        raise ValueError(f"開關檔名不是 DXF：{value!r}")
    return value[:-4]


def model_filenames(brand: str, *, path: str | Path | None = None) -> tuple[str, ...]:
    """Read fresh CSV at call time; preserve row order, deduplicate by filename."""
    if brand not in BRANDS:
        return ()  # No invented options for brands absent from this source.
    source = Path(path) if path is not None else INDEX_PATH
    with source.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = csv.reader(stream)
        columns = next(rows, None)
        if tuple(columns or ()) != HEADER:
            raise ValueError("開關索引.csv 欄位不符，應為圖塊名稱／各品牌與深度")
        index = columns.index(brand)
        seen: set[str] = set()
        filenames: list[str] = []
        for line_number, row in enumerate(rows, start=2):
            if len(row) != len(HEADER):
                raise ValueError(f"開關索引.csv 第 {line_number} 行欄位數錯誤")
            filename = row[index].strip()
            if not filename or filename == UNMAPPED:
                continue
            if (not filename.lower().endswith(".dxf")
                    or filename in (".dxf", ".DXF")
                    or "/" in filename or "\\" in filename):
                raise ValueError(
                    f"開關索引.csv 第 {line_number} 行檔名不合法：{filename!r}"
                )
            identity = filename.casefold()
            if identity not in seen:
                seen.add(identity)
                filenames.append(filename)
    return tuple(filenames)


def model_choices(brand: str, *, path: str | Path | None = None) -> tuple[str, ...]:
    """Names displayed to the user; never return .dxf to the UI."""
    return tuple(display_model(name) for name in model_filenames(brand, path=path))


def model_depth_mm(
    brand: str, filename: str, *, path: str | Path | None = None,
) -> float | None:
    """Read the *adjacent* 深 column for this exact brand + DXF filename.

    CSV is user-editable and read afresh on every request. No filename-suffix
    inference, cross-brand fallback, unapproved alias or hardcoded 400 models.
    Blank/missing values remain unknown; conflicting duplicate rows fail
    closed instead of making a physically incorrect PAD decision.
    """
    from math import isfinite

    if brand not in BRANDS:
        return None
    if not isinstance(filename, str) or not filename.strip():
        return None
    key = filename.strip().casefold()
    if "/" in key or "\\" in key or not key.endswith(".dxf"):
        return None
    source = Path(path) if path is not None else INDEX_PATH
    values: set[float | None] = set()
    with source.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = csv.reader(stream)
        columns = next(rows, None)
        if tuple(columns or ()) != HEADER:
            raise ValueError("開關索引.csv 欄位不符，應為圖塊名稱／各品牌與深度")
        idx = columns.index(brand)
        if idx + 1 >= len(columns) or columns[idx + 1] != "深":
            raise ValueError("開關索引.csv 廠牌深度欄位錯位")
        for number, row in enumerate(rows, start=2):
            if len(row) != len(HEADER):
                raise ValueError(f"開關索引.csv 第 {number} 行欄位數錯誤")
            if row[idx].strip().casefold() != key:
                continue
            raw = row[idx + 1].strip()
            if not raw:
                values.add(None)
                continue
            try:
                value = float(raw)
            except ValueError as exc:
                raise ValueError(f"開關索引.csv 第 {number} 行深度不是數字") from exc
            if not isfinite(value) or value <= 0:
                raise ValueError(f"開關索引.csv 第 {number} 行深度必須為正的有限數值")
            values.add(value)
    if len(values) > 1:
        raise ValueError(f"開關索引.csv {brand}/{filename} 重複深度不一致")
    return next(iter(values)) if values else None
