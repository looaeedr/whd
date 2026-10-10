"""Canonical regression sharding must preserve every selector and every case."""
from collections import Counter
from pathlib import Path
import tempfile
import xml.etree.ElementTree as ET

import pytest

from tools.product_ci_regression import (
    PYTEST_PATHS, _merge_shard_junit, _pytest_command, shard_paths,
)


@pytest.mark.parametrize("count", [1, 2, 3, 4, 7, len(PYTEST_PATHS)])
def test_each_selector_appears_in_exactly_one_shard(count):
    shards = [shard_paths(i, count) for i in range(count)]
    seen = Counter(path for shard in shards for path in shard)
    assert set(seen) == set(PYTEST_PATHS)
    assert all(n == 1 for n in seen.values())
    assert all(shards)
    assert shards == [PYTEST_PATHS[i::count] for i in range(count)]


@pytest.mark.parametrize("index,count", [(-1, 3), (3, 3), (0, 0),
                                          (0, len(PYTEST_PATHS) + 1)])
def test_invalid_shard_fails_closed(index, count):
    with pytest.raises(ValueError, match="invalid regression shard"):
        shard_paths(index, count)


def _report(path: Path, names, *, failing=False):
    root = ET.Element("testsuites")
    suite = ET.SubElement(root, "testsuite")
    for name in names:
        case = ET.SubElement(suite, "testcase", {
            "classname": "tests.test_dummy",
            "name": name,
        })
        if failing:
            ET.SubElement(case, "failure", {"message": "intentional"})
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)


def test_merge_retains_all_cases_without_skips_or_dedup():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        a, b, c = [base / f"shard-{i}.xml" for i in range(3)]
        _report(a, ["case_a", "case_b"])
        _report(b, ["case_c"])
        _report(c, ["case_d"])
        output = base / "combined.xml"
        _merge_shard_junit([c, a, b], 3, output)
        cases = ET.parse(output).getroot().findall(".//testcase")
        assert [x.get("name") for x in cases] == [
            "case_a", "case_b", "case_c", "case_d"
        ]


def test_merge_rejects_missing_duplicate_or_non_green_shards():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        a, b, c = [base / f"shard-{i}.xml" for i in range(3)]
        _report(a, ["a"])
        _report(b, ["b"])
        _report(c, ["c"])
        output = base / "combined.xml"
        with pytest.raises(ValueError, match="mandatory"):
            _merge_shard_junit([a, b], 3, output)
        with pytest.raises(ValueError, match="duplicate"):
            _merge_shard_junit([a, a, c], 3, output)
        _report(b, ["b"], failing=True)
        with pytest.raises(ValueError, match="non-green"):
            _merge_shard_junit([a, b, c], 3, output)


def test_pytest_command_uses_only_provided_selectors_and_reports_durations():
    command = _pytest_command(Path("sample.xml"), ("tests/test_issue1464_custom_manufacturing.py",))
    assert "--durations=15" in command
    assert "--junitxml" in command
    assert "tests/test_issue1464_custom_manufacturing.py" in command
    assert "tests/test_issue1465_quantity_ui.py" not in command
