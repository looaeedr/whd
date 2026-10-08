"""Regression tests for fail-closed native issue-bound PR admission."""
from datetime import datetime, timedelta, timezone
import unittest
from tools.flow_v2_delivery_entry_gate import DeliveryEntryError, validate_pr_entry

NOW = datetime(2026, 10, 8, 16, 0, tzinfo=timezone.utc)
SHA = 'a' * 40
REPO = 'looaeedr/whd'


def pr():
    return {
        'head': {'ref': 'work/issue-1431-flow-v2-entry-gate', 'sha': SHA, 'repo': {'full_name': REPO}},
        'base': {'ref': 'cleanup/2d-3d-sync'},
        'title': 'Flow v2 delivery gate', 'body': 'Closes #1431',
    }


def acquired():
    return {
        'schema': 'WHD_EXECUTION_RECORD_V2', 'issue': 1431, 'state': 'ACTIVE',
        'owner_kind': 'SCHEDULER', 'owner_id': 'chatgpt.flowv2.work1',
        'lane_id': 'chatgpt.flowv2.work1', 'slot_id': 'worker.slot.1',
        'work_branch': 'work/issue-1431-flow-v2-entry-gate', 'head_sha': SHA,
        'target_branch': 'cleanup/2d-3d-sync',
        'lease': {'token': 'trusted-native-lease', 'invocation_identity': 'test-invocation',
                  'expires_at': (NOW + timedelta(hours=1)).isoformat()},
        'mutation_scope': {'target_branch': 'cleanup/2d-3d-sync', 'base_sha': 'b'*40,
                           'write_paths': ['tools/flow_v2_delivery_entry_gate.py'],
                           'delete_paths': [], 'reservation_state': 'ACTIVE'},
        'transaction': {'kind': 'APPLY_COMMIT', 'status': 'RECONCILED',
                        'invocation_identity': 'test-invocation'},
    }


class NativeDeliveryEntryTests(unittest.TestCase):
    def expect_failure(self, code, request=None, record=None):
        with self.assertRaisesRegex(DeliveryEntryError, code):
            validate_pr_entry(request or pr(), record, repository=REPO, now=NOW)

    def test_missing_record_denied(self):
        self.expect_failure('NATIVE_EXECUTION_RECORD_REQUIRED')

    def test_ready_unclaimed_denied(self):
        rec = acquired(); rec['state'] = 'READY'
        self.expect_failure('NATIVE_ACQUIRE_REQUIRED', record=rec)

    def test_owner_mismatch_denied(self):
        rec = acquired(); rec['owner_id'] = 'chatgpt.flowv2.work0'
        self.expect_failure('NATIVE_OWNER_LANE_MISMATCH', record=rec)

    def test_expired_lease_denied(self):
        rec = acquired(); rec['lease']['expires_at'] = (NOW - timedelta(seconds=1)).isoformat()
        self.expect_failure('NATIVE_LEASE_EXPIRED', record=rec)

    def test_invocation_mismatch_denied(self):
        rec = acquired(); rec['transaction']['invocation_identity'] = 'foreign-invocation'
        self.expect_failure('NATIVE_TRANSACTION_INVOCATION_MISMATCH', record=rec)

    def test_preflight_or_comment_is_not_acquire(self):
        rec = acquired(); rec['state'] = 'READY'; rec['preflight'] = 'GREEN'; rec['issue_comment'] = 'ACQUIRED'
        self.expect_failure('NATIVE_ACQUIRE_REQUIRED', record=rec)

    def test_missing_delivery_reservation_denied(self):
        rec = acquired(); rec['mutation_scope'] = None
        self.expect_failure('NATIVE_DELIVERY_RESERVATION_REQUIRED', record=rec)

    def test_stale_head_denied(self):
        rec = acquired(); rec['head_sha'] = 'c'*40
        self.expect_failure('NATIVE_HEAD_SHA_MISMATCH', record=rec)

    def test_wrong_branch_denied(self):
        rec = acquired(); rec['work_branch'] = 'work/issue-1430-wrong'
        self.expect_failure('NATIVE_WORK_BRANCH_MISMATCH', record=rec)

    def test_fork_claim_denied(self):
        req = pr(); req['head']['repo']['full_name'] = 'other/whd'
        self.expect_failure('PR_HEAD_REPOSITORY_MISMATCH', request=req, record=acquired())

    def test_multi_issue_ambiguous_denied(self):
        req = pr(); req['body'] = 'Closes #1431, fixes #1430'
        self.expect_failure('ISSUE_BOUND_PR_AMBIGUOUS_ISSUES', request=req, record=acquired())

    def test_legitimate_acquired_delivery_allowed(self):
        out = validate_pr_entry(pr(), acquired(), repository=REPO, now=NOW)
        self.assertEqual(out['status'], 'GREEN')

    def test_unrelated_product_pr_is_unaffected(self):
        req = pr(); req['head']['ref'] = 'feature/product-view'; req['body'] = 'Improve drawing'; req['title'] = 'Product improvement'
        out = validate_pr_entry(req, None, repository=REPO, now=NOW)
        self.assertEqual(out['status'], 'SKIPPED')

    def test_closing_keyword_without_issue_branch_still_requires_record(self):
        req = pr(); req['head']['ref'] = 'feature/box'; req['body'] = 'Fixes #1431'
        self.expect_failure('NATIVE_EXECUTION_RECORD_REQUIRED', request=req)

if __name__ == '__main__':
    unittest.main()
