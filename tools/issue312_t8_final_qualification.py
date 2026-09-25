from __future__ import annotations


ACCEPTED_T7_SHA = "db0b79cd767717e67bcb65c8bd1f0e8eed6b2b4f"


class QualificationError(RuntimeError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def validate_final_qualification(payload: dict) -> dict:
    if (
        payload["accepted_t7_sha"] != ACCEPTED_T7_SHA
        or payload["tested_sha"] != ACCEPTED_T7_SHA
    ):
        raise QualificationError("T7_SHA_MISMATCH")

    collection = payload["collection"]
    if collection["missing"]:
        raise QualificationError("MISSING_NODES")
    if collection["extra"]:
        raise QualificationError("EXTRA_NODES")
    if collection["duplicate"]:
        raise QualificationError("DUPLICATE_NODES")
    if collection["full"] != collection["unique_executed"]:
        raise QualificationError("COLLECTION_EXECUTION_MISMATCH")

    if payload["results"]["unclassified_red"]:
        raise QualificationError("UNCLASSIFIED_RED")
    if payload["protected_drift"]:
        raise QualificationError("PROTECTED_DRIFT")

    production = payload["production"]
    if production["mutated"]:
        raise QualificationError("PRODUCTION_MUTATION")
    if not production["drift_audit_complete"]:
        raise QualificationError("DRIFT_AUDIT_INCOMPLETE")
    if not production["integration_shape_qualified"]:
        raise QualificationError("INTEGRATION_SHAPE_UNQUALIFIED")

    cleanup = payload["cleanup"]
    if not cleanup["evidence_secured"]:
        raise QualificationError("CLEANUP_BEFORE_EVIDENCE")
    if not cleanup["open_pr_refs_checked"]:
        raise QualificationError("OPEN_PR_REF_GATE_NOT_RUN")
    if cleanup["deleted_live_pr_refs"]:
        raise QualificationError("LIVE_PR_REF_DELETED")

    durable_rules = payload["durable_rules"]
    if not durable_rules["updated"] or not durable_rules["readback_verified"]:
        raise QualificationError("DURABLE_RULE_READBACK_MISSING")

    if payload["final_state"] != "QUALIFIED_FOR_INTEGRATION":
        raise QualificationError("INVALID_FINAL_STATE")

    return {"decision": "GREEN", **payload}
