# Audit116 — Receiving Set/Bay dimensions through Fold editor / Custom transition

Date: 2026-10-27 (Asia/Taipei)
Baseline: localX 284691a6; isolated branch `fix/audit116-receiving-custom-live-preserve-20261027`.

## Reproduced defect
Native Windows Tk: fresh Receiving Set1/Bay1 W800/H1600/D350, change to W820/H1700/D360, then update sheet thickness T2→2.5. Legacy Fold editor returned cached W800/D350, and dimension recalculation plus bidirectional D-W-D profile synchronization overwrote the live Bay/3D dimensions. Switching to Custom then inherited those incorrect dimensions. This is not a valid operator dimension edit.

## Source authority and implementation
- Receiving Set/Bay or Quantity owns working W/H/D; `_settings_values` W/H/D are reusable defaults only.
- Legacy Fold editor must not re-commit its cached W/H/D in Receiving mode. Other fold/profile data and genuine T/FW settings remain editable.
- Part dimension recalculation and linked-profile refresh must overlay other Settings without replacing live Receiving W/H/D.
- In Set/Bay mode, reverse Fold D-W-D inference must not treat stale editor cores as user-authored cabinet dimensions. Re-project Fold cores from active Bay; non-Receiving retains existing bidirectional behavior.
- Preserve real inverse CROSS contact/collision validation, existing CAD/DXF source rules, and localX→X release gate.

## Acceptance
1. Native Tk Receiving W800 -> W820, H1700, D360 persists across T2.5 edit.
2. Transition Receiving -> Custom preserves current working W/H/D/T.
3. Earlier W800->W820 Divider Y span and 3D inverse CROSS still render correctly.
4. Native known-family reset, pure source validation, save/reload, and manufacturing DXF regressions remain green.
5. Never mark all 116 signed solely from automated tests.

## Evidence
`tests/test_audit116_receiving_custom_native.py`; native Windows program logs under TEMP. No production X modifications.
