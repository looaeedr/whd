"""Repack a verified WHD Windows ZIP with a corrected zh-TW update note.

Only the ZIP's 本次更新.md is replaced. All other extracted file bytes,
including WHD.exe, must be unchanged. No Git tag/X/Release mutation here:
the authorized GitHub workflow separately validates and uploads the output.
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import zipfile

from tools.release_notes_zh_tw import validate_notes


def read_release_body(document: Path, *, tag: str, sha: str) -> str:
    raw = document.read_text(encoding="utf-8")
    if not raw.startswith("---\n") or "\n---\n" not in raw:
        raise ValueError("BACKFILL_RELEASE_NOTES_METADATA_REQUIRED")
    body = raw.split("\n---\n", 1)[1].strip() + "\n"
    validate_notes(body)
    if tag not in body or sha not in body:
        raise ValueError("BACKFILL_RELEASE_NOTES_IDENTITY_MISMATCH")
    return body


def repack(
    original: Path, output_dir: Path, *,
    tag: str, sha: str, body: str,
) -> tuple[Path, Path]:
    if not tag.startswith("v") or len(sha) != 40 or any(c not in "0123456789abcdef" for c in sha):
        raise ValueError("BACKFILL_INVALID_RELEASE_IDENTITY")
    expected_name = f"WHD_Windows_x64_{tag}.zip"
    if original.name != expected_name:
        raise ValueError("BACKFILL_WRONG_ARCHIVE_TAG")
    validate_notes(body)
    if tag not in body or sha not in body:
        raise ValueError("BACKFILL_WRONG_NOTES_SOURCE")
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / expected_name
    if original.resolve() == target.resolve():
        raise ValueError("BACKFILL_SOURCE_CANNOT_BE_OVERWRITTEN")
    data = body.encode("utf-8")
    replacements = {"WHD/本次更新.md": data}
    files: dict[str, str] = {}
    with zipfile.ZipFile(original, "r") as src, zipfile.ZipFile(target, "w", allowZip64=True) as dst:
        entries = src.infolist()
        names = [entry.filename.replace("\\", "/") for entry in entries]
        if len(names) != len(set(names)):
            raise ValueError("BACKFILL_DUPLICATE_ZIP_ENTRY")
        if not {"WHD/WHD.exe", "WHD/BUILD_SOURCE.txt", "WHD/本次更新.md"} <= set(names):
            raise ValueError("BACKFILL_REQUIRED_CONTENT_MISSING")
        source = src.read("WHD/BUILD_SOURCE.txt").decode("utf-8-sig")
        if sha not in source:
            raise ValueError("BACKFILL_WRONG_EXE_SOURCE_SHA")
        for entry in entries:
            name = entry.filename.replace("\\", "/")
            if not name.startswith("WHD/") or ".." in name.split("/"):
                raise ValueError("BACKFILL_UNSAFE_ARCHIVE_ENTRY")
            original_bytes = src.read(entry)
            payload = replacements.get(name, original_bytes)
            dst.writestr(entry, payload)
            if name != "WHD/本次更新.md":
                files[name] = hashlib.sha256(original_bytes).hexdigest()
    with zipfile.ZipFile(target) as result:
        if result.testzip() is not None:
            raise ValueError("BACKFILL_NEW_ZIP_CRC_ERROR")
        if result.read("WHD/本次更新.md") != data:
            raise ValueError("BACKFILL_NEW_NOTES_MISMATCH")
        for name, digest in files.items():
            if hashlib.sha256(result.read(name)).hexdigest() != digest:
                raise ValueError(f"BACKFILL_UNEXPECTED_FILE_CHANGE:{name}")
    notes_file = output_dir / "WHD_Release_Notes_zh-TW.md"
    notes_file.write_bytes(data)
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    (output_dir / "SHA256.txt").write_text(
        f"{digest}  {target.name}\n", encoding="ascii"
    )
    return target, notes_file


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--old", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--notes", type=Path, required=True)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--sha", required=True)
    args = parser.parse_args()
    notes = read_release_body(args.notes, tag=args.tag, sha=args.sha)
    archive, body_file = repack(args.old, args.out, tag=args.tag, sha=args.sha, body=notes)
    print(f"RELEASE_NOTES_REPACKED {archive.name} {body_file.name} sha={args.sha}")


if __name__ == "__main__":
    main()
