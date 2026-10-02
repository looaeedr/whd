from __future__ import annotations

import random

import pytest

from tools.test_shard_manifest import (
    ALGORITHM_VERSION,
    ManifestError,
    build_manifests,
    canonical_json_bytes,
    canonical_node_id,
    choose_shard,
    hrw_score,
    reconcile_ownership,
)


def test_canonical_node_id_normalizes_only_path_syntax() -> None:
    raw = r" ./tests\test_a.py::test_Case[param/Value] "
    assert canonical_node_id(raw) == "tests/test_a.py::test_Case[param/Value]"


def test_hrw_score_uses_normative_sha256_framing_and_owner_is_order_independent() -> None:
    node = "tests/test_a.py::test_case[param]"
    assert ALGORITHM_VERSION == "sha256-hrw-v1"
    assert hrw_score("unit", node, "s00") == (
        24398440403218355190566505360480890002061931653307926707996181872747795730523
    )
    shards = ["s00", "s01", "s02", "s03"]
    expected = choose_shard("unit", node, shards)
    assert choose_shard("unit", node, list(reversed(shards))) == expected
    shuffled = shards[:]
    random.Random(305).shuffle(shuffled)
    assert choose_shard("unit", node, shuffled) == expected


def test_hrw_adding_shard_only_moves_nodes_to_new_shard_and_inventory_growth_is_stable() -> None:
    nodes = [f"tests/test_synthetic.py::test_case[{i:03d}]" for i in range(200)]
    old_shards = ["s00", "s01", "s02"]
    new_shards = ["s00", "s01", "s02", "s03"]
    old = {node: choose_shard("integration", node, old_shards) for node in nodes}
    new = {node: choose_shard("integration", node, new_shards) for node in nodes}
    changed = {node for node in nodes if old[node] != new[node]}
    assert changed
    assert {new[node] for node in changed} == {"s03"}
    extended = nodes + ["tests/test_synthetic.py::test_new_case"]
    extended_owners = {node: choose_shard("integration", node, old_shards) for node in extended}
    assert {node: extended_owners[node] for node in nodes} == old


@pytest.mark.parametrize(
    ("full_nodes", "lane_nodes", "shard_nodes", "reason"),
    [
        ({"a", "b"}, {"unit": {"a"}}, {"unit:s00": {"a"}}, "LANE_MISSING"),
        ({"a"}, {"unit": {"a", "b"}}, {"unit:s00": {"a", "b"}}, "LANE_EXTRA"),
        ({"a"}, {"unit": {"a"}, "integration": {"a"}}, {"unit:s00": {"a"}}, "LANE_DUPLICATE"),
        ({"a", "b"}, {"unit": {"a", "b"}}, {"unit:s00": {"a"}}, "SHARD_MISSING"),
        ({"a"}, {"unit": {"a"}}, {"unit:s00": {"a", "b"}}, "SHARD_EXTRA"),
        ({"a"}, {"unit": {"a"}}, {"unit:s00": {"a"}, "unit:s01": {"a"}}, "SHARD_DUPLICATE"),
    ],
)
def test_reconciliation_fails_closed_with_stable_reason_tokens(
    full_nodes: set[str],
    lane_nodes: dict[str, set[str]],
    shard_nodes: dict[str, set[str]],
    reason: str,
) -> None:
    with pytest.raises(ManifestError, match=reason):
        reconcile_ownership(full_nodes, lane_nodes, shard_nodes)


def test_build_manifests_rejects_config_lane_mismatch_and_invalid_counts() -> None:
    full = {"tests/test_a.py::test_a"}
    lanes = {"unit": set(full)}
    with pytest.raises(ManifestError, match="CONFIG_LANE_MISMATCH"):
        build_manifests(full, lanes, {"unit": 1, "integration": 1}, source_sha="abc")
    with pytest.raises(ManifestError, match="INVALID_SHARD_COUNT"):
        build_manifests(full, lanes, {"unit": 0}, source_sha="abc")


def test_manifest_payloads_and_digests_are_byte_stable_for_logically_identical_input() -> None:
    nodes = [
        "tests/test_a.py::test_b",
        "tests/test_a.py::test_a",
        "tests/test_b.py::test_c[param]",
    ]
    lane_nodes_a = {"unit": nodes[:2], "integration": nodes[2:]}
    lane_nodes_b = {"integration": list(reversed(nodes[2:])), "unit": list(reversed(nodes[:2]))}
    counts_a = {"unit": 2, "integration": 3}
    counts_b = {"integration": 3, "unit": 2}
    first = build_manifests(nodes, lane_nodes_a, counts_a, source_sha="deadbeef")
    second = build_manifests(list(reversed(nodes)), lane_nodes_b, counts_b, source_sha="deadbeef")
    assert first.lane_manifest_bytes == second.lane_manifest_bytes
    assert first.shard_manifest_bytes == second.shard_manifest_bytes
    assert first.lane_manifest_sha256 == second.lane_manifest_sha256
    assert first.shard_manifest_sha256 == second.shard_manifest_sha256
    assert canonical_json_bytes(first.lane_manifest) == first.lane_manifest_bytes
    assert canonical_json_bytes(first.shard_manifest) == first.shard_manifest_bytes
