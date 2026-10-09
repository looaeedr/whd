"""#1439: TOK authenticates only SYNC_TARGET PR work-branch writes, never CAS."""
import io
import json
import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch, call
from urllib.error import HTTPError

from tools import control_transaction_production_executor as ex


class Issue1439TokIdentityTests(unittest.TestCase):
    def test_missing_tok_fails_closed_without_io(self):
        with patch.dict(os.environ, {"WHD_PR_BRANCH_WRITE_TOKEN": ""}), patch.object(ex, "urlopen") as opener:
            with self.assertRaisesRegex(ex.ProductionExecutorError, "SYNC_TARGET_TOK_MISSING"):
                ex._verified_sync_target_user_token("looaeedr/whd")
            opener.assert_not_called()

    def test_real_owner_user_identity_allowed(self):
        payload = io.BytesIO(json.dumps({"login": "looaeedr", "type": "User"}).encode())
        with patch.dict(os.environ, {"WHD_PR_BRANCH_WRITE_TOKEN": "unit-test-fake-pat"}), patch.object(ex, "urlopen", return_value=payload) as opener:
            self.assertEqual(ex._verified_sync_target_user_token("looaeedr/whd"), "unit-test-fake-pat")
            request = opener.call_args.args[0]
            self.assertEqual(request.full_url, "https://api.github.com/user")
            self.assertIn("unit-test-fake-pat", request.get_header("Authorization"))

    def test_bot_token_cannot_fall_back_to_app(self):
        payload = io.BytesIO(json.dumps({"login": "github-actions[bot]", "type": "Bot"}).encode())
        with patch.dict(os.environ, {"WHD_PR_BRANCH_WRITE_TOKEN": "unit-test-fake-bot"}), patch.object(ex, "urlopen", return_value=payload):
            with self.assertRaisesRegex(ex.ProductionExecutorError, "SYNC_TARGET_TOK_IDENTITY_MISMATCH") as error:
                ex._verified_sync_target_user_token("looaeedr/whd")
            self.assertNotIn("unit-test-fake-bot", str(error.exception))

    def test_wrong_user_cannot_trigger_branch_mutation(self):
        payload = io.BytesIO(json.dumps({"login": "someone-else", "type": "User"}).encode())
        with patch.dict(os.environ, {"WHD_PR_BRANCH_WRITE_TOKEN": "unit-test-fake-token"}), patch.object(ex, "urlopen", return_value=payload):
            with self.assertRaisesRegex(ex.ProductionExecutorError, "SYNC_TARGET_TOK_IDENTITY_MISMATCH"):
                ex._verified_sync_target_user_token("looaeedr/whd")

    def test_rejected_token_does_not_echo_sensitive_http_response(self):
        problem = HTTPError("https://api.github.com/user", 403, "unit-test-fake-token-secret", {}, None)
        with patch.dict(os.environ, {"WHD_PR_BRANCH_WRITE_TOKEN": "unit-test-fake-token-secret"}), patch.object(ex, "urlopen", side_effect=problem):
            with self.assertRaisesRegex(ex.ProductionExecutorError, "SYNC_TARGET_TOK_IDENTITY_REJECTED") as err:
                ex._verified_sync_target_user_token("looaeedr/whd")
            self.assertNotIn("unit-test-fake-token-secret", str(err.exception))

    def test_sync_branch_write_uses_pat_while_reads_use_app(self):
        record = SimpleNamespace(
            issue=1439, target_branch="cleanup/2d-3d-sync", work_branch="work/issue-1439-tok-ci-identity",
            head_sha="old-head", next_action=SimpleNamespace(
                kind="SYNC_TARGET", args={
                    "target_sha": "target-head", "target_branch": "cleanup/2d-3d-sync",
                    "qa_workflow": ".github/workflows/whd-product-regression.yml", "pr_number": 1440,
                },
            ),
        )
        with patch.object(ex, "_require_current_invocation_lease"), \
             patch.object(ex, "_read_branch_head", side_effect=["target-head", "old-head", "new-head"]) as reads, \
             patch.object(ex, "_verified_sync_target_user_token", return_value="unit-test-owner-token"), \
             patch.object(ex, "_api", return_value={}) as api:
            evidence = ex._trusted_sync_target_effect("looaeedr/whd", "unit-test-app-token",
                record=record, invocation_identity="unit-invocation")
        self.assertEqual(evidence["head_sha"], "new-head")
        self.assertEqual(evidence["next_action"]["kind"], "START_QA")
        self.assertEqual(reads.call_args_list, [
            call("looaeedr/whd", "unit-test-app-token", "cleanup/2d-3d-sync"),
            call("looaeedr/whd", "unit-test-app-token", "work/issue-1439-tok-ci-identity"),
            call("looaeedr/whd", "unit-test-app-token", "work/issue-1439-tok-ci-identity"),
        ])
        self.assertEqual(api.call_args.args[3], "unit-test-owner-token")

    def test_existing_reconciled_merge_does_not_need_pat(self):
        record = SimpleNamespace(
            issue=1439, target_branch="cleanup/2d-3d-sync", work_branch="work/issue-1439-tok-ci-identity",
            head_sha="old", next_action=SimpleNamespace(
                kind="SYNC_TARGET", args={
                    "target_sha": "target", "target_branch": "cleanup/2d-3d-sync",
                    "qa_workflow": "product.yml", "pr_number": 1440,
                },
            ),
        )
        with patch.object(ex, "_require_current_invocation_lease"), \
             patch.object(ex, "_read_branch_head", side_effect=["target", "advanced"]) as reads, \
             patch.object(ex, "_is_ancestor", return_value=True), \
             patch.object(ex, "_verified_sync_target_user_token") as identity, \
             patch.object(ex, "_api") as api:
            evidence = ex._trusted_sync_target_effect("looaeedr/whd", "unit-test-app-token",
                record=record, invocation_identity="unit-invocation")
            identity.assert_not_called()
            api.assert_not_called()
            self.assertEqual(evidence["head_sha"], "advanced")
            self.assertEqual(reads.call_count, 2)



class Issue1439RealPrQaTests(unittest.TestCase):
    @staticmethod
    def _record():
        return SimpleNamespace(
            head_sha="a" * 40,
            next_action=SimpleNamespace(kind="START_QA", args={
                "workflow": ".github/workflows/whd-control-plane-regression.yml",
            }),
        )

    @staticmethod
    def _run(conclusion="success"):
        return {
            "id": 1439001, "head_sha": "a" * 40,
            "path": ".github/workflows/whd-control-plane-regression.yml",
            "status": "completed", "conclusion": conclusion,
            "event": "pull_request",
        }

    @staticmethod
    def _jobs(total=1, conclusion="success"):
        return {"total_count": total, "jobs": [
            {"run_id": 1439001, "status": "completed", "conclusion": conclusion}
        ] if total else []}

    def _consume(self, jobs, *, run=None):
        payloads = [run or self._run(), jobs]
        with patch.object(ex, "_require_current_invocation_lease"), patch.object(
            ex, "_api", side_effect=payloads
        ) as api:
            result = ex._trusted_consume_qa_effect(
                "looaeedr/whd", "app-token",
                record=self._record(), invocation_identity="unit-invocation",
                supplied={"run_id": 1439001},
            )
        self.assertEqual(api.call_count, 2)
        return result

    def test_real_pr_run_success_requires_real_green_job(self):
        self.assertEqual(self._consume(self._jobs())["conclusion"], "success")

    def test_real_pr_run_with_zero_jobs_is_rejected(self):
        with self.assertRaisesRegex(ex.ControlTransactionConflict, "CONSUME_QA_PR_JOBS_NOT_GREEN"):
            self._consume(self._jobs(total=0))

    def test_real_pr_run_with_failed_job_is_rejected(self):
        with self.assertRaisesRegex(ex.ControlTransactionConflict, "CONSUME_QA_PR_JOBS_NOT_GREEN"):
            self._consume(self._jobs(conclusion="failure"))

    def test_real_pr_run_with_skipped_job_is_rejected(self):
        with self.assertRaisesRegex(ex.ControlTransactionConflict, "CONSUME_QA_PR_JOBS_NOT_GREEN"):
            self._consume(self._jobs(conclusion="skipped"))

    def test_real_pr_run_with_incomplete_job_set_is_rejected(self):
        with self.assertRaisesRegex(ex.ControlTransactionConflict, "CONSUME_QA_PR_JOBS_NOT_GREEN"):
            self._consume(self._jobs(total=2))

    def test_real_pr_action_required_is_rejected_even_without_job_lookup(self):
        with patch.object(ex, "_require_current_invocation_lease"), patch.object(
            ex, "_api", return_value=self._run("action_required")
        ) as api, self.assertRaisesRegex(ex.ControlTransactionConflict, "CONSUME_QA requires success"):
            ex._trusted_consume_qa_effect("looaeedr/whd", "app-token",
                record=self._record(), invocation_identity="unit-invocation",
                supplied={"run_id": 1439001})
        self.assertEqual(api.call_count, 1)

    def test_workflow_keeps_user_token_separate_from_control_plane_app_token(self):
        from pathlib import Path
        workflow = Path(__file__).resolve().parents[2] / ".github/workflows/whd-control-transaction-v2-request.yml"
        content = workflow.read_text(encoding="utf-8")
        self.assertIn("GITHUB_TOKEN: " + chr(36) + "{{ steps.app-token.outputs.token }}", content)
        self.assertIn("WHD_PR_BRANCH_WRITE_TOKEN: " + chr(36) + "{{ secrets.TOK }}", content)
        self.assertNotIn("WHD_PR_BRANCH_WRITE_TOKEN: " + chr(36) + "{{ steps.app-token.outputs.token }}", content)


if __name__ == "__main__":
    unittest.main()
