"""Explicit /推推 remains the only allowed production X publish approval."""
import unittest
from tools.localx_publish_gate import (
    require_publish_approval, LocalXPublishDenied,
    require_conversational_bugfix_localx_integration, require_github_localx_integration, LocalXIntegrationDenied,
    official_release_tag, require_official_release_proof, OfficialReleaseDenied,
)

class PublishGateTests(unittest.TestCase):
    def _approval(self, *, head="a"*40, base="b"*40,
                  owner="looaeedr", marker="WHD_LOCALX_PUBLISH_AUTH_V1",
                  command="/推推", comment_id=101):
        fields = ("repo=looaeedr/whd\npr=12\nsource=localX\n"
                  + "head=" + head + "\ntarget=cleanup/2d-3d-sync\n"
                  + "base=" + base)
        return [{"id": comment_id,
                 "user": {"login": owner, "type": "User"},
                 "body": command + "\n" + marker + "\n" + fields}]

    def _publish(self, comments):
        return require_publish_approval(
            repo="looaeedr/whd", pr_number=12,
            pr={"head":{"ref":"localX","sha":"a"*40},
                "base":{"ref":"cleanup/2d-3d-sync","sha":"b"*40}},
            head_sha="a"*40, target_sha="b"*40, comments=comments)

    def test_absent_owner_push_is_denied(self):
        with self.assertRaisesRegex(LocalXPublishDenied, "EXPLICIT_USER_SLASH_PUSH"):
            self._publish([])

    def test_slash_push_itself_is_release_acceptance(self):
        # No second /驗收通過 or fictional test_site=WINDOWS claim.
        self._publish(self._approval())

    def test_historical_windows_acceptance_is_optional(self):
        historical = {"id": 100, "user": {"login": "looaeedr", "type": "User"},
                      "body": "/驗收通過\nWHD_WINDOWS_LOCALX_UAT_V1"}
        with self.assertRaises(LocalXPublishDenied):
            self._publish([historical])
        self._publish([historical] + self._approval())

    def test_wrong_owner_sha_target_command_or_marker_is_denied(self):
        for mutation in (
            {"owner": "github-actions[bot]"}, {"head": "f"*40},
            {"base": "f"*40}, {"marker": "WRONG_MARKER"},
            {"command": "/驗收通過"}, {"comment_id": None},
        ):
            with self.subTest(mutation=mutation), self.assertRaises(LocalXPublishDenied):
                self._publish(self._approval(**mutation))

    def test_untrusted_duplicate_fields_and_hidden_extra_lines_rejected(self):
        comment = self._approval()
        comment[0]["body"] += "\nhead=" + "a"*40
        with self.assertRaises(LocalXPublishDenied):
            self._publish(comment)

class ConversationBugfixIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.auth = {
            "source": "AUTHENTICATED_USER_CONVERSATION",
            "intent": "EXECUTE_BUGFIX",
            "instruction_id": "user-turn-bugfix-1",
            "scope": "NFB GUI selection freeze",
            "repo": "looaeedr/whd",
        }
        self.delivery = {
            "repo": "looaeedr/whd", "scope": self.auth["scope"],
            "stage": "LOCALX_INTEGRATION", "pr_base": "localX",
            "work_branch": "fix/nfb-selection",
            "head_sha": "a" * 40, "ci_head_sha": "a" * 40,
            "ci_conclusion": "SUCCESS", "required_tests_complete": True,
        }

    def test_dc_is_never_implicit_in_bugfix_authorization(self):
        with self.assertRaises(LocalXIntegrationDenied):
            require_conversational_bugfix_localx_integration(authorization=self.auth, delivery=self.delivery)
        require_conversational_bugfix_localx_integration(
            authorization=dict(self.auth, dc_explicitly_authorized=True), delivery=self.delivery)

    def test_discussing_a_bug_does_not_grant_dc(self):
        self.auth["intent"] = "DISCUSS_BUG"
        with self.assertRaises(LocalXIntegrationDenied):
            require_conversational_bugfix_localx_integration(
                authorization=self.auth, delivery=self.delivery)

    def test_cross_task_scope_does_not_grant_dc(self):
        self.delivery["scope"] = "different bug"
        with self.assertRaises(LocalXIntegrationDenied):
            require_conversational_bugfix_localx_integration(
                authorization=self.auth, delivery=self.delivery)

    def test_ci_head_must_be_exact_and_successful(self):
        for field, value in (("ci_head_sha", "b" * 40),
                             ("ci_conclusion", "IN_PROGRESS"),
                             ("required_tests_complete", False)):
            item = dict(self.delivery, **{field: value})
            with self.subTest(field=field), self.assertRaises(LocalXIntegrationDenied):
                require_conversational_bugfix_localx_integration(
                    authorization=self.auth, delivery=item)

    def test_explicit_no_dc_or_github_only_cannot_be_overridden(self):
        for field in ("github_only", "dc_forbidden", "revoked"):
            item = dict(self.auth, **{field: True})
            with self.subTest(field=field), self.assertRaises(LocalXIntegrationDenied):
                require_conversational_bugfix_localx_integration(
                    authorization=item, delivery=self.delivery)

    def test_cannot_use_local_dc_for_build_or_x_publish(self):
        for stage in ("BUILD", "PUBLISH_X"):
            item = dict(self.delivery, stage=stage)
            with self.subTest(stage=stage), self.assertRaises(LocalXIntegrationDenied):
                require_conversational_bugfix_localx_integration(
                    authorization=self.auth, delivery=item)

    def test_default_github_localx_after_ci_green_without_dc(self):
        delivery = dict(self.delivery, mergeable=True, base_change_impact_checked=True)
        require_github_localx_integration(authorization=self.auth, delivery=delivery)
        require_github_localx_integration(
            authorization=dict(self.auth, github_only=True, dc_forbidden=True),
            delivery=delivery,
        )

    def test_default_github_route_requires_exact_success_and_safe_pr(self):
        delivery = dict(self.delivery, mergeable=True, base_change_impact_checked=True)
        for delta in (
            {"mergeable": False}, {"base_change_impact_checked": False},
            {"ci_conclusion": "FAILURE"}, {"ci_head_sha": "b" * 40},
            {"pr_base": "cleanup/2d-3d-sync"}, {"stage": "PUBLISH_X"},
        ):
            with self.subTest(delta=delta), self.assertRaises(LocalXIntegrationDenied):
                require_github_localx_integration(
                    authorization=self.auth, delivery=dict(delivery, **delta))

    def test_default_github_route_blocks_scope_drift_and_revocation(self):
        delivery = dict(self.delivery, mergeable=True, base_change_impact_checked=True)
        for delta in (
            {"revoked": True}, {"localx_merge_forbidden": True},
            {"source": "MEMORY_SUMMARY"}, {"intent": "DISCUSS_BUG"},
        ):
            with self.subTest(delta=delta), self.assertRaises(LocalXIntegrationDenied):
                require_github_localx_integration(
                    authorization=dict(self.auth, **delta), delivery=delivery)
        with self.assertRaises(LocalXIntegrationDenied):
            require_github_localx_integration(
                authorization=self.auth, delivery=dict(delivery, scope="another task"))

    def test_untrusted_context_is_rejected(self):
        item = dict(self.auth, source="MEMORY_SUMMARY")
        with self.assertRaises(LocalXIntegrationDenied):
            require_conversational_bugfix_localx_integration(
                authorization=item, delivery=self.delivery)


class OfficialReleaseTests(unittest.TestCase):
    X, SOURCE, MERGE = ("b" * 40, "a" * 40, "c" * 40)

    def _pr(self, **updates):
        pr = {
            "number": 12, "merged": True,
            "merged_at": "2026-10-12T17:35:00Z",
            "merge_commit_sha": self.MERGE,
            "head": {"ref": "localX", "repo": {"full_name": "looaeedr/whd"}},
            "base": {"ref": "cleanup/2d-3d-sync",
                     "repo": {"full_name": "looaeedr/whd"}},
        }
        pr.update(updates)
        return pr

    def _comments(self):
        fields = ("repo=looaeedr/whd\npr=12\nsource=localX\n"
                  "head=" + self.SOURCE + "\ntarget=cleanup/2d-3d-sync\n"
                  "base=" + self.X)
        return [{"id": 101,
                 "user": {"login": "looaeedr", "type": "User"},
                 "body": "/推推\nWHD_LOCALX_PUBLISH_AUTH_V1\n" + fields}]

    def _check(self, *, x=None, pr=None, parents=None, comments=None):
        return require_official_release_proof(
            repo="looaeedr/whd", pushed_sha=self.MERGE,
            production_sha=self.MERGE if x is None else x,
            pr=self._pr() if pr is None else pr,
            merge_parents=[self.X, self.SOURCE] if parents is None else parents,
            comments=self._comments() if comments is None else comments,
        )

    def test_release_tag_uses_taipei_date_and_exact_merge_sha(self):
        self.assertEqual(self._check(), "v2026.10.13-x-cccccccccccc")
        self.assertEqual(
            official_release_tag(self.MERGE, "2026-10-12T15:59:59Z"),
            "v2026.10.12-x-cccccccccccc")
        self.assertEqual(
            official_release_tag(self.MERGE, "2026-10-12T16:00:00Z"),
            "v2026.10.13-x-cccccccccccc")

    def test_no_release_before_github_sync(self):
        with self.assertRaisesRegex(OfficialReleaseDenied, "SYNC"):
            self._check(x=self.X)

    def test_reject_unapproved_or_non_product_merge(self):
        for pr in (
            self._pr(merged=False),
            self._pr(merge_commit_sha=self.X),
            self._pr(head={"ref": "feature", "repo": {"full_name": "looaeedr/whd"}}),
            self._pr(head={"ref": "localX", "repo": {"full_name": "other/whd"}}),
            self._pr(base={"ref": "main", "repo": {"full_name": "looaeedr/whd"}}),
        ):
            with self.subTest(pr=pr), self.assertRaises(OfficialReleaseDenied):
                self._check(pr=pr)
        for parents in ([], [self.X], [self.X, self.SOURCE, self.MERGE]):
            with self.subTest(parents=parents), self.assertRaises(OfficialReleaseDenied):
                self._check(parents=parents)
        with self.assertRaises(LocalXPublishDenied):
            self._check(parents=[self.SOURCE, self.X])

    def test_release_needs_exact_owner_push_but_no_second_uat(self):
        # A single authenticated /推推 is sufficient even if no Windows test is asserted.
        self._check(comments=self._comments())
        for subset in ([], [{"id": 100, "user": {"login": "looaeedr", "type": "User"},
                             "body": "/驗收通過\nWHD_WINDOWS_LOCALX_UAT_V1"}]):
            with self.subTest(subset=subset), self.assertRaises(LocalXPublishDenied):
                self._check(comments=subset)
        wrong = self._comments()
        wrong[0]["body"] = wrong[0]["body"].replace(self.SOURCE, self.X)
        with self.assertRaises(LocalXPublishDenied):
            self._check(comments=wrong)

    def test_invalid_sha_and_unzoned_merge_time_fail_closed(self):
        for stamp in ("2026-10-13T00:00:00", "bad", None):
            with self.subTest(stamp=stamp), self.assertRaises(OfficialReleaseDenied):
                official_release_tag(self.MERGE, stamp)
        with self.assertRaises(OfficialReleaseDenied):
            official_release_tag("NOT_SHA", "2026-10-13T00:00:00+08:00")


if __name__ == "__main__":
    unittest.main()
