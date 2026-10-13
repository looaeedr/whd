"""Explicit /推推 remains the only allowed production X publish approval."""
import unittest
from tools.localx_publish_gate import (
    require_publish_approval, LocalXPublishDenied,
    require_conversational_bugfix_localx_integration, LocalXIntegrationDenied,
)

class PublishGateTests(unittest.TestCase):
    def test_absent_approval_is_denied(self):
        with self.assertRaises(LocalXPublishDenied):
            require_publish_approval(repo="looaeedr/whd",pr_number=12,
              pr={"head":{"ref":"localX","sha":"a"*40},"base":{"ref":"cleanup/2d-3d-sync","sha":"b"*40}},
              head_sha="a"*40,target_sha="b"*40,comments=[])

    def _approval(self, *, uat_head="a"*40, test_site="WINDOWS",
                  order=(100, 101), uat_owner="looaeedr"):
        fields = ("repo=looaeedr/whd\\npr=12\\nsource=localX\\n"
                  "head=" + ("a"*40) + "\\ntarget=cleanup/2d-3d-sync\\n"
                  "base=" + ("b"*40))
        return [
            {"id": order[0], "user": {"login": uat_owner, "type": "User"},
             "body": "/驗收通過\\nWHD_WINDOWS_LOCALX_UAT_V1\\n"
                     + fields + "\\ntest_site=" + test_site
                     + "\\nwindows_head=" + uat_head},
            {"id": order[1], "user": {"login": "looaeedr", "type": "User"},
             "body": "/推推\\nWHD_LOCALX_PUBLISH_AUTH_V1\\n" + fields},
        ]

    def _publish(self, comments):
        return require_publish_approval(
            repo="looaeedr/whd", pr_number=12,
            pr={"head":{"ref":"localX","sha":"a"*40},
                "base":{"ref":"cleanup/2d-3d-sync","sha":"b"*40}},
            head_sha="a"*40, target_sha="b"*40, comments=comments)

    def test_exact_approval_is_allowed(self):
        self._publish(self._approval())

    def test_push_without_windows_uat_fails(self):
        with self.assertRaisesRegex(LocalXPublishDenied, "WINDOWS_LOCALX_MANUAL_UAT_REQUIRED"):
            self._publish(self._approval()[1:])

    def test_windows_uat_without_push_fails(self):
        with self.assertRaisesRegex(LocalXPublishDenied, "EXPLICIT_USER_SLASH_PUSH"):
            self._publish(self._approval()[:1])

    def test_wrong_windows_head_or_site_fails(self):
        for args in ({"uat_head": "f"*40}, {"test_site": "COREELEC"},
                     {"uat_owner":"github-actions[bot]"}):
            with self.subTest(args=args), self.assertRaises(LocalXPublishDenied):
                self._publish(self._approval(**args))

    def test_uat_must_precede_push(self):
        with self.assertRaisesRegex(LocalXPublishDenied, "MUST_PRECEDE"):
            self._publish(self._approval(order=(102,101)))

    def test_missing_github_comment_ids_fail_closed(self):
        comments = self._approval()
        for item in comments:
            item.pop("id")
        with self.assertRaises(LocalXPublishDenied):
            self._publish(comments)


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

    def test_explicit_conversation_fix_flows_to_localx_without_second_dc_approval(self):
        require_conversational_bugfix_localx_integration(
            authorization=self.auth, delivery=self.delivery)

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

    def test_untrusted_context_is_rejected(self):
        item = dict(self.auth, source="MEMORY_SUMMARY")
        with self.assertRaises(LocalXIntegrationDenied):
            require_conversational_bugfix_localx_integration(
                authorization=item, delivery=self.delivery)


if __name__ == "__main__":
    unittest.main()
