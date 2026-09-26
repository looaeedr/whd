"""Bounded DXF export sink for canonical manufacturing output."""
from __future__ import annotations

import os
from pathlib import Path
import re
import tempfile


def save_part_render_data_dxf(
    scene,
    output_path,
    *,
    serializer,
    overwrite: bool = False,
) -> str:
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and not overwrite:
        raise FileExistsError(str(destination))

    safe_stem = re.sub(r'[<>:"/\\|?*]', '_', destination.stem)
    fd, temp_name = tempfile.mkstemp(
        prefix=f'.{safe_stem}.tmp-',
        suffix=destination.suffix or '.dxf',
        dir=str(destination.parent),
    )
    os.close(fd)
    temp_path = Path(temp_name)
    try:
        serializer(str(temp_path), scene)
        os.replace(temp_path, destination)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise
    return str(destination)


def safe_dxf_part_stem(part_id: str) -> str:
    value = str(part_id or '').strip()
    if not value:
        raise ValueError('physical part id is empty')
    return re.sub(r'[<>:"/\\\\|?*]', '_', value)


def resolved_physical_dxf_stem(part_id: str, *, box_body_physical_piece_roles) -> str:
    value = str(part_id or '').strip()
    root, sep, role = value.partition(':')
    if (
        sep
        and root == 'box_body'
        and ':' not in role
        and role in box_body_physical_piece_roles
    ):
        return f'box_body__{safe_dxf_part_stem(role)}'
    return safe_dxf_part_stem(value)


def resolved_physical_render_parts(resolved_geometry):
    rows = []
    for part in tuple(getattr(resolved_geometry, 'parts', ()) or ()):
        key = str(getattr(part, 'part_key', '') or '').strip()
        if not key:
            raise ValueError('resolved manufacturing part missing part_key')
        render_data = getattr(part, 'render_data', None)
        if render_data is None:
            raise ValueError(f'resolved manufacturing part missing render_data: {key}')
        pieces = tuple(getattr(render_data, 'pieces', ()) or ())
        if pieces:
            for index, piece in enumerate(pieces, start=1):
                piece_render = getattr(piece, 'render_data', None)
                if piece_render is None:
                    raise ValueError(f'resolved piece missing render_data: {key}#{index}')
                piece_key = str(
                    getattr(piece, 'key', '')
                    or getattr(piece, 'piece_key', '')
                    or f'piece{index}'
                ).strip()
                rows.append((f'{key}:{piece_key}', piece_render))
        else:
            rows.append((key, render_data))
    return tuple(rows)


def resolved_physical_dxf_filename(part_id: str, *, box_body_physical_piece_roles) -> str:
    stem = resolved_physical_dxf_stem(
        part_id, box_body_physical_piece_roles=box_body_physical_piece_roles
    )
    return f'{stem}.dxf'


def save_resolved_manufacturing_geometry_dxf(
    resolved_geometry,
    output_dir,
    *,
    save_part_render_data_dxf,
    box_body_physical_piece_roles,
    overwrite: bool = False,
) -> dict[str, str]:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    outputs: dict[str, str] = {}
    for part_id, render_data in resolved_physical_render_parts(resolved_geometry):
        path = root / resolved_physical_dxf_filename(
            part_id, box_body_physical_piece_roles=box_body_physical_piece_roles
        )
        outputs[part_id] = save_part_render_data_dxf(
            render_data,
            path,
            overwrite=overwrite,
        )
    return outputs


def resolved_manufacturing_nc_capability() -> dict[str, object]:
    return {
        'available': False,
        'reason': 'production NC sink is not implemented at the ResolvedManufacturingGeometry boundary',
        'canonical_input': 'ResolvedManufacturingGeometry',
    }
