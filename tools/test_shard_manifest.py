"""Deterministic pytest shard manifest generation for WHD CI.

T1 is metadata-only: this module inventories the existing lane taxonomy,
assigns canonical node ids to deterministic SHA-256 HRW shards, and fails
closed if lane or shard ownership does not reconcile with full collection.
It does not execute test shards or alter test semantics.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.test_lane_policy import LANE_EXPRESSIONS, XVFB_UI_EXPRESSION


ALGORITHM_VERSION = "sha256-hrw-v1"
CONFIG_SCHEMA = "WHD_TEST_SHARD_CONFIG_V1"
LANE_MANIFEST_SCHEMA = "WHD_TEST_LANE_MANIFEST_V1"
SHARD_MANIFEST_SCHEMA = "WHD_TEST_SHARD_MANIFEST_V1"
DIGESTS_SCHEMA = "WHD_TEST_MANIFEST_DIGESTS_V1"


class ManifestError(ValueError):
    """Fail-closed manifest/reconciliation error with a stable reason token."""


@dataclass(frozen=True)
class ManifestBundle:
    lane_manifest: dict[str, object]
    shard_manifest: dict[str, object]
    reconciliation: dict[str, object]
    lane_manifest_bytes: bytes
    shard_manifest_bytes: bytes
    lane_manifest_sha256: str
    shard_manifest_sha256: str
    full_collection_sha256: str
    config_sha256: str


def canonical_node_id(raw: str) -> str:
    """Canonicalize pytest node-id path syntax without touching node suffix text."""
    value = str(raw).strip()
    if "::" in value:
        path_text, suffix = value.split("::", 1)
        suffix_text = f"::{suffix}"
    else:
        path_text, suffix_text = value, ""
    path_text = path_text.replace("\\", "/")
    while path_text.startswith("./"):
        path_text = path_text[2:]
    return f"{path_text}{suffix_text}"


def canonical_json_bytes(payload: object) -> bytes:
    """Return language-neutral canonical JSON bytes with no trailing newline."""
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def hrw_score(
    lane: str,
    node_id: str,
    shard_id: str,
    *,
    algorithm: str = ALGORITHM_VERSION,
) -> int:
    """Return the SHA-256 HRW score for one lane/node/shard candidate."""
    if algorithm != ALGORITHM_VERSION:
        raise ManifestError(f"UNSUPPORTED_ALGORITHM: {algorithm}")
    framed = "\0".join(
        (algorithm, str(lane), canonical_node_id(node_id), str(shard_id))
    ).encode("utf-8")
    return int.from_bytes(hashlib.sha256(framed).digest(), "big")


def choose_shard(lane: str, node_id: str, shard_ids: Sequence[str]) -> str:
    """Choose the highest-scoring HRW shard; lexical order breaks score ties."""
    candidates = sorted({str(shard_id) for shard_id in shard_ids})
    if not candidates:
        raise ManifestError("INVALID_SHARD_COUNT: no shard ids")
    best_id = candidates[0]
    best_score = hrw_score(lane, node_id, best_id)
    for shard_id in candidates[1:]:
        score = hrw_score(lane, node_id, shard_id)
        if score > best_score:
            best_score = score
            best_id = shard_id
    return best_id


def _canonical_set(nodes: Iterable[str]) -> set[str]:
    return {canonical_node_id(node) for node in nodes}


def _duplicate_owners(mapping: Mapping[str, set[str]]) -> dict[str, list[str]]:
    owners: dict[str, list[str]] = {}
    for owner, nodes in mapping.items():
        for node in nodes:
            owners.setdefault(node, []).append(owner)
    return {
        node: sorted(node_owners)
        for node, node_owners in sorted(owners.items())
        if len(node_owners) > 1
    }


def reconcile_ownership(
    full_nodes: Iterable[str],
    lane_nodes: Mapping[str, Iterable[str]],
    shard_nodes: Mapping[str, Iterable[str]],
) -> dict[str, object]:
    """Verify exact one-lane/one-shard ownership against full collection."""
    full = _canonical_set(full_nodes)
    lanes = {str(name): _canonical_set(nodes) for name, nodes in lane_nodes.items()}
    shards = {str(name): _canonical_set(nodes) for name, nodes in shard_nodes.items()}

    lane_union = set().union(*lanes.values()) if lanes else set()
    lane_missing = sorted(full - lane_union)
    lane_extra = sorted(lane_union - full)
    lane_duplicate = _duplicate_owners(lanes)

    if lane_missing:
        raise ManifestError(f"LANE_MISSING: {lane_missing}")
    if lane_extra:
        raise ManifestError(f"LANE_EXTRA: {lane_extra}")
    if lane_duplicate:
        raise ManifestError(f"LANE_DUPLICATE: {lane_duplicate}")

    shard_union = set().union(*shards.values()) if shards else set()
    shard_missing = sorted(full - shard_union)
    shard_extra = sorted(shard_union - full)
    shard_duplicate = _duplicate_owners(shards)

    if shard_missing:
        raise ManifestError(f"SHARD_MISSING: {shard_missing}")
    if shard_extra:
        raise ManifestError(f"SHARD_EXTRA: {shard_extra}")
    if shard_duplicate:
        raise ManifestError(f"SHARD_DUPLICATE: {shard_duplicate}")

    return {
        "full_count": len(full),
        "lane_union_count": len(lane_union),
        "unique_shard_union_count": len(shard_union),
        "lane_missing": [],
        "lane_extra": [],
        "lane_duplicate": {},
        "shard_missing": [],
        "shard_extra": [],
        "shard_duplicate": {},
    }


def _shard_ids(count: int) -> list[str]:
    if isinstance(count, bool) or not isinstance(count, int) or count <= 0:
        raise ManifestError(f"INVALID_SHARD_COUNT: {count!r}")
    width = max(2, len(str(count - 1)))
    return [f"s{index:0{width}d}" for index in range(count)]


def build_manifests(
    full_nodes: Iterable[str],
    lane_nodes: Mapping[str, Iterable[str]],
    shard_counts: Mapping[str, int],
    *,
    source_sha: str,
) -> ManifestBundle:
    """Build deterministic lane/shard manifests and fail closed on drift."""
    full = sorted(_canonical_set(full_nodes))
    lanes = {
        str(lane): sorted(_canonical_set(nodes))
        for lane, nodes in lane_nodes.items()
    }
    counts = {str(lane): count for lane, count in shard_counts.items()}

    if set(lanes) != set(counts):
        raise ManifestError(
            "CONFIG_LANE_MISMATCH: "
            f"lane_only={sorted(set(lanes) - set(counts))} "
            f"config_only={sorted(set(counts) - set(lanes))}"
        )
    for count in counts.values():
        _shard_ids(count)

    # Validate lane ownership before generating shards so lane defects retain
    # their own stable reason tokens.
    lane_union = set().union(*(set(nodes) for nodes in lanes.values())) if lanes else set()
    lane_missing = sorted(set(full) - lane_union)
    lane_extra = sorted(lane_union - set(full))
    lane_duplicate = _duplicate_owners({name: set(nodes) for name, nodes in lanes.items()})
    if lane_missing:
        raise ManifestError(f"LANE_MISSING: {lane_missing}")
    if lane_extra:
        raise ManifestError(f"LANE_EXTRA: {lane_extra}")
    if lane_duplicate:
        raise ManifestError(f"LANE_DUPLICATE: {lane_duplicate}")

    flat_shards: dict[str, set[str]] = {}
    nested_shards: dict[str, dict[str, list[str]]] = {}
    for lane in sorted(lanes):
        ids = _shard_ids(counts[lane])
        lane_shards = {shard_id: [] for shard_id in ids}
        for node in lanes[lane]:
            lane_shards[choose_shard(lane, node, ids)].append(node)
        nested_shards[lane] = {
            shard_id: sorted(nodes) for shard_id, nodes in sorted(lane_shards.items())
        }
        for shard_id, nodes in nested_shards[lane].items():
            flat_shards[f"{lane}:{shard_id}"] = set(nodes)

    reconciliation = reconcile_ownership(full, lanes, flat_shards)

    config_payload = {
        "algorithm": ALGORITHM_VERSION,
        "schema": CONFIG_SCHEMA,
        "shard_counts": {lane: counts[lane] for lane in sorted(counts)},
    }
    config_sha256 = _sha256(canonical_json_bytes(config_payload))
    full_collection_sha256 = _sha256(canonical_json_bytes(full))

    lane_manifest: dict[str, object] = {
        "algorithm": ALGORITHM_VERSION,
        "config_sha256": config_sha256,
        "full_collection_count": len(full),
        "full_collection_sha256": full_collection_sha256,
        "lanes": {
            lane: {"count": len(lanes[lane]), "nodes": lanes[lane]}
            for lane in sorted(lanes)
        },
        "schema": LANE_MANIFEST_SCHEMA,
        "source_sha": str(source_sha),
    }
    shard_manifest: dict[str, object] = {
        "algorithm": ALGORITHM_VERSION,
        "config_sha256": config_sha256,
        "full_collection_count": len(full),
        "full_collection_sha256": full_collection_sha256,
        "reconciliation": reconciliation,
        "schema": SHARD_MANIFEST_SCHEMA,
        "shards": {
            lane: {
                shard_id: {"count": len(nodes), "nodes": nodes}
                for shard_id, nodes in sorted(nested_shards[lane].items())
            }
            for lane in sorted(nested_shards)
        },
        "source_sha": str(source_sha),
    }

    lane_bytes = canonical_json_bytes(lane_manifest)
    shard_bytes = canonical_json_bytes(shard_manifest)
    return ManifestBundle(
        lane_manifest=lane_manifest,
        shard_manifest=shard_manifest,
        reconciliation=reconciliation,
        lane_manifest_bytes=lane_bytes,
        shard_manifest_bytes=shard_bytes,
        lane_manifest_sha256=_sha256(lane_bytes),
        shard_manifest_sha256=_sha256(shard_bytes),
        full_collection_sha256=full_collection_sha256,
        config_sha256=config_sha256,
    )


def _collect(expr: str | None) -> list[str]:
    cmd = [sys.executable, "-m", "pytest", "--collect-only", "-q", "tests"]
    if expr:
        cmd.extend(["-m", expr])
    proc = subprocess.run(
        cmd,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if proc.returncode != 0:
        raise ManifestError(
            f"COLLECTION_FAILED: expr={expr!r} rc={proc.returncode}\n{proc.stdout}"
        )
    return sorted(
        {
            canonical_node_id(line)
            for line in proc.stdout.splitlines()
            if line.startswith("tests/") and "::" in line
        }
    )


def _load_config(path: Path) -> dict[str, int]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema") != CONFIG_SCHEMA:
        raise ManifestError(f"CONFIG_SCHEMA_MISMATCH: {payload.get('schema')!r}")
    if payload.get("algorithm") != ALGORITHM_VERSION:
        raise ManifestError(f"UNSUPPORTED_ALGORITHM: {payload.get('algorithm')!r}")
    counts = payload.get("shard_counts")
    if not isinstance(counts, dict):
        raise ManifestError("CONFIG_LANE_MISMATCH: shard_counts is not an object")
    normalized = {str(lane): count for lane, count in counts.items()}
    for count in normalized.values():
        _shard_ids(count)
    return normalized


def _git_head() -> str:
    proc = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        raise ManifestError(f"SOURCE_SHA_FAILED: {proc.stderr.strip()}")
    return proc.stdout.strip()


def _write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload + b"\n")


def generate_live_manifests(
    *,
    out_dir: Path,
    config_path: Path,
    source_sha: str,
) -> ManifestBundle:
    full = _collect(None)
    lane_nodes = {lane: _collect(expr) for lane, expr in LANE_EXPRESSIONS.items()}
    lane_nodes["xvfb_ui"] = _collect(XVFB_UI_EXPRESSION)
    counts = _load_config(config_path)
    bundle = build_manifests(full, lane_nodes, counts, source_sha=source_sha)

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "full-collection.txt").write_text(
        "\n".join(full) + ("\n" if full else ""),
        encoding="utf-8",
    )
    _write_bytes(out_dir / "lane-manifest.json", bundle.lane_manifest_bytes)
    _write_bytes(out_dir / "shard-manifest.json", bundle.shard_manifest_bytes)
    reconciliation_bytes = canonical_json_bytes(bundle.reconciliation)
    _write_bytes(out_dir / "reconciliation.json", reconciliation_bytes)

    digests = {
        "algorithm": ALGORITHM_VERSION,
        "config_sha256": bundle.config_sha256,
        "full_collection_sha256": bundle.full_collection_sha256,
        "lane_manifest_sha256": bundle.lane_manifest_sha256,
        "reconciliation_sha256": _sha256(reconciliation_bytes),
        "schema": DIGESTS_SCHEMA,
        "shard_manifest_sha256": bundle.shard_manifest_sha256,
        "source_sha": source_sha,
    }
    _write_bytes(out_dir / "manifest-digests.json", canonical_json_bytes(digests))
    return bundle


def main() -> int:
    parser = argparse.ArgumentParser(description="Build deterministic WHD pytest shard manifests")
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument(
        "--config",
        type=Path,
        default=ROOT / "config" / "ci_test_shards.json",
    )
    parser.add_argument("--source-sha")
    args = parser.parse_args()

    source_sha = args.source_sha or _git_head()
    try:
        bundle = generate_live_manifests(
            out_dir=args.out_dir,
            config_path=args.config,
            source_sha=source_sha,
        )
    except ManifestError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    summary = {
        "config_sha256": bundle.config_sha256,
        "full_count": bundle.reconciliation["full_count"],
        "lane_manifest_sha256": bundle.lane_manifest_sha256,
        "lane_union_count": bundle.reconciliation["lane_union_count"],
        "shard_manifest_sha256": bundle.shard_manifest_sha256,
        "source_sha": source_sha,
        "unique_shard_union_count": bundle.reconciliation["unique_shard_union_count"],
    }
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
