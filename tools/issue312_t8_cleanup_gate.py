class CleanupGateError(RuntimeError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def compute_safe_deletions(
    candidates: set[str], open_pr_refs: set[str], evidence_secured: bool
) -> dict:
    if not evidence_secured:
        raise CleanupGateError("CLEANUP_BEFORE_EVIDENCE")
    protected = sorted(candidates & open_pr_refs)
    safe = sorted(candidates - open_pr_refs)
    return {"safe": safe, "protected": protected}
