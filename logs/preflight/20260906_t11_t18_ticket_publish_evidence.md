# T11-T18 Ticket Publish Evidence

- user RED approval: confirmed
- user ticket-breakdown approval: confirmed
- backup: backup-20260906-132347-t11-t18-ticket-publish
- local source head before publish: c35aa11498f7acffaa33aa858d8d85c318fb55a2
- production changes: none

## Approved RED source
- tests/test_phase6_receiving_vault_requirement_reds.py
- logs/preflight/20260906_receiving_vault_requirement_red_evidence.md
- refined RED result: Headless 11 failed / 7 passed / 6 GUI skipped; Xvfb 17 failed / 7 passed; GREEN diagnostics 7/7 passed.

## GitHub issue mapping
- T11 → #11 — Family State Isolation：類型切換只共享 W/H/D/T
- T13 → #12 — Receiving Base Plate 55 Contract
- T12 → #13 — Receiving Asymmetric Policy：取消並隱藏對稱結構
- T15 → #14 — Per-Door Inner Door Selection + Physical Inner-Door Panel
- T14 → #15 — Box Body Child Input Sections
- T16 → #16 — Receiving Door / Frame / Divider Authoritative Placement Contract
- T17 → #17 — Receiving Inner Door / Frame Default 80 mm Datum
- T18 → #18 — Integrated RED Closure + Headless/Xvfb Release Gate

## Dependency correction
The connector create response exposed issue URLs but not a numeric issue field. Initial dependent issue bodies therefore contained `#undefined`. The issues were immediately re-read from GitHub and updated using the actual assigned numbers above. Final verification must assert no `#undefined` remains.

## GREEN guards intentionally not split into repair tickets
- R03: divider is already a real material sheet.
- R06-Divider: divider authoritative placement resolver exists.
- R10: 2-piece/3-piece box body physical pieces already exist.
- R12-D: per-door inner-door state model already represents arbitrary subsets.
- R14: single-door=0 divider, multi-door divider topology already exists.

READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md
