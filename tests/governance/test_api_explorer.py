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


def test_pages_first_deploy_is_not_blocked_by_unauthenticated_probe():
    workflow = (Path(__file__).resolve().parents[2] / ".github/workflows/whd-api-explorer.yml").read_text(encoding="utf-8")
    assert "uses: actions/upload-pages-artifact@v3" in workflow
    assert "uses: actions/deploy-pages@v4" in workflow
    assert "needs: build" in workflow
    assert "pages_enabled" not in workflow
    assert "api.github.com/repos/" not in workflow


def test_integration_category_uses_full_callable_paths_not_bare_module_name(tmp_path):
    """Both real integration callables appear under the integration filter."""
    _source_tree(tmp_path)
    _write(tmp_path, "ae_engine/integration_api.py",
           (tmp_path / "ae_engine/integration_api.py").read_text(encoding="utf-8")
           + "\ndef export_verified_resolved_integration_bays(bays, output_dir, *, pre_commit_guard):\n"
           + '    """Already-resolved Receiving physical parts only."""\n'
           + "    return ()\n")
    _write(tmp_path, "ae_engine/__init__.py",
           "__all__ = ['dispatch_manufacturing_integration', "
           "'export_verified_resolved_integration_bays']\n"
           "from .integration_api import (dispatch_manufacturing_integration, "
           "export_verified_resolved_integration_bays)\n")
    markdown, html, rows = generate(tmp_path)
    integration = [row for row in rows if row["category"] == "integration"]
    assert {row["name"] for row in integration} == {
        "dispatch_manufacturing_integration",
        "export_verified_resolved_integration_bays",
    }
    assert all(
        any(path.startswith("ae_engine.integration_api.") for path in row["entrypoints"])
        for row in integration
    )
    assert all("ae_engine." + row["name"] in row["entrypoints"] for row in integration)
    assert "## CADSplit／WHD 整合入口（2）" in markdown
    assert '<option value="integration">CADSplit／WHD 整合入口</option>' in html
    assert html.count('"category": "integration"') == 2
    assert next(row for row in rows if row["name"] == "describe_source")["category"] == "view"


def test_real_engine_integration_callables_are_not_missing_from_catalog():
    from tools.build_api_explorer import ROOT

    rows = find_public_api(ROOT)
    integration = {row["name"]: row for row in rows if row["category"] == "integration"}
    assert "dispatch_manufacturing_integration" in integration
    assert "export_verified_resolved_integration_bays" in integration
    for name in ("dispatch_manufacturing_integration", "export_verified_resolved_integration_bays"):
        assert "ae_engine.integration_api." + name in integration[name]["entrypoints"]
        assert integration[name]["source"] == "ae_engine/integration_api.py"


def test_receiving_gui_calls_are_discovered_from_real_ast_without_importing_gui(tmp_path):
    _source_tree(tmp_path)
    _write(tmp_path, "gui_modules/application/receiving_set_bay_adapter.py",
           "from ae_engine import manufacturing_api as engine\n"
           "def update():\n"
           "    return engine.describe_source('P1')\n")
    _write(tmp_path, "gui.py",
           "from ae_engine.manufacturing_api import save_verified_parts as save\n"
           "def export():\n"
           "    return save([], guard=object())\n")
    _write(tmp_path, "phase6_bending_ui.py",
           "import ae_engine.manufacturing_api as mfg\n"
           "def fold():\n"
           "    return mfg.describe_source('fold')\n")
    _write(tmp_path, "gui_modules/application/receiving_unused.py",
           "from ae_engine import manufacturing_api\n"
           "unrelated = manufacturing_api.describe_source\n"
           "from ae_engine.receiving_layout import guessed_internal_part\n"
           "def ignore():\n"
           "    return guessed_internal_part()\n")

    markdown, html, rows = generate(tmp_path)
    by_name = {r["name"]: r for r in rows}
    feature = by_name["describe_source"]
    assert [(s["source"], s["line"], s["scope"]) for s in feature["gui_usage"]] == [
        ("gui_modules/application/receiving_set_bay_adapter.py", 3, "receiving"),
        ("phase6_bending_ui.py", 3, "shared"),
    ]
    assert feature["gui_usage"][0]["link"].endswith(
        "/gui_modules/application/receiving_set_bay_adapter.py#L3"
    )
    assert [s["source"] for s in by_name["save_verified_parts"]["gui_usage"]] == ["gui.py"]
    assert not by_name["dispatch_manufacturing_integration"]["gui_usage"]
    assert "## 受電箱 GUI 直接呼叫的公開 API（1）" in markdown
    assert "gui_modules/application/receiving_set_bay_adapter.py:3" in markdown
    assert 'id="scope"' in html
    assert '"scope": "receiving"' in html
    assert '"scope": "shared"' in html
    assert 'scope.addEventListener("change",draw)' in html


def test_receiving_gui_explorer_does_not_claim_runtime_or_external_certification(tmp_path):
    _source_tree(tmp_path)
    _write(tmp_path, "gui_modules/application/receiving_example.py",
           "from ae_engine import manufacturing_api\n"
           "manufacturing_api.save_verified_parts([], guard=None)\n")
    markdown, html, rows = generate(tmp_path)
    assert len(rows) == 3
    assert "靜態呼叫" in markdown
    assert "靜態呼叫" in html
    assert "非製造認證" in html
    assert "HTTP／Swagger" in html
    assert "製造資格" in markdown


def test_gui_change_triggers_existing_pages_workflow():
    workflow = (Path(__file__).resolve().parents[2] / ".github/workflows/whd-api-explorer.yml").read_text(encoding="utf-8")
    for trigger in ("gui.py", "fold_designer_bridge.py", "phase6_*.py", "gui_modules/**"):
        assert workflow.count("'" + trigger + "'") >= 2
    assert "branches: [localX]" in workflow
    assert "actions/deploy-pages@v4" in workflow


def test_real_receiving_gui_calls_are_in_live_public_catalog():
    from tools.build_api_explorer import ROOT

    _, _, rows = generate(ROOT)
    matched = {
        r["name"] for r in rows
        if any(site["scope"] == "receiving" for site in r["gui_usage"])
    }
    assert "rename_receiving_panel" in matched
    assert "apply_receiving_bay_dimensions" in matched
    assert "preview_quantity_inner_door_confirm" in matched
