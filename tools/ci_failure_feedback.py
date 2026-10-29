#!/usr/bin/env python3
"""Show exact failing pytest nodes from a shard JUnit without weakening CI.

Development feedback only. This step always returns 0 so the original failed
product test remains the authoritative CI failure. Missing/malformed JUnit and
unknown test nodes are explicitly reported as unresolved, never as GREEN.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path, PurePosixPath
import sys
import xml.etree.ElementTree as ET

try:
    from tools.change_test_profile import build_fast_feedback
except ModuleNotFoundError:  # python tools/ci_failure_feedback.py
    from change_test_profile import build_fast_feedback

MAX_JUNIT_BYTES = 16 * 1024 * 1024
MAX_DISPLAY = 20


def _valid_source_file(raw: str, root: Path) -> str | None:
    if not raw or any(ord(char) < 32 or ord(char) == 127 for char in raw):
        return None
    raw = raw.replace("\\", "/")
    path = PurePosixPath(raw)
    if (path.is_absolute() or ".." in path.parts or path.as_posix() != raw
            or not raw.startswith("tests/") or not raw.endswith(".py")
            or not path.name.startswith("test_")):
        return None
    base = root.resolve()
    absolute = (base / raw).resolve()
    if not absolute.is_relative_to(base) or not absolute.is_file():
        return None
    return raw


def _selector(case: ET.Element, root: Path) -> str | None:
    name = case.get("name", "")
    if (not name.startswith("test_")
            or any(ord(c) < 32 or ord(c) == 127 for c in name)):
        return None
    classname = case.get("classname", "")
    file_attr = case.get("file", "")
    source = _valid_source_file(file_attr, root)
    classes: list[str] = []
    if source is None and classname:
        parts = classname.split(".")
        for index in range(len(parts), 0, -1):
            candidate = "/".join(parts[:index]) + ".py"
            source = _valid_source_file(candidate, root)
            if source is not None:
                classes = parts[index:]
                break
    elif source is not None and classname:
        parts = classname.split(".")
        module = source.removesuffix(".py").replace("/", ".")
        if classname == module:
            classes = []
        elif classname.startswith(module + "."):
            classes = classname[len(module) + 1:].split(".")
        else:
            return None
    if source is None or any(not segment.isidentifier() for segment in classes):
        return None
    return "::".join((source, *classes, name))


def inspect_junit(junit: Path, *, root: Path) -> dict[str, object]:
    if not junit.is_file():
        return {"status": "NO_JUNIT", "failed_cases": 0, "selectors": [],
                "command": None}
    try:
        if junit.stat().st_size > MAX_JUNIT_BYTES:
            raise ValueError("JUnit exceeded size bound")
        raw = junit.read_bytes()
        if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
            raise ValueError("DTD/entity prohibited")
        suite = ET.fromstring(raw)
    except (OSError, ET.ParseError, ValueError) as exc:
        return {"status": "INVALID_JUNIT", "failed_cases": 0, "selectors": [],
                "command": None, "error": type(exc).__name__}

    failures = [
        case for case in suite.findall(".//testcase")
        if case.find("failure") is not None or case.find("error") is not None
    ]
    selectors = list(dict.fromkeys(
        selected for case in failures
        if (selected := _selector(case, root)) is not None
    ))
    if not failures:
        status = "NO_FAILED_CASE_IN_JUNIT"
        command = None
    elif len(selectors) != len(failures):
        status = "UNRESOLVED_FAILED_CASE"
        command = None  # Never offer a misleading partial retry command.
    elif len(selectors) > MAX_DISPLAY:
        status = "TOO_MANY_FAILED_CASES"
        command = None
    else:
        profile = build_fast_feedback(
            ["tests/test_ci_bounded_install.py"], feedback_tests=selectors
        )
        status = profile["status"]
        command = profile["command"]
    return {"status": status, "failed_cases": len(failures),
            "selectors": selectors, "command": command}


def _escape_annotation(value: str) -> str:
    return (value.replace("%", "%25").replace("\r", "%0D")
            .replace("\n", "%0A").replace(",", "%2C").replace(":", "%3A"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--junit", required=True, type=Path)
    args = parser.parse_args(argv)
    result = inspect_junit(args.junit, root=Path.cwd())
    print(f"CI_FAST_FEEDBACK_STATUS={result['status']} failed_cases={result['failed_cases']}")
    if result["status"] == "READY":
        for selector in result["selectors"]:
            source = str(selector).split("::", 1)[0]
            print("::error file=" + _escape_annotation(source)
                  + ",title=Product regression failed::" + _escape_annotation(str(selector)))
        print("CI_FAST_FEEDBACK_COMMAND=" + str(result["command"]))
    else:
        print("CI_FAST_FEEDBACK_UNRESOLVED=Read original failing job/step/JUnit; "
              "do not count partial or missing evidence as passed.")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        try:
            with open(summary, "a", encoding="utf-8") as stream:
                stream.write("\n### Product CI failure: targeted development feedback\n")
                stream.write(f"- Status: \u0060{result['status']}\u0060\n")
                stream.write(f"- Failed cases in JUnit: {result['failed_cases']}\n")
                if result["status"] == "READY":
                    stream.write("- Local/cloud workspace retry (does not replace full CI):\n")
                    stream.write("\u0060\u0060\u0060sh\n" + str(result["command"])
                                 + "\n\u0060\u0060\u0060\n")
        except OSError as exc:
            print("CI_FAST_FEEDBACK_SUMMARY_WRITE_FAILED=" + type(exc).__name__)
    return 0


if __name__ == "__main__":
    sys.exit(main())
