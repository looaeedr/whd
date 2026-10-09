"""Explicit /推推 remains the only allowed production X publish approval."""
import unittest
from tools.localx_publish_gate import require_publish_approval, LocalXPublishDenied

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

if __name__ == "__main__":
    unittest.main()
