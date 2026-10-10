"""Bounded DXF export sink for canonical manufacturing output."""
from __future__ import annotations

import os
from pathlib import Path
import re
import tempfile
import shutil


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


def safe_dxf_instance_namespace(instance_namespace: str) -> str:
    value = str(instance_namespace or '').strip()
    if not value:
        raise ValueError('manufacturing instance namespace is empty')
    return safe_dxf_part_stem(value)


def receiving_instance_namespace(*, set_id: str, bay_id: str) -> str:
    """Return stable Set/Bay inventory namespace without engraving it into geometry."""
    return f'{safe_dxf_part_stem(set_id)}__{safe_dxf_part_stem(bay_id)}'


def resolved_physical_dxf_filename(
    part_id: str,
    *,
    box_body_physical_piece_roles,
    instance_namespace: str | None = None,
) -> str:
    stem = resolved_physical_dxf_stem(
        part_id, box_body_physical_piece_roles=box_body_physical_piece_roles
    )
    if instance_namespace is not None:
        stem = f'{safe_dxf_instance_namespace(instance_namespace)}__{stem}'
    return f'{stem}.dxf'


def _atomic_commit_staged_dxfs(
    staged: dict[str, Path],
    root: Path,
    *,
    overwrite: bool,
) -> dict[str, str]:
    """Commit a fully serialized DXF set with rollback on commit failure."""
    root.mkdir(parents=True, exist_ok=True)
    destinations = {key: root / path.name for key, path in staged.items()}
    names = [path.name for path in destinations.values()]
    if len(names) != len(set(names)):
        raise ValueError('duplicate DXF filename in requested manufacturing batch')
    if not overwrite:
        existing = [str(path) for path in destinations.values() if path.exists()]
        if existing:
            raise FileExistsError(existing[0])

    backup_dir = Path(tempfile.mkdtemp(prefix='.whd-dxf-backup-', dir=str(root)))
    moved: list[Path] = []
    backups: dict[Path, Path] = {}
    try:
        for destination in destinations.values():
            if destination.exists():
                backup = backup_dir / destination.name
                os.replace(destination, backup)
                backups[destination] = backup
        for key, stage_path in staged.items():
            destination = destinations[key]
            os.replace(stage_path, destination)
            moved.append(destination)
        return {key: str(destinations[key]) for key in staged}
    except Exception:
        for destination in reversed(moved):
            destination.unlink(missing_ok=True)
        for destination, backup in backups.items():
            if backup.exists():
                os.replace(backup, destination)
        raise
    finally:
        shutil.rmtree(backup_dir, ignore_errors=True)


def _save_resolved_rows_atomic(
    rows,
    output_dir,
    *,
    save_part_render_data_dxf,
    overwrite: bool,
) -> dict[str, str]:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    stage_dir = Path(tempfile.mkdtemp(prefix='.whd-dxf-stage-', dir=str(root)))
    staged: dict[str, Path] = {}
    try:
        filenames: set[str] = set()
        for output_key, filename, render_data in rows:
            if filename in filenames:
                raise ValueError(f'duplicate DXF filename in requested manufacturing batch: {filename}')
            filenames.add(filename)
            stage_path = stage_dir / filename
            save_part_render_data_dxf(render_data, stage_path, overwrite=True)
            staged[str(output_key)] = stage_path
        return _atomic_commit_staged_dxfs(staged, root, overwrite=overwrite)
    finally:
        shutil.rmtree(stage_dir, ignore_errors=True)


def save_resolved_manufacturing_geometry_dxf(
    resolved_geometry,
    output_dir,
    *,
    save_part_render_data_dxf,
    box_body_physical_piece_roles,
    overwrite: bool = False,
    instance_namespace: str | None = None,
) -> dict[str, str]:
    rows = []
    for part_id, render_data in resolved_physical_render_parts(resolved_geometry):
        filename = resolved_physical_dxf_filename(
            part_id,
            box_body_physical_piece_roles=box_body_physical_piece_roles,
            instance_namespace=instance_namespace,
        )
        rows.append((part_id, filename, render_data))
    return _save_resolved_rows_atomic(
        rows,
        output_dir,
        save_part_render_data_dxf=save_part_render_data_dxf,
        overwrite=overwrite,
    )


def save_resolved_manufacturing_geometry_batch_dxf(
    instances,
    output_dir,
    *,
    save_part_render_data_dxf,
    box_body_physical_piece_roles,
    overwrite: bool = False,
) -> dict[str, str]:
    """Atomically export multiple stable manufacturing instances into one inventory."""
    rows = []
    seen_namespaces: set[str] = set()
    for instance_namespace, resolved_geometry in tuple(instances or ()):
        namespace = safe_dxf_instance_namespace(instance_namespace)
        if namespace in seen_namespaces:
            raise ValueError(f'duplicate manufacturing instance namespace: {namespace}')
        seen_namespaces.add(namespace)
        for part_id, render_data in resolved_physical_render_parts(resolved_geometry):
            filename = resolved_physical_dxf_filename(
                part_id,
                box_body_physical_piece_roles=box_body_physical_piece_roles,
                instance_namespace=namespace,
            )
            rows.append((f'{namespace}:{part_id}', filename, render_data))
    return _save_resolved_rows_atomic(
        rows,
        output_dir,
        save_part_render_data_dxf=save_part_render_data_dxf,
        overwrite=overwrite,
    )


def resolved_manufacturing_nc_capability() -> dict[str, object]:
    return {
        'available': False,
        'reason': 'production NC sink is not implemented at the ResolvedManufacturingGeometry boundary',
        'canonical_input': 'ResolvedManufacturingGeometry',
    }



def save_quantity_manufacturing_groups_dxf(
    groups, output_dir, *, save_part_render_data_dxf, verify_part_dxf, overwrite=False,
    render_data_transform=None,
):
    """Serialize one sheet per validated group through the existing atomic sink."""
    rows = []
    keys = set()
    filenames = set()
    for group in tuple(groups):
        key = str(group.key)
        if not re.fullmatch(r"[0-9a-f]{64}", key) or key in keys:
            raise ValueError("invalid/duplicate manufacturing group key")
        keys.add(key)
        filename = group.filename
        if filename != f"part_{key}.dxf" or filename in filenames:
            raise ValueError("invalid/duplicate manufacturing group filename")
        filenames.add(filename)
        if isinstance(group.quantity, bool) or not isinstance(group.quantity, int) or group.quantity < 1:
            raise ValueError("manufacturing group quantity must be positive")
        render = group.render_data
        if render_data_transform is not None:
            render = render_data_transform(group)
        rows.append((key, filename, render))
    if not rows:
        raise ValueError("at least one manufacturing group is required")
    def save_verified(render, path, *, overwrite):
        saved = save_part_render_data_dxf(render, path, overwrite=overwrite)
        result = verify_part_dxf(render, saved)
        if not result.ok:
            raise ValueError(f"staged manufacturing DXF verification failed: {result.issues}")
        return saved

    return _save_resolved_rows_atomic(
        rows, output_dir, save_part_render_data_dxf=save_verified,
        overwrite=overwrite,
    )
