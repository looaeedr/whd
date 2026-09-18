# Issue #354 T0 — Phase 2 ownership / state / effect / timing preflight

## Identity
- Master: #353
- Task: #354 / T0
- Fixed Phase 2 semantic baseline: `7a8b87f8cbb50a34c5038aa196fa137b301702a4`
- Branch: `refactor/issue354-phase2-preflight-20260919`
- Classified machine gate: RUN `35403531195` / job `105788388832` — **SUCCESS**

No manufacturing implementation semantics changed in T0.

## State ownership inventory

Machine scan found **14 read keys** and **5 write keys** in the current manufacturing owner. All are classified; unclassified = 0.

### Reads
| Current app/self source | Phase 2 owner |
|---|---|
| `_phase6_assembly_type` | `request.assembly_intent` |
| `_phase6_box_whd` | `request.box_dimensions` |
| `_phase6_corner_state` | `request.corner_state` |
| `_phase6_endcap_bottom_wrap_state` | `request.endcap_bottom_wrap` |
| `_phase6_endcap_fw_state` | `request.endcap_fw` |
| `_phase6_input_snapshot` | `request.input_snapshot` |
| `_phase6_last_resolved_manufacturing_geometry` | `cache_service.cached_result` |
| `_phase6_last_resolved_manufacturing_signature` | `cache_service.cached_key` |
| `_scene_query_callback` | `adapter.render_data_provider` |
| `_settings_values` | `request.settings` |
| `assembly_ignore_fixed_corner_var` | adapter extracts immutable fallback bool |
| `assembly_relief_clearance_var` | `request.relief_clearance` |
| `baseline_model_var` | `request.cabinet_model` |
| `designer_workspace` | adapter request builder |

### Writes
| Current implicit write | Phase 2 owner |
|---|---|
| `_phase6_last_interference_probe_parts` | diagnostics result |
| `_phase6_last_relief_errors` | diagnostics result |
| `_phase6_last_relief_solutions` | diagnostics result |
| `_phase6_last_resolved_manufacturing_geometry` | cache service/result |
| `_phase6_last_resolved_manufacturing_signature` | cache service/receipt |

## Phase-1-only wiring lifecycle

Machine classification:

- `_phase6_mesh_profiles_for_part` → `PHASE1_ONLY_SERVICE_WIRING_REMOVE_AFTER_T4`
- `_phase6_operator_finished_dimensions` → `PHASE1_ONLY_SERVICE_WIRING_REMOVE_AFTER_T4`
- `_phase6_scene_query_payload_for_part` → `PHASE1_ONLY_SERVICE_WIRING_REMOVE_AFTER_T4`
- `_phase6_publish_live_state` → `PREEXISTING_COMPAT_WIRING_PHASE3_REVIEW`

Important distinction:
- the first three helper **functions** still have ordinary bridge callers;
- their `Phase6FoldDesignerApp.xxx = helper` class wiring exists for the Phase 1 service callback path and is a T4 removal target after callback decoupling;
- `_phase6_publish_live_state` class wiring predates this migration, so Phase 2 will stop using it from service, but deletion is not assumed without a separate compatibility audit.

Repo search found no explicit `self._phase6_<helper>(...)` call sites for these four names.

## Cache-hit short-circuit

Baseline source proves:

```text
1. _phase6_manufacturing_state_signature(self)
2. read last resolved geometry/signature
3. equal signature + cached result -> immediate return
4. only on miss: available-parts / scene payload / profiles / render data
```

Machine result:

```text
PASS CACHE_SIGNATURE_FIRST_SHORT_CIRCUIT=1
```

This is the performance contract for #359 / T5. Phase 2 must not require full expensive per-part DTO materialization before a cache hit unless end-to-end A/B proves no significant regression.

## Tk event-loop pump inventory

Static call graph roots:
- `_phase6_resolve_manufacturing_geometry`
- `_phase6_resolve_explicit_joint_reliefs`

The graph additionally models Phase 1 dynamic `_phase6_call_bridge(self, "name")` edges into the actual bridge callbacks.

Results:
- reachable repo functions: **223**
- direct confirmed Tk pump: **0**
- transitive confirmed Tk pump: **0**
- conservative `update/after` candidates: **11**
- unclassified candidate: **0**

All 11 candidates are data-mapping mutations:
- `raw.update`
- `source.update`
- `result.update`
- `payload.update`
- `values.update`
- `snapshot.update`

None is a Tk/root/widget event-loop pump; no `after()` candidate was found.

Machine result:

```text
PASS DIRECT_TK_PUMP_COUNT=0
PASS TRANSITIVE_TK_PUMP_PATH_COUNT=0
PASS DATA_MAPPING_UPDATE_NOT_TK_COUNT=11
PASS UNCLASSIFIED_POTENTIAL_TK_PUMP_COUNT=0
```

Therefore Phase 2 does **not** need to preserve a hidden Tk event-loop reentrancy point inside the accepted solve path.

## T0 conclusion

All required implicit inputs, outputs, effects, wiring lifecycle, cache short-circuit and Tk-pump assumptions are classified.

Next predecessor-gated task: #355 / T1 immutable request DTO contracts.
