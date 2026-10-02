# Phase 4 T1 — Immutable Settings contracts

## Identity
- Master: #388
- Task: #390 / T1
- Fixed Phase 4 root: `fdcc9b0a08f7ed19f5c17984f2793c16d6f49be4`
- Predecessor T0 accepted candidate: `d3f37e251816af974d940e7f2c1738dbb38edb3e`
- Branch: `refactor/issue390-phase4-t1-settings-contracts-20260920`

## RED
- First harness run `35461287458`: invalid RED because runner lacked `python3-tk`; not accepted.
- Clean intended RED RUN: `35461321608`
- Result: workflow SUCCESS while pytest intentionally RED
- Focused pytest: **5 failed**
  - 4 × `ModuleNotFoundError: phase6_settings_contracts`
  - 1 × expected file-not-found structural probe
- Marker: `ISSUE390_T1_EXPECTED_RED=1`

## GREEN
Final GREEN RUN: `35461489775` / job `105946045848`

- T1 contract tests: **5 passed**
- Existing focused Settings regressions: **14 passed / 6 skipped**
- `ISSUE390_T1_CONTRACT_GREEN=1`
- `ISSUE390_T1_EXISTING_SETTINGS_GREEN=1`
- `ISSUE390_T1_RUNTIME_SOURCE_DELTA=0`
- `ISSUE390_T1_PROTECTED_DRIFT=0`
- `ISSUE390_T1_REVERSE_IMPORTS=0`

Two earlier GREEN attempts were harness dependency failures only:
- `35461401180`: missing `ezdxf`
- `35461447321`: missing `shapely`
The final workflow uses repo `requirements.txt`.

## Contracts added
`phase6_settings_contracts.py`:
- `FrozenSettingsMapping`
- `SettingsStateSnapshot`
- `SettingsMutationResult`
- `SettingsEffect`
- `SettingsStageRequest`
- `SettingsCommitRequest`
- `ExternalSettingsSyncRequest`
- `ExternalModelTransitionRequest`
- canonical Settings JSON
- deterministic SHA-256 Settings fingerprint
- recursive defensive freeze

## Invariants
- nested mappings/sequences are defensively frozen
- callback values fail closed
- Tk objects fail closed
- app/gui objects fail closed
- insertion order does not affect canonical fingerprint
- Settings contracts import no Tk/gui/bridge modules
- existing Settings runtime sources are byte-identical to the T0 predecessor
- no runtime cutover occurred in T1

Next: #391 T2 pure Settings transition kernel.
