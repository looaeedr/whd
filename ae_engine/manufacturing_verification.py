"""Bounded manufacturing DXF verification owner."""
from __future__ import annotations

from pathlib import Path


def verify_saved_part_render_data_dxf(
    render_data,
    output_path,
    *,
    coordinate_tolerance: float = 1e-6,
    area_tolerance: float = 1e-6,
):
    from .dxf_acceptance import verify_saved_part_render_data_dxf as _verify

    return _verify(
        render_data,
        output_path,
        coordinate_tolerance=coordinate_tolerance,
        area_tolerance=area_tolerance,
    )


def verify_saved_resolved_manufacturing_geometry_dxf(
    resolved_geometry,
    output_dir,
    *,
    resolved_physical_render_parts,
    resolved_physical_dxf_filename,
    verify_part_dxf,
    coordinate_tolerance: float = 1e-6,
    area_tolerance: float = 1e-6,
):
    from .dxf_acceptance import (
        ResolvedDxfAcceptanceIssue,
        ResolvedDxfAcceptanceResult,
    )

    root = Path(output_dir)
    expected_rows = resolved_physical_render_parts(resolved_geometry)
    expected_files = {
        resolved_physical_dxf_filename(part_id): part_id
        for part_id, _render_data in expected_rows
    }
    actual_files = {path.name for path in root.glob('*.dxf') if path.is_file()}
    issues = []
    part_results = {}

    missing = sorted(set(expected_files) - actual_files)
    extra = sorted(actual_files - set(expected_files))
    for filename in missing:
        issues.append(ResolvedDxfAcceptanceIssue(
            expected_files[filename],
            'MISSING_PART',
            f'expected physical-part DXF is missing: {filename}',
            filename,
            None,
        ))
    for filename in extra:
        issues.append(ResolvedDxfAcceptanceIssue(
            filename[:-4] if filename.lower().endswith('.dxf') else filename,
            'EXTRA_PART',
            f'stale/extra DXF not present in current resolved physical-part state: {filename}',
            None,
            filename,
        ))

    for part_id, render_data in expected_rows:
        filename = resolved_physical_dxf_filename(part_id)
        path = root / filename
        if not path.is_file():
            continue
        result = verify_part_dxf(
            render_data,
            path,
            coordinate_tolerance=coordinate_tolerance,
            area_tolerance=area_tolerance,
        )
        part_results[part_id] = result
        for issue in result.issues:
            issues.append(ResolvedDxfAcceptanceIssue(
                part_id,
                issue.category,
                issue.detail,
                issue.expected,
                issue.actual,
            ))

    return ResolvedDxfAcceptanceResult(
        ok=not issues,
        issues=tuple(issues),
        part_results=part_results,
    )
