from __future__ import annotations

from pathlib import Path

from tools import xvfb_shard_execution as execution


def test_junit_failure_location_falls_back_to_traceback_when_testcase_has_no_line(tmp_path: Path) -> None:
    xml = tmp_path / "result.xml"
    xml.write_text(
        '<testsuites><testsuite>'
        '<testcase classname="tests.x" name="test_a">'
        '<failure message="AssertionError: boom">'
        'tests/x.py:17: in test_a\n    assert False\nE   AssertionError: boom'
        '</failure>'
        '</testcase>'
        '</testsuite></testsuites>',
        encoding="utf-8",
    )

    result = execution.read_xvfb_junit(xml, ["tests/x.py::test_a"])

    assert result["failure_evidence"]["tests/x.py::test_a"]["file"] == "tests/x.py"
    assert result["failure_evidence"]["tests/x.py::test_a"]["line"] == 17
