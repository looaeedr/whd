# -*- coding: utf-8 -*-
"""Phase 3 T4 registry / diagnostics application controller.

Owns candidate lifecycle, registry command ordering, diagnostic selection, and
presentation-ready diagnostic status. Domain registry backends and 3D solvers
are injected by callers; this module must not become a manufacturing solver.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Mapping


class Phase6RegistryDiagnosticsController:
    def __init__(
        self,
        *,
        candidate_id="",
        candidate_record=None,
        regression_evidence=None,
        rule_records=None,
        promotion_candidates=None,
    ) -> None:
        self._candidate_id = str(candidate_id or "")
        self._candidate_record = deepcopy(dict(candidate_record or {}))
        self._regression_evidence = deepcopy(dict(regression_evidence or {}))
        self._rule_records = {
            str(key): deepcopy(dict(value or {}))
            for key, value in dict(rule_records or {}).items()
        }
        self._promotion_candidates = deepcopy(dict(promotion_candidates or {}))

    @property
    def candidate_id(self) -> str:
        return str(self._candidate_id or "")

    @property
    def candidate_record(self) -> dict:
        return deepcopy(self._candidate_record)

    @property
    def regression_evidence(self) -> dict:
        return deepcopy(self._regression_evidence)

    @property
    def rule_records(self) -> dict:
        return deepcopy(self._rule_records)

    @property
    def promotion_candidates(self) -> dict:
        return deepcopy(self._promotion_candidates)

    def validate_formula(self, record, variables, *, validator, evaluator):
        raw = validator(record)
        return evaluator(raw, variables)

    def candidate_is_current(self, current_record) -> bool:
        if not self._candidate_id or not self._candidate_record:
            return False
        try:
            current = deepcopy(dict(current_record or {}))
        except Exception:
            return False
        return current == deepcopy(self._candidate_record)

    def require_current_candidate(self, current_record) -> str:
        candidate_id = self.candidate_id
        if not candidate_id:
            raise ValueError("請先儲存候選")
        if not self.candidate_is_current(current_record):
            raise ValueError("表單已變更；請重新儲存候選後再驗證")
        return candidate_id

    def save_candidate(self, record, *, saver):
        item = saver(deepcopy(dict(record or {})))
        candidate_id = str(item["candidate_id"])
        self._candidate_id = candidate_id
        self._candidate_record = deepcopy(dict(record or {}))
        self._regression_evidence = {"candidate_id": candidate_id}
        return item

    def run_formula_matrix(
        self,
        current_record,
        base_variables,
        *,
        validator,
        evaluator,
    ) -> dict:
        candidate_id = self.require_current_candidate(current_record)
        raw = validator(current_record)
        base = dict(base_variables or {})
        samples = []
        for t in (max(0.5, base["T"] * 0.75), base["T"], base["T"] * 1.25):
            for fw in (
                max(t * 2, base["FW"] * 0.8),
                base["FW"],
                base["FW"] * 1.2,
            ):
                variables = dict(base, T=t, FW=fw)
                evaluator(raw, variables)
                samples.append(variables)
        evidence = dict(self._regression_evidence)
        evidence.update({
            "matrix_passed": True,
            "cases": len(samples),
            "candidate_id": candidate_id,
        })
        self._regression_evidence = evidence
        return deepcopy(evidence)

    def merge_3d_evidence(self, evidence3d) -> dict:
        evidence = dict(self._regression_evidence)
        evidence.update(deepcopy(dict(evidence3d or {})))
        self._regression_evidence = evidence
        return deepcopy(evidence)

    def promote_candidate(self, current_record, *, promoter):
        candidate_id = self.require_current_candidate(current_record)
        return promoter(
            candidate_id,
            regression_evidence=deepcopy(self._regression_evidence),
        )

    def load_rule_records(self, *, loader):
        rows = list(loader() or ())
        self._rule_records = {
            f"{row['rule_id']}@{row['revision']}": deepcopy(dict(row))
            for row in rows
        }
        return deepcopy(rows)

    def rule_record(self, key) -> dict:
        return deepcopy(dict(self._rule_records.get(str(key), {}) or {}))

    @staticmethod
    def route_joint_add(callback, **kwargs):
        return callback(**kwargs)

    @staticmethod
    def route_joint_delete(callback, joint_id):
        return callback(joint_id)

    def build_promotion_candidates(
        self,
        *,
        solutions,
        snapshot,
        assembly_intent,
        cabinet_family,
        builder,
    ) -> dict:
        candidates = {}
        for part_key in ("head", "tail"):
            solution = dict(solutions or {}).get(part_key)
            if solution is None:
                continue
            if not bool(getattr(solution, "verified", False)):
                continue
            if str(getattr(solution, "trust_level", "") or "") != "PROVISIONAL_3D":
                continue
            candidates[part_key] = builder(
                solution,
                cabinet_family=cabinet_family,
                part_role=part_key,
                joint_face="TOP",
                assembly_intent=assembly_intent,
                source_signature=dict(snapshot or {}),
            )
        self._promotion_candidates = deepcopy(candidates)
        return deepcopy(candidates)

    @staticmethod
    def diagnostic_ids(resolved) -> tuple[str, ...]:
        diagnostics = (
            tuple(getattr(resolved, "diagnostics", ()) or ())
            if resolved is not None
            else ()
        )
        return tuple(
            str(getattr(item, "joint_id", ""))
            for item in diagnostics
            if str(getattr(item, "joint_id", ""))
        )

    @staticmethod
    def selected_diagnostic(resolved, joint_id):
        if resolved is None or not str(joint_id or ""):
            return None
        try:
            return resolved.joint_diagnostic(str(joint_id))
        except Exception:
            return None

    @staticmethod
    def diagnostic_status(
        *,
        fallback_enabled: bool,
        solutions,
        errors,
        measurement_text,
    ) -> tuple[str, str]:
        solutions = dict(solutions or {})
        errors = dict(errors or {})
        labels = {"head": "封頭", "tail": "封尾"}

        if not fallback_enabled and not solutions:
            return (
                "實際截角尺寸：等待資料庫查詢",
                "截角來源：已認證規則優先；未知組合的立體備援已停用",
            )

        if solutions:
            size_parts = []
            verify_parts = []
            for key in ("head", "tail"):
                solution = solutions.get(key)
                if solution is None:
                    continue
                measurements = [
                    getattr(item, "measurement", None)
                    for item in tuple(getattr(solution, "corner_reliefs", ()) or ())
                ]
                texts = []
                for measurement in (m for m in measurements if m is not None):
                    text = measurement_text(measurement)
                    if text not in texts:
                        texts.append(text)
                if texts:
                    size_parts.append(
                        f"{labels.get(key, key)}：{' / '.join(texts)}"
                    )
                verify_parts.append(
                    f"{labels.get(key, key)}"
                    f"{'✓' if bool(getattr(solution, 'verified', False)) else '✗'}"
                )
            size_text = (
                "實際截角尺寸："
                + ("；".join(size_parts) if size_parts else "無需截角")
            )
            if errors:
                detail = "；".join(
                    f"{labels.get(k, k)}：{v}" for k, v in errors.items()
                )
                status_text = (
                    "3D驗證：" + " ".join(verify_parts) + f"（{detail}）"
                )
            elif verify_parts and all(
                bool(getattr(solutions[k], "verified", False))
                for k in solutions
            ):
                status_text = (
                    "3D驗證：" + " ".join(verify_parts) + "（零材料穿透）"
                )
            else:
                status_text = "3D驗證：" + " ".join(verify_parts)
            return size_text, status_text

        if errors:
            detail = "；".join(
                f"{labels.get(k, k)}：{v}" for k, v in errors.items()
            )
            return "實際截角尺寸：求解失敗", f"3D驗證：{detail}"

        return "實際截角尺寸：等待計算", "3D驗證：等待計算"
