---
whd_doc_role: REFERENCE
whd_contract: issue1378-t0-readback-characterization
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# Issue #1378 T0 readback characterization

CURRENT behavior observed before DM8-A refactor:

| Path | Existing state | Provider mutation |
| --- | --- | --- |
| MERGE / ALREADY_MERGED | PR already merged | merge PUT = 0 |
| SYNC_TARGET / ancestry already applied | work branch already contains target | POST /merges = 0 |
| FINALIZE / closed+completed | Issue already terminal | close PATCH = 0 |
| RELEASE_PATHS / ACTIVE scope | not stale cleanup | no stale provider mutation |
| stale RELEASE_PATHS / branch absent | stale ref already absent | DELETE = 0 |
| stale RELEASE_PATHS / branch exists | exact stale proof passes | conditional DELETE = 1 |
| stale DELETE + unrelated coord CAS race | same Issue unchanged | no provider replay; DELETE remains 1 |
| stale DELETE + same-Issue drift | same Issue changed | fail closed; DELETE remains 1 |

The permanent test uses a strict readback-only provider fence for the no-mutation paths. Any unexpected provider mutation fails the test immediately.

This checkpoint is evidence only. It does not change runtime behavior or authority.
