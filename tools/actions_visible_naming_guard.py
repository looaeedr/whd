from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Iterable

_HAN_RE = re.compile(r"[\u3400-\u9fff]")
_TOP_SCALAR_RE = re.compile(r"^(name|run-name):\s*(.*?)\s*$")
_JOB_RE = re.compile(r"^  ([A-Za-z0-9_.-]+):\s*(?:#.*)?$")
_JOB_NAME_RE = re.compile(r"^    name:\s*(.*?)\s*$")
_STEPS_RE = re.compile(r"^    steps:\s*(?:#.*)?$")
_STEP_START_RE = re.compile(r"^      -(?:\s+|$)")
_STEP_INLINE_NAME_RE = re.compile(r"^      -\s+name:\s*(.*?)\s*$")
_STEP_NAME_RE = re.compile(r"^        name:\s*(.*?)\s*$")
_BLOCK_SCALARS = {"|", "|-", "|+", ">", ">-", ">+"}


def _has_han(value: str) -> bool:
    return bool(_HAN_RE.search(str(value or "")))


def _collect_top_scalar(lines: list[str], key: str) -> str | None:
    for index, line in enumerate(lines):
        match = _TOP_SCALAR_RE.match(line)
        if not match or match.group(1) != key:
            continue
        value = match.group(2).strip()
        if value not in _BLOCK_SCALARS:
            return value
        chunks: list[str] = []
        for follow in lines[index + 1 :]:
            if follow and not follow.startswith((" ", "\t")):
                break
            if follow.strip():
                chunks.append(follow.strip())
        return " ".join(chunks)
    return None


def validate_workflow_text(text: str, *, path: str = "<memory>") -> list[str]:
    lines = text.splitlines()
    errors: list[str] = []

    workflow_name = _collect_top_scalar(lines, "name")
    run_name = _collect_top_scalar(lines, "run-name")
    if workflow_name is None:
        errors.append(f"{path}: 缺少 top-level name")
    elif not _has_han(workflow_name):
        errors.append(f"{path}: workflow name 必須包含繁體中文可見文字: {workflow_name!r}")

    if run_name is None:
        errors.append(f"{path}: 缺少 top-level run-name，禁止 fallback 到 commit message")
    elif not _has_han(run_name):
        errors.append(f"{path}: run-name 必須包含繁體中文可見文字: {run_name!r}")

    try:
        jobs_index = next(i for i, line in enumerate(lines) if line.strip() == "jobs:" and not line.startswith(" "))
    except StopIteration:
        errors.append(f"{path}: 缺少 jobs")
        return errors

    job_starts: list[tuple[int, str]] = []
    for index in range(jobs_index + 1, len(lines)):
        match = _JOB_RE.match(lines[index])
        if match:
            job_starts.append((index, match.group(1)))

    if not job_starts:
        errors.append(f"{path}: jobs 下沒有可辨識 job")
        return errors

    for pos, (start, job_id) in enumerate(job_starts):
        end = job_starts[pos + 1][0] if pos + 1 < len(job_starts) else len(lines)
        block = lines[start:end]

        job_name = None
        for line in block[1:]:
            match = _JOB_NAME_RE.match(line)
            if match:
                job_name = match.group(1).strip()
                break
        if job_name is None:
            errors.append(f"{path}: job {job_id!r} 缺少 user-visible name")
        elif not _has_han(job_name):
            errors.append(f"{path}: job {job_id!r} name 必須包含繁體中文: {job_name!r}")

        steps_rel = None
        for rel, line in enumerate(block):
            if _STEPS_RE.match(line):
                steps_rel = rel
                break
        if steps_rel is None:
            continue

        step_starts = [
            rel
            for rel in range(steps_rel + 1, len(block))
            if _STEP_START_RE.match(block[rel])
        ]
        for step_pos, step_start in enumerate(step_starts):
            step_end = step_starts[step_pos + 1] if step_pos + 1 < len(step_starts) else len(block)
            step_block = block[step_start:step_end]
            step_name = None

            inline = _STEP_INLINE_NAME_RE.match(step_block[0])
            if inline:
                step_name = inline.group(1).strip()
            else:
                for line in step_block[1:]:
                    match = _STEP_NAME_RE.match(line)
                    if match:
                        step_name = match.group(1).strip()
                        break

            ordinal = step_pos + 1
            if step_name is None:
                errors.append(f"{path}: job {job_id!r} step {ordinal} 缺少 user-visible name")
            elif not _has_han(step_name):
                errors.append(
                    f"{path}: job {job_id!r} step {ordinal} name 必須包含繁體中文: {step_name!r}"
                )

    return errors


def validate_paths(paths: Iterable[str | Path]) -> list[str]:
    errors: list[str] = []
    for raw in paths:
        path = Path(raw)
        if not path.is_file():
            errors.append(f"{path}: workflow 檔案不存在")
            continue
        errors.extend(validate_workflow_text(path.read_text(encoding="utf-8"), path=path.as_posix()))
    return errors


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print("usage: python tools/actions_visible_naming_guard.py <workflow.yml> [...]")
        return 2

    errors = validate_paths(args)
    if errors:
        for error in errors:
            print(f"ACTIONS_VISIBLE_NAMING_RED {error}")
        return 1

    print(f"ACTIONS_VISIBLE_NAMING_GREEN files={len(args)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
