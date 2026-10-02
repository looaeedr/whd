from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
from typing import Iterable
import zipfile

EXCLUDED_DIRS = {"__pycache__", ".pytest_cache"}
EXCLUDED_SUFFIXES = {".pyc"}


@dataclass(frozen=True)
class ReleasePolicy:
    update_baseline_mode: str
    mandatory_update_files: tuple[str, ...]
    mandatory_update_trees: tuple[str, ...] = ()
    forbidden_update_files: tuple[str, ...] = ("config.ini",)
    excluded_package_roots: tuple[str, ...] = (".git", ".scratch")
    excluded_update_roots: tuple[str, ...] = ("BACKUP",)
    update_cleanup_paths: tuple[str, ...] = ()


def _normalized(rel: str | Path) -> str:
    raw = Path(rel).as_posix()
    while raw.startswith("./"):
        raw = raw[2:]
    return raw


def _is_packaged_file(
    path: Path,
    root: Path,
    excluded_package_roots: Iterable[str] = (),
) -> bool:
    rel = path.relative_to(root)
    if rel.parts:
        first = rel.parts[0]
        if first in {_normalized(item).rstrip("/") for item in excluded_package_roots}:
            return False
    if any(part in EXCLUDED_DIRS for part in rel.parts):
        return False
    if path.suffix in EXCLUDED_SUFFIXES:
        return False
    return path.is_file()


def _is_under_excluded_update_root(rel: str, roots: Iterable[str]) -> bool:
    parts = Path(rel).parts
    if not parts:
        return False
    first = parts[0]
    for root in roots:
        root = _normalized(root).rstrip("/")
        if not root:
            continue
        if first == root or first.startswith(root + "_"):
            return True
    return False


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_release_policy(root: Path) -> ReleasePolicy:
    manifest = root / "release_required_artifacts.json"
    data = json.loads(manifest.read_text(encoding="utf-8"))
    if data.get("schema_version") != 2:
        raise ValueError("unsupported release_required_artifacts schema_version")
    files = data.get("mandatory_update_files")
    if not isinstance(files, list) or not all(isinstance(x, str) and x for x in files):
        raise ValueError("mandatory_update_files must be a non-empty string list")
    baseline_mode = data.get("update_baseline_mode")
    if baseline_mode != "explicit_runtime_archive":
        raise ValueError("update_baseline_mode must be 'explicit_runtime_archive'")
    trees = data.get("mandatory_update_trees", [])
    forbidden = data.get("forbidden_update_files", ["config.ini"])
    package_excluded = data.get("excluded_package_roots", [".git", ".scratch"])
    excluded = data.get("excluded_update_roots", ["BACKUP"])
    cleanup = data.get("update_cleanup_paths", [])
    for name, value in (("mandatory_update_trees", trees), ("forbidden_update_files", forbidden), ("excluded_package_roots", package_excluded), ("excluded_update_roots", excluded), ("update_cleanup_paths", cleanup)):
        if not isinstance(value, list) or not all(isinstance(x, str) and x for x in value):
            raise ValueError(f"{name} must be a string list")
    return ReleasePolicy(
        update_baseline_mode=baseline_mode,
        mandatory_update_files=tuple(_normalized(x) for x in files),
        mandatory_update_trees=tuple(_normalized(x) for x in trees),
        forbidden_update_files=tuple(_normalized(x) for x in forbidden),
        excluded_package_roots=tuple(_normalized(x) for x in package_excluded),
        excluded_update_roots=tuple(_normalized(x) for x in excluded),
        update_cleanup_paths=tuple(_normalized(x) for x in cleanup),
    )


def load_mandatory_update_files(root: Path) -> list[str]:
    return list(load_release_policy(root).mandatory_update_files)


def collect_full_paths(
    source_root: Path,
    excluded_package_roots: Iterable[str] = (),
) -> set[str]:
    source_root = source_root.resolve()
    return {
        path.relative_to(source_root).as_posix()
        for path in source_root.rglob("*")
        if _is_packaged_file(path, source_root, excluded_package_roots)
    }


def collect_update_paths(
    source_root: Path,
    baseline_root: Path,
    mandatory_update_files: Iterable[str],
    mandatory_update_trees: Iterable[str] = (),
    forbidden_update_files: Iterable[str] = ("config.ini",),
    excluded_update_roots: Iterable[str] = ("BACKUP",),
    excluded_package_roots: Iterable[str] = (),
) -> set[str]:
    source_root = source_root.resolve()
    baseline_root = baseline_root.resolve()
    forbidden = {_normalized(x) for x in forbidden_update_files}
    result: set[str] = set()

    for path in source_root.rglob("*"):
        if not _is_packaged_file(path, source_root, excluded_package_roots):
            continue
        rel = path.relative_to(source_root).as_posix()
        if rel in forbidden or _is_under_excluded_update_root(rel, excluded_update_roots):
            continue
        old = baseline_root / rel
        if not old.is_file() or _sha256(path) != _sha256(old):
            result.add(rel)

    for tree in mandatory_update_trees:
        tree_rel = _normalized(tree).rstrip("/")
        tree_root = source_root / tree_rel
        if not tree_root.is_dir():
            raise FileNotFoundError(f"mandatory update tree missing: {tree_rel}")
        found = False
        for path in tree_root.rglob("*"):
            if not _is_packaged_file(path, source_root, excluded_package_roots):
                continue
            rel = path.relative_to(source_root).as_posix()
            if rel in forbidden:
                raise ValueError(f"mandatory tree contains forbidden update file: {rel}")
            result.add(rel)
            found = True
        if not found:
            raise FileNotFoundError(f"mandatory update tree is empty: {tree_rel}")

    for rel in mandatory_update_files:
        rel = _normalized(rel)
        source = source_root / rel
        if rel in forbidden:
            raise ValueError(f"mandatory update artifact is forbidden: {rel}")
        if not source.is_file():
            raise FileNotFoundError(f"mandatory update artifact missing: {rel}")
        result.add(rel)

    result.difference_update(forbidden)
    return result


def _write_zip(source_root: Path, output_zip: Path, paths: Iterable[str]) -> set[str]:
    source_root = source_root.resolve()
    output_zip = output_zip.resolve()
    selected = {_normalized(rel) for rel in paths}
    output_zip.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_zip, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for rel in sorted(selected):
            source = source_root / rel
            if not source.is_file():
                raise FileNotFoundError(f"package source missing: {rel}")
            zf.write(source, arcname=rel)
    return selected


def write_full_zip(
    source_root: Path,
    output_zip: Path,
    excluded_package_roots: Iterable[str] = (),
) -> set[str]:
    return _write_zip(
        source_root,
        output_zip,
        collect_full_paths(source_root, excluded_package_roots),
    )


def write_update_zip(
    source_root: Path,
    baseline_root: Path,
    output_zip: Path,
    mandatory_update_files: Iterable[str],
    mandatory_update_trees: Iterable[str] = (),
    forbidden_update_files: Iterable[str] = ("config.ini",),
    excluded_update_roots: Iterable[str] = ("BACKUP",),
    excluded_package_roots: Iterable[str] = (),
) -> set[str]:
    paths = collect_update_paths(
        source_root,
        baseline_root,
        mandatory_update_files,
        mandatory_update_trees,
        forbidden_update_files,
        excluded_update_roots,
        excluded_package_roots,
    )
    return _write_zip(source_root, output_zip, paths)


def validate_update_baseline_archive(policy: ReleasePolicy, baseline_archive: Path) -> None:
    if policy.update_baseline_mode != "explicit_runtime_archive":
        raise ValueError(f"unsupported update baseline mode: {policy.update_baseline_mode!r}")
    if not baseline_archive.is_file():
        raise FileNotFoundError(baseline_archive)
    if baseline_archive.suffix.lower() != ".zip":
        raise ValueError(f"UPDATE baseline must be a ZIP archive: {baseline_archive}")
    try:
        with zipfile.ZipFile(baseline_archive) as zf:
            bad = zf.testzip()
    except zipfile.BadZipFile as exc:
        raise ValueError(f"UPDATE baseline is not a valid ZIP: {baseline_archive}") from exc
    if bad is not None:
        raise ValueError(f"baseline ZIP CRC failed: {bad}")


# Backward-compatible import name for older callers. Semantics are runtime-selected,
# not filename-pinned.
def validate_canonical_baseline_archive(policy: ReleasePolicy, baseline_archive: Path) -> None:
    validate_update_baseline_archive(policy, baseline_archive)


def verify_zip_against_source(
    source_root: Path,
    archive: Path,
    expected_paths: Iterable[str],
    excluded_package_roots: Iterable[str] = (),
) -> None:
    source_root = source_root.resolve()
    expected = {_normalized(x) for x in expected_paths}
    excluded_roots = {_normalized(x).rstrip("/") for x in excluded_package_roots}
    with zipfile.ZipFile(archive) as zf:
        bad = zf.testzip()
        if bad is not None:
            raise ValueError(f"ZIP CRC failed: {bad}")
        names = {name.rstrip("/") for name in zf.namelist() if not name.endswith("/")}
        forbidden = sorted(
            name for name in names
            if Path(name).parts and Path(name).parts[0] in excluded_roots
        )
        if forbidden:
            raise ValueError(f"ZIP contains excluded package root: {forbidden[:20]}")
        if names != expected:
            missing = sorted(expected - names)
            extra = sorted(names - expected)
            raise ValueError(f"ZIP content mismatch: missing={missing[:20]} extra={extra[:20]}")
        with tempfile.TemporaryDirectory(prefix="phase6-release-verify-") as td:
            root = Path(td)
            zf.extractall(root)
            for rel in sorted(expected):
                if _sha256(root / rel) != _sha256(source_root / rel):
                    raise ValueError(f"ZIP SHA256 mismatch: {rel}")


def build_release(
    source_root: Path,
    baseline_archive: Path,
    output_dir: Path,
    release_name: str,
    timestamp: str,
) -> tuple[Path, Path, set[str], set[str]]:
    source_root = source_root.resolve()
    policy = load_release_policy(source_root)
    validate_update_baseline_archive(policy, baseline_archive)
    full_zip = output_dir / f"{release_name}_FULL_{timestamp}.zip"
    update_zip = output_dir / f"{release_name}_UPDATE_{timestamp}.zip"
    with tempfile.TemporaryDirectory(prefix="phase6-canonical-baseline-") as td:
        baseline_root = Path(td)
        with zipfile.ZipFile(baseline_archive) as zf:
            zf.extractall(baseline_root)
        for rel in policy.update_cleanup_paths:
            rel = _normalized(rel).rstrip("/")
            parts = Path(rel).parts
            if not rel or rel.startswith("/") or ".." in parts:
                raise ValueError(f"unsafe update cleanup path: {rel!r}")
            if (source_root / rel).exists():
                raise ValueError(f"cleanup path still exists in current source: {rel}")
            if not (baseline_root / rel).exists():
                raise ValueError(f"cleanup path missing from canonical baseline: {rel}")
        full_paths = write_full_zip(
            source_root, full_zip, policy.excluded_package_roots
        )
        update_paths = write_update_zip(
            source_root,
            baseline_root,
            update_zip,
            policy.mandatory_update_files,
            policy.mandatory_update_trees,
            policy.forbidden_update_files,
            policy.excluded_update_roots,
            policy.excluded_package_roots,
        )
    verify_zip_against_source(
        source_root, full_zip, full_paths, policy.excluded_package_roots
    )
    verify_zip_against_source(
        source_root, update_zip, update_paths, policy.excluded_package_roots
    )
    forbidden = set(policy.forbidden_update_files)
    if update_paths & forbidden:
        raise ValueError(f"forbidden files entered UPDATE: {sorted(update_paths & forbidden)}")
    for tree in policy.mandatory_update_trees:
        source_tree = {
            p.relative_to(source_root).as_posix()
            for p in (source_root / tree).rglob("*")
            if _is_packaged_file(p, source_root, policy.excluded_package_roots)
        }
        if not source_tree.issubset(update_paths):
            raise ValueError(f"mandatory update tree incomplete: {tree}")
    return full_zip, update_zip, full_paths, update_paths
