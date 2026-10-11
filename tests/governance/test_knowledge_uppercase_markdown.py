"""Regression: governed uppercase .MD files must not escape authority scans."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools import knowledge_governance


class UppercaseMarkdownGovernanceTests(unittest.TestCase):
    def test_uppercase_markdown_is_in_inventory(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            doc = root / "GUI.MD"
            doc.write_text(
                "---\n"
                "whd_doc_role: REFERENCE\n"
                "whd_contract: uppercase-markdown-reference\n"
                "whd_canonical: null\n"
                "whd_schema: WHD_DOC_META_V1\n"
                "---\n"
                "# Legacy reference\n",
                encoding="utf-8",
            )
            self.assertTrue(knowledge_governance.is_governed_markdown("GUI.MD"))
            inventory = knowledge_governance.build_inventory(root, source_head="test-head")
            self.assertIn("GUI.MD", {row["path"] for row in inventory["rows"]})

    def test_uppercase_markdown_without_metadata_fails_strict(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "說明.MD").write_text("# Legacy without metadata\n", encoding="utf-8")
            errors = knowledge_governance.validate_strict(root)
            self.assertTrue(any("說明.MD" in error and "missing" in error for error in errors), errors)


class CurrentSpecAuthorityCoverageTests(unittest.TestCase):
    """Keep distinct existing CURRENT specs mapped without changing their rules."""

    def test_current_spec_contracts_are_registered_once(self) -> None:
        root = Path(__file__).resolve().parents[2]
        authority = (root / "個人AI檔案庫/第二層_專案與SOP/09_WHD_Canonical_Authority_Map.md").read_text(encoding="utf-8")
        owners = {
            "receiving-inner-door-frame-physical-mating": "docs/receiving-inner-door-frame-mating-contract.md",
            "assembly-joint-placement-marking": "docs/superpowers/specs/2026-09-21-joint-placement-marking-design.md",
            "ci-test-sharding-parallelization-design": "docs/superpowers/specs/2026-09-16-ci-test-sharding-parallelization-design.md",
        }
        for contract, path in owners.items():
            metadata = knowledge_governance.parse_doc_metadata(
                (root / path).read_text(encoding="utf-8-sig"), path=path
            )
            self.assertEqual((metadata.role, metadata.contract), ("CURRENT", contract))
            marker = f"<!-- WHD_AUTHORITY contract={contract} role=CURRENT path={path} -->"
            self.assertEqual(authority.count(marker), 1, (contract, path))
            self.assertEqual(authority.count(f"WHD_AUTHORITY contract={contract} role=CURRENT "), 1)


if __name__ == "__main__":
    unittest.main()
