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

    def test_exact_approval_is_allowed(self):
        require_publish_approval(repo="looaeedr/whd",pr_number=12,
          pr={"head":{"ref":"localX","sha":"a"*40},"base":{"ref":"cleanup/2d-3d-sync","sha":"b"*40}},
          head_sha="a"*40,target_sha="b"*40,
          comments=[{"user":{"login":"looaeedr","type":"User"},
          "body":"/推推\nWHD_LOCALX_PUBLISH_AUTH_V1\nrepo=looaeedr/whd\npr=12\nsource=localX\nhead="+("a"*40)+"\ntarget=cleanup/2d-3d-sync\nbase="+("b"*40)}])



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
