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


if __name__ == "__main__":
    unittest.main()
