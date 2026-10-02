from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
SOP = ROOT / "個人AI檔案庫/第二層_專案與SOP"
DUPLICATE_PREFIXES = {"07", "08", "09", "11", "12"}


def _frontmatter_value(path: Path, key: str) -> str | None:
    lines = path.read_text(encoding="utf-8").lstrip("\ufeff").splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if line.startswith(key + ":"):
            return line.split(":", 1)[1].strip().strip('"').strip("'")
    return None


def test_duplicate_numeric_sop_prefixes_have_unique_stable_doc_ids():
    selected = []
    for path in SOP.glob("*.md"):
        m = re.match(r"^(\d{2})_", path.name)
        if m and m.group(1) in DUPLICATE_PREFIXES:
            selected.append(path)
    ids = {}
    for path in selected:
        doc_id = _frontmatter_value(path, "whd_doc_id")
        assert doc_id, path
        assert doc_id not in ids, (doc_id, ids.get(doc_id), path)
        ids[doc_id] = path
    for prefix in DUPLICATE_PREFIXES:
        members = [p for p in selected if p.name.startswith(prefix + "_")]
        assert len(members) >= 2, prefix
