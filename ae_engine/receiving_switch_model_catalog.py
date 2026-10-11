# -*- coding: utf-8 -*-
"""Runtime authority for Receiving inner-door NFB model choices.

Only the operator-editable repository CSV supplies model filenames. This module
does not resolve NFB geometry or manufacture a DXF from an unverified mapping.
"""
from __future__ import annotations

import csv
from pathlib import Path

INDEX_PATH = Path(__file__).resolve().parents[1] / "開關索引.csv"
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
