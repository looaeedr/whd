"""Public API explorer discovers additions without updating a handwritten list."""
from __future__ import annotations

import json
from pathlib import Path

from tools.build_api_explorer import find_public_api, generate, signature


def _write(root: Path, filename: str, content: str) -> None:
    destination = root / filename
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(content, encoding="utf-8")


def _source_tree(tmp_path: Path) -> None:
    _write(tmp_path, "ae_engine/__init__.py",
           "__all__ = ['dispatch_manufacturing_integration']\n"
           "from .integration_api import dispatch_manufacturing_integration\n")
    _write(tmp_path, "ae_engine/integration_api.py",
           "def dispatch_manufacturing_integration(operation: str) -> str:\n"
           '    """Source only, not manufacturing authorization."""\n'
           "    return operation\n")
    _write(tmp_path, "ae_engine/manufacturing_api.py",
           "from .feature_api import describe_source\n"
           "def save_verified_parts(parts, *, guard, overwrite=False) -> dict:\n"
           '    """Only Engine resolved physical parts."""\n'
           "    return {}\n")
    _write(tmp_path, "ae_engine/feature_api.py",
           "def describe_source(source: str, *, options: tuple[str, ...] = ()) -> dict:\n"
           '    """Read source features."""\n'
           "    return {}\n")


def test_new_public_function_is_auto_discovered_with_signature_and_link(tmp_path):
    _source_tree(tmp_path)
    first = find_public_api(tmp_path)
    assert {v["name"] for v in first} == {
        "dispatch_manufacturing_integration", "save_verified_parts", "describe_source",
    }
    before_markdown, before_html, _ = generate(tmp_path)
    assert "describe_source" in before_markdown
    assert "describe_source" in before_html
    assert "ae_engine/feature_api.py#L1" in before_html
    assert "source: str" in before_html

    _write(tmp_path, "ae_engine/feature_api.py",
           (tmp_path / "ae_engine/feature_api.py").read_text(encoding="utf-8")
           + "\ndef new_manufacturing_api(*, family: str, parts=()) -> tuple:\n"
           + '    """New public Engine operation."""\n'
           + "    return tuple(parts)\n")
    _write(tmp_path, "ae_engine/manufacturing_api.py",
           (tmp_path / "ae_engine/manufacturing_api.py").read_text(encoding="utf-8")
           + "\nfrom .feature_api import new_manufacturing_api\n")

    after_markdown, after_html, rows = generate(tmp_path)
    assert "new_manufacturing_api" not in before_markdown
    assert "new_manufacturing_api" in after_markdown
    assert "new_manufacturing_api" in after_html
    new = next(row for row in rows if row["name"] == "new_manufacturing_api")
    assert new["entrypoints"] == ["ae_engine.manufacturing_api.new_manufacturing_api"]
    assert new["signature"] == "new_manufacturing_api(*, family: str, parts=()) -> tuple"
    assert new["source"] == "ae_engine/feature_api.py"


def test_private_internal_helper_does_not_appear_and_no_module_imports(tmp_path):
    _source_tree(tmp_path)
    _write(tmp_path, "ae_engine/feature_api.py",
           (tmp_path / "ae_engine/feature_api.py").read_text(encoding="utf-8")
           + "\ndef _internal_unsafe_derive_geometry(x):\n"
           + "    raise RuntimeError('do not execute in API indexing')\n")
    markdown, html, rows = generate(tmp_path)
    assert "_internal_unsafe_derive_geometry" not in markdown
    assert "_internal_unsafe_derive_geometry" not in html
    assert all(not row["name"].startswith("_") for row in rows)
    assert "Source only, not manufacturing authorization" in markdown
    assert "同程序" in markdown
    assert "WHD API" in html


def test_generated_output_is_deterministic_and_json_embedded(tmp_path):
    _source_tree(tmp_path)
    a_md, a_html, rows = generate(tmp_path)
    b_md, b_html, others = generate(tmp_path)
    assert (a_md, a_html, rows) == (b_md, b_html, others)
    assert "const rows = [" in a_html
    assert "CAT_OPTIONS" not in a_html
    assert "API_DATA" not in a_html
    assert "search.addEventListener" in a_html
    assert all(row["link"].startswith("https://github.com/looaeedr/whd/") for row in rows)
