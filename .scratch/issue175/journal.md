# Issue #175 / T2 journal

## 2026-09-13 CLAIMED
- atomic claim branch: `coord/issue-175-claim`
- work branch created from `6a26e7be05a8098c8b9b2bff6f0fd675d3491e45`
- production resolver readback: already DM7-conformant; no production rewrite planned

## 2026-09-13 RED
- regression: `tests/test_issue175_dm7_navigation_authority_contract.py`
- local mirrored run: `2 failed`
- failure class: stale durable guidance in Skill + AI08
- exact conflict: stale explicit child / unspecified BoxBody context could be re-resolved to remembered/first child in docs, while canonical DM7 requires fail-closed exact identity and explicit `RESTORE_CHILD_CONTEXT`

## 2026-09-13 IMPLEMENTING / GREEN
- updated only affected Skill + AI08 durable rule; no production geometry/navigation source changed
- local focused GREEN: `2 passed`; canonical pure module probe PASS
- remote first terminal failure `34714063047 @ be2a58eb...`: preflight-only failure because task word `guidance` substring-matched Registry `UI`; config/baseline invariants remained unchanged
- read `.agents/skills/engineering/UI設計與去AI味/SKILL.md`, corrected preflight evidence/task wording
- terminal remote GREEN: `34714142384 @ 1c001074ed508957dfd4f83d9d907aabee70032a`
- Phase6 Knowledge Preflight: PASS
- focused pytest: `9 passed, 0 failed, 1 warning in 1.48s`
- canonical module `RESTORE_CHILD_CONTEXT` probe: PASS
- config SHA before/after: `980eab68d4a1732a5313b22329852dfc9691c83e4e2a64cccd18022afae4ee67`
- protected baseline fingerprint before/after: `d1aa9f08fd2bbd1eca6e10e106c91722ecd0461418233b5a30858d1aa942ef60`

## 2026-09-13 CLEANUP
- tested head locked: `1c001074ed508957dfd4f83d9d907aabee70032a`
- delete temporary QA workflow and `.scratch/issue175/*`
- compare tested head → cleaned head; only those cleanup paths may differ
- then reread final Skill/AI08/test and write #175 closure evidence
