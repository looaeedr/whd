# Phase 4 T4 — Typed Final Scene dependency/runtime contracts

## Identity
- Master: #388
- Task: #393 / T4
- Fixed Phase 4 root: `fdcc9b0a08f7ed19f5c17984f2793c16d6f49be4`
- Predecessor T3 accepted candidate: `70c4a0a470647322e7aa4a685b74b27520019652`
- Final tested HEAD: `9973bece9a56061360feb1f85730059a1ca33b8b`

## RED
First RED RUN `35472182509` was harness-only failure because runner lacked `python3-tk`; it is not accepted evidence.

Clean intended RED RUN: `35472206380`
- workflow SUCCESS while focused pytest intentionally RED
- **5 failed**
- missing `phase6_final_scene_contracts.py`
- adapter still owned generic `services` + `_service(name)`
- bridge had no `FinalSceneDependencies`
- marker: `ISSUE393_T4_EXPECTED_RED=1`

## GREEN
Final GREEN RUN: `35472475483`
- Headless job `105975835408`: SUCCESS
- Xvfb job `105975835518`: SUCCESS

Headless:
- T4 typed-contract tests: **5 PASS**
- existing Final Scene regressions: **42 PASS / 3 SKIP**
- projection/renderer predecessor A/B fingerprint: **32 definitions, delta = 0**
- `FINAL_SCENE_DYNAMIC_SERVICE_LOOKUP=0`
- `FINAL_SCENE_GENERIC_SERVICE_BAG=0`
- `FINAL_SCENE_CONTRACT_REVERSE_IMPORTS=0`
- `ISSUE393_T4_SCOPE_GREEN=1`
- `ISSUE393_T4_PROTECTED_DRIFT=0`

Xvfb:
- Final Scene regressions: **13 PASS**
- `ISSUE393_T4_XVFB_GREEN=1`

## Implementation
Added `phase6_final_scene_contracts.py` with frozen:
- `AssemblyScenePart`
- `AssemblySceneRenderData`
- `FinalSceneViewRequest`
- `FinalSceneDependencies`
- `FinalSceneRuntimeState`
- `FinalSceneRenderResult`
- `FinalSceneEffects`

`Phase6FinalSceneViewAdapter` now consumes explicit `FinalSceneDependencies`; generic service bag and string dispatch are removed.

`fold_designer_bridge.py` constructs explicit named dependencies. The last compatibility mutation of `adapter.services["final_render_provider"]` was removed after the first GREEN attempt exposed it.

## Superseded runs
Pushes during the focused remediation generated older-head runs `35472469685` and `35472472177`; they are superseded and are not acceptance evidence. Only RUN `35472475483` at exact tested HEAD `9973bece...` is authoritative.

## T4 boundary
Projection and renderer logic were not moved or changed; the 32-definition AST A/B fingerprint proves semantic code identity for that boundary.

Next: #394 T5 pure Final Scene projection extraction.
