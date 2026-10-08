"""Regression for Flow v2 QA run-read permissions and safe GitHub 403 diagnostics."""
from __future__ import annotations

from io import BytesIO
from pathlib import Path
from urllib.error import HTTPError

import pytest

from tools import control_transaction_production_executor as writer

ROOT = Path(__file__).resolve().parents[2]


def test_push_transaction_explicitly_grants_actions_read():
    workflow = (ROOT / '.github/workflows/whd-control-transaction-v2-request.yml').read_text(encoding='utf-8')
    permissions = workflow.split('\npermissions:\n', 1)[1].split('\nconcurrency:', 1)[0]
    assert '  contents: write\n' in permissions
    assert '  issues: write\n' in permissions
    assert '  actions: read\n' in permissions


@pytest.mark.parametrize('message,classification', [
    ('Resource not accessible by integration', 'INTEGRATION_PERMISSION_DENIED'),
    ('You have exceeded a secondary rate limit.', 'GITHUB_RATE_LIMIT'),
    ('Forbidden by policy', 'FORBIDDEN_UNCLASSIFIED'),
])
def test_github_403_diagnostic_has_allowlisted_fields_only(monkeypatch, message, classification):
    fake_token = 'ghs_TEST_DO_NOT_LOG_SECRETS'
    leaked_body = ('{"message":"' + message + '", "token":"' + fake_token + '"}').encode()

    def forbidden(request, timeout):
        raise HTTPError(
            request.full_url, 403, 'Forbidden',
            hdrs={'X-GitHub-Request-Id': 'ABC1:DEF2:012345:6789AB',
                  'X-RateLimit-Remaining': '0',
                  'Retry-After': '31',
                  'X-Accepted-GitHub-Permissions': 'actions=read'},
            fp=BytesIO(leaked_body),
        )

    monkeypatch.setattr(writer, 'urlopen', forbidden)
    with pytest.raises(writer.ProductionExecutorError) as exc:
        writer._api('looaeedr/whd', 'GET', '/actions/runs/123456', fake_token)
    diagnostic = str(exc.value)
    assert 'GITHUB_API_403' in diagnostic
    assert 'endpoint=ACTIONS_RUN_READ' in diagnostic
    assert 'method=GET' in diagnostic
    assert 'class=' + classification in diagnostic
    assert 'rate_remaining=0' in diagnostic
    assert 'retry_after_seconds=31' in diagnostic
    assert 'request_id=ABC1:DEF2:012345:6789AB' in diagnostic
    assert 'accepted_permissions=actions:read' in diagnostic
    assert fake_token not in diagnostic
    assert 'token' not in diagnostic.lower()
    assert 'Forbidden by policy' not in diagnostic
    assert 'message' not in diagnostic


def test_403_diagnostic_sanitizes_malicious_headers_and_paths(monkeypatch):
    def forbidden(request, timeout):
        raise HTTPError(request.full_url, 403, 'Forbidden',
                        hdrs={'X-GitHub-Request-Id': 'evil\nsecret=yes',
                              'X-RateLimit-Remaining': 'fake',
                              'Retry-After': 'bad',
                              'X-Accepted-GitHub-Permissions': 'Bearer GHSECRET'},
                        fp=BytesIO(b'not json, GHSECRET'))
    monkeypatch.setattr(writer, 'urlopen', forbidden)
    with pytest.raises(writer.ProductionExecutorError) as exc:
        writer._api('looaeedr/whd', 'GET', '/issues/12?secret=GHSECRET', 'GHSECRET')
    diagnostic = str(exc.value)
    assert 'endpoint=OTHER_GITHUB_API' in diagnostic
    assert 'request_id=unavailable' in diagnostic
    assert 'rate_remaining=unknown' in diagnostic
    assert 'retry_after_seconds=unknown' in diagnostic
    assert 'accepted_permissions=unavailable' in diagnostic
    assert 'GHSECRET' not in diagnostic
    assert '\n' not in diagnostic
