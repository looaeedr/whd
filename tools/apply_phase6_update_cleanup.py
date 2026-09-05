from __future__ import annotations

import json
from pathlib import Path
import shutil


def _safe_relative_path(raw: str) -> Path:
    value = str(raw or "").strip().replace("\\", "/")
    path = Path(value)
    if not value or path.is_absolute() or ".." in path.parts:
        raise ValueError(f"unsafe cleanup path: {raw!r}")
    return path


def apply_cleanup_paths(project_root: Path, cleanup_paths) -> tuple[str, ...]:
    root = Path(project_root).resolve()
    removed: list[str] = []
    for raw in cleanup_paths:
        rel = _safe_relative_path(raw)
        target = (root / rel).resolve()
        try:
            target.relative_to(root)
        except ValueError as exc:
            raise ValueError(f"unsafe cleanup path: {raw!r}") from exc
        if target.is_dir():
            shutil.rmtree(target)
            removed.append(rel.as_posix())
        elif target.exists():
            target.unlink()
            removed.append(rel.as_posix())
    return tuple(removed)


def apply_manifest_cleanup(project_root: Path | None = None) -> tuple[str, ...]:
    root = Path(project_root or Path(__file__).resolve().parents[1]).resolve()
    manifest = root / "release_required_artifacts.json"
    data = json.loads(manifest.read_text(encoding="utf-8"))
    return apply_cleanup_paths(root, data.get("update_cleanup_paths", ()))


def main() -> int:
    removed = apply_manifest_cleanup()
    if removed:
        print("已移除舊路徑：" + ", ".join(removed))
    else:
        print("沒有需要移除的舊路徑。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
