# -*- coding: utf-8 -*-
"""Standalone NFB PAD preview adapter; reuse the WHD generator and V5 source.

This module creates *draft* data, never a manufacturing-certified part.
No cabinet, GUI, persisted NFB editor or fabricated model dimensions required.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json

from .receiving_nfb_numeric_catalog import BRANDS, model_spec
from .receiving_nfb_pad_generator import (
    PadPattern, PadToolingRule, generate_nfb_pad_patterns, read_pad_tooling_rule,
)


@dataclass(frozen=True)
class PadSelection:
    tier: int
    brand: str
    model: str


@dataclass(frozen=True)
class PadJob:
    tier: int
    selected_index: int
    pattern: PadPattern


@dataclass(frozen=True)
class PadPreview:
    selections: tuple[PadSelection, ...]
    jobs: tuple[PadJob, ...]
    plate_thickness_mm: float
    tooling_revision: str


def build_pad_preview(
    selections, *, plate_thickness_mm: float,
    tooling: PadToolingRule | None = None,
) -> PadPreview:
    """Derive every tier independently from actual per-brand numeric CSV V5.

    A user may select models for several tiers without a receiving-cabinet
    document. Zero generated pads is valid when depths match inside each tier.
    Physical placement and certification remain separate concerns.
    """
    items = tuple(selections)
    if not items:
        raise ValueError("請至少選擇一顆 NFB")
    if len(items) > 200:
        raise ValueError("一次最多預覽 200 顆 NFB")
    groups: dict[int, list[tuple[int, object]]] = {}
    for index, item in enumerate(items):
        if not isinstance(item, PadSelection):
            raise ValueError("NFB 選擇資料格式不正確")
        if type(item.tier) is not int or not 1 <= item.tier <= 32:
            raise ValueError("實體層數必須為 1～32 的整數")
        if item.brand not in BRANDS or not isinstance(item.model, str):
            raise ValueError("NFB CSV V5 廠牌或型號不合法")
        spec = model_spec(item.brand, item.model)
        if spec is None:
            raise ValueError(f"找不到 CSV V5 型號：{item.brand}/{item.model}")
        if not spec.dimensionally_complete:
            raise ValueError(f"CSV V5 尺寸／螺絲孔不完整：{item.brand}/{item.model}")
        groups.setdefault(item.tier, []).append((index, spec))
    rule = tooling if tooling is not None else read_pad_tooling_rule()
    result: list[PadJob] = []
    for tier, rows in sorted(groups.items()):
        patterns = generate_nfb_pad_patterns(
            [spec for _, spec in rows],
            plate_thickness_mm=plate_thickness_mm, tooling=rule,
        )
        for pattern in patterns:
            result.append(PadJob(
                tier=tier, selected_index=rows[pattern.switch_index][0],
                pattern=pattern,
            ))
    return PadPreview(
        selections=items, jobs=tuple(result),
        plate_thickness_mm=float(plate_thickness_mm),
        tooling_revision=rule.revision,
    )


def export_draft_pad_dxf(preview: PadPreview, folder: str | Path) -> tuple[Path, ...]:
    """Export explicitly NON-manufacturing drawings to a NEW output folder.

    This function cannot issue PART_ONLY CHECK/Q, base mating cuts, 3D contact
    evidence or certified NC files. Do not rename DRAFT layers to CUTTING/BEND.
    """
    if not preview.jobs:
        raise ValueError("沒有需要輸出的墊高片")
    import ezdxf

    destination = Path(folder)
    if destination.exists():
        raise FileExistsError(f"草稿資料夾已存在，禁止覆寫：{destination}")
    # Construct all entities before creating an output directory.
    drawings = []
    for job in preview.jobs:
        pad = job.pattern
        document = ezdxf.new("R2010")
        document.header["$INSUNITS"] = 4  # millimetres
        for name, color in (
            ("DRAFT_OUTLINE", 1), ("DRAFT_BEND", 3),
            ("DRAFT_SCREWS", 5), ("DRAFT_WARNING", 2),
        ):
            document.layers.new(name, dxfattribs={"color": color})
        space = document.modelspace()
        space.add_lwpolyline(
            pad.unfolded_outline_xy_mm, close=True,
            dxfattribs={"layer": "DRAFT_OUTLINE"},
        )
        for x in pad.bend_stations_x_mm:
            space.add_line(
                (x, 0), (x, pad.formed_height_mm),
                dxfattribs={"layer": "DRAFT_BEND"},
            )
        for x, y in pad.pad_unfolded_screw_centres_xy_mm:
            space.add_circle(
                (x, y), pad.screw_diameter_mm / 2,
                dxfattribs={"layer": "DRAFT_SCREWS"},
            )
        space.add_text(
            "DRAFT ONLY - NOT FOR MANUFACTURING",
            dxfattribs={
                "height": 5.0, "insert": (0, -15),
                "layer": "DRAFT_WARNING",
            },
        )
        filename = f"NFB_PAD_DRAFT_T{job.tier}_N{job.selected_index + 1}.dxf"
        drawings.append((filename, document))
    manifest = {
        "schema": "WHD_STANDALONE_NFB_PAD_DRAFT_V1",
        "manufacturing_ready": False,
        "manufacturing_release": "NOT_APPROVED",
        "note": "2D preview only. No base/contact/NC certification.",
        "tooling_revision": preview.tooling_revision,
        "plate_thickness_mm": preview.plate_thickness_mm,
        "pads": [{
            "file": name,
            "tier": job.tier,
            "selected_index": job.selected_index,
            "brand": job.pattern.brand,
            "model": job.pattern.model,
            "reference_depth_mm": job.pattern.reference_depth_mm,
            "switch_depth_mm": job.pattern.switch_depth_mm,
            "rise_mm": job.pattern.rise_mm,
            "blank_width_mm": job.pattern.blank_width_mm,
            "manufacturing_ready": False,
        } for job, (name, _) in zip(preview.jobs, drawings)],
    }
    destination.mkdir(parents=True, exist_ok=False)
    paths = []
    for name, document in drawings:
        path = destination / name
        document.saveas(str(path))
        paths.append(path)
    receipt = destination / "DRAFT_NOT_FOR_MANUFACTURING.json"
    receipt.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return tuple(paths)
