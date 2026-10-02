CI_PREFIXES = (
    ".github/workflows/qa-issue30",
    ".github/workflows/qa-issue31",
    "tools/test_shard_",
    "tools/xvfb_shard_",
    "tools/issue311_t7_",
    "tools/issue312_t8_",
    "tests/test_issue3",
    "docs/superpowers/",
    ".agents/skills/engineering/",
    "個人AI檔案庫/",
)


def classify_path(path: str) -> str:
    return "CI_OR_EVIDENCE" if path.startswith(CI_PREFIXES) else "PRODUCTION_SOURCE"
