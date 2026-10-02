# Receiving / Vault Requirement RED Evidence

- task: Requirement-level RED-only verification for Receiving/Vault follow-up requirements. No production changes. No ticket breakdown before user approval.
- backup: backup-20260906-125148-product-reds
- source_head_before_refinement: 1d9fb48965efb5558ea1ae7ad41155fc1f6e6140
- refined_red_commit: 46e00ad09a452ab8125f99bf04bc8ee2fc6571c9

phase6-corner-3d-model-integrity
diagnosing-bugs
tdd
READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md
READ_REFERENCE: 基準檔/截角資料庫/README_母規則說明.md
READ_REFERENCE: 基準檔/截角資料庫/certified_relief_rules.json
READ_REFERENCE: 個人AI檔案庫/踩坑庫/phase6_assembly_relief_pitfalls.md

## User clarification incorporated
- Shared dimensions across family switch are W/H/D/T; prior E was a typo.
- Divider exists only for multi-door topology.
- Each outer door independently may have an inner door or no inner door.
- Receiving inner-door default depth datum is 80 mm inward from that outer door face.
- Receiving inner-door frame uses the same default 80 mm depth datum.
- 80 mm is a Receiving default, not a globally immutable constant.

## Commands
Headless:
`env -u DISPLAY python -m pytest -q tests/test_phase6_receiving_vault_requirement_reds.py`

Observed: 11 failed / 7 passed / 6 skipped. GUI requirements skipped by policy without DISPLAY.

Xvfb:
`xvfb-run -a python -m pytest -q tests/test_phase6_receiving_vault_requirement_reds.py`

Observed: 17 failed / 7 passed. No collection, fixture, DISPLAY, timeout, or syntax failures.

Diagnostic GREEN-only rerun:
`python -m pytest -q <R03> <R06-divider> <R10> <R12-diagnostic> <R14>`

Observed: 7 passed.

## Requirement evidence matrix — user approved

| ID | Requirement | Observed behavior | Status | User decision |
|---|---|---|---|---|
| R01 | Receiving base plate default shrink top/bottom/left/right = 55 | Defaults are 0/0/0/0 | RED | approved |
| R02 | 55 nominal shrink survives local seam relief | Expected blank X=720, observed 830 | RED | approved |
| R03 | Divider is a real manufacturing sheet part | Real sheet/blank exists and W-2T span is valid | GREEN diagnostic | n/a |
| R04 | Receiving outer door 3D plane mates to real body front datum | Door Z=175 while body front Z=346 | RED | approved |
| R05 | Receiving horizontal divider occupies body depth interval | Divider Z starts about -12.5 while body begins at 0 | RED | approved |
| R06-door | Door has authoritative placement contract | resolver raises no authoritative placement contract | RED | approved |
| R06-frame-top | Top frame has authoritative placement contract | resolver raises no authoritative placement contract | RED | approved |
| R06-frame-left | Left frame has authoritative placement contract | resolver raises no authoritative placement contract | RED | approved |
| R06-frame-right | Right frame has authoritative placement contract | resolver raises no authoritative placement contract | RED | approved |
| R06-divider | Divider authoritative placement resolver exists | resolves successfully | GREEN diagnostic | n/a |
| R07 | Receiving hides symmetry control and is asymmetric | symmetry bar still packed/visible | RED | approved |
| R08 | Family switch preserves W/H/D/T only | W/H/D reset to Receiving defaults; T survives | RED | approved |
| R09 | Switching back to Vault restores Vault FW/fold values | Receiving FW/ZL1 overwrite Vault values | RED | approved |
| R10 | 2-piece / 3-piece box body already has true physical piece counts | 2 and 3 real physical pieces resolve | GREEN diagnostic | n/a |
| R11 | Each box-body child physical piece has its own input group | expected child groups absent | RED | approved |
| R12 | Every outer door has an independent inner-door checkbox state | no visible 內門 checkbox exists | RED | approved |
| R12-diagnostic | State model can represent any subset of outer doors with inner doors | none/upper/lower/both all derive correctly | GREEN diagnostic | n/a |
| R13 | Only enabled outer doors get real inner-door panel physical parts | `inner_door:upper` / `inner_door:lower` panels are absent from workspace | RED | approved |
| R14 | Divider exists only for multi-door topology | single door -> 0 divider; two doors -> 1 divider | GREEN diagnostic | n/a |
| R15 | Receiving inner-door default plane is 80 mm inside its own outer-door face | observed separation 175 mm | RED | approved |
| R16 | Receiving inner-door frame default plane is 80 mm inside its own outer-door face | observed separation 175 mm | RED | approved |

## Boundary guard
- No product ticket numbers or issue boundaries are assigned by this evidence.
- GREEN diagnostic requirements must not become repair tickets.
- User approved the RED interpretation; ticket grouping was subsequently approved and published as T11-T18.
