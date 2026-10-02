---
whd_doc_role: REFERENCE
whd_contract: issue497-t0-settings-dataflow-census
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# Issue #497 / Phase 5 T0 — Fresh Settings Mutation / Dataflow Ownership Census

Identity
- Master #506
- Ticket #497
- Production target cleanup/2d-3d-sync
- Frozen X execution base ba9cda2e1eed30d4702a2e2e4cebbd001bbf56aa
- Frozen Git tree 74b2dcbeb7b280b547ff28092205a34f84da0845
- Work-order branch work/issue506-phase5-settings-dataflow-20260922
- Preflight evidence commit fe319a1618079c90abe9ab47f7ec0dfd78a6ce8a
- Bridge blob 9b119a4af2101d4fc9cd197bfb4cef4bb7f090e1
- Bridge LOC at execution base 7929
- Top-level defs/classes 334 = 329 functions + 5 classes
- Spec publication bridge LOC was 7923; the +6 line execution-base drift is observational only. Phase 5 has no LOC threshold.
- Requirement Authority: user-approved Phase 5 v1.1, R1-R6 approved.
- T0 is evidence-only; production/test behavior change is not authorized.

Settings owner map frozen at T0
- Main GUI committed runtime Settings: phase6_settings_center.py::SettingsService — d441ae582b3101226aa2ffa1a01d140f3ecc3c25
- Designer pure semantic transitions: phase6_settings_transitions.py — 9c415adeca3f5ff944dd4baf9ed2128d5d3ebc82
- Designer transaction semantic commit: Phase6SettingsTransactionController — 0edd1aef6df4ee47e59b27a5b86dc9128946accd
- Stage/debounce/external-revision ordering: Phase6SettingsTransactionService — 9146ef77c8b696068df304836b329fed4f99bc6e
- Typed contract seam, not behavior owner: phase6_settings_contracts.py — 42979e3a1c93534edb7c0277426ec4ef0ba00b66
- Settings presentation: Phase6SettingsPanel — abc61019652dd99c825d6a0147d05a4f5d94eef8
- Live-sync transport helpers: phase6_sync_envelope.py — a230f74c833053546710f25c34c5a183bc1c7deb
- Application composition: Phase6FoldDesignerComposition — 82780fdd4bcd05176387d9de94f5a0f2094d7d0e
- Update scheduling/routing: gui_modules/application/command_router.py — 29e75ca0d2c04f870e91523e29c01e45970e2b89
- Main GUI lifecycle/live snapshot application: gui_modules/application/lifecycle.py — 8940b637c690caa2a4025edc4f625a340b1a3a2e
- Reverse imports of fold_designer_bridge across all listed owners: 0

R1 — Settings apply/update sequencing
- _phase6_apply_setting_updates: lines 1668-1768, 101 LOC
- callers: _phase6_flush_pending_settings, _phase6_apply_external_settings, _phase6_apply_settings_delta
- direct bridge writes: _job, _phase6_applying_settings, _phase6_settings_guard
- current sequence includes transactions.normalize_updates, W reconcile/restore, _save_current_part, transactions.commit_settings, UI variable projection, _phase6_refresh_profiles_from_settings, root.after_cancel, do_update, and _settings_change_callback
- T1/T2 must preserve ordering while removing deep effect sequencing from bridge; normalize/reconcile/commit semantics stay with existing Settings owners

R2 — Settings to profile/dimension projection mixed with apply/render
- _phase6_recalculate_part_dimensions: lines 1555-1616, 62 LOC
- callers: _phase6_refresh_profiles_from_settings, _phase6_reset_initial_values, _phase6_refresh_linked_part_profiles, _phase6_store_editor_values
- reads _settings_values and _phase6_input_snapshot; computes and updates part_dimensions including Door/BasePlate physical child dimensions
- _phase6_refresh_profiles_from_settings: lines 1617-1667, 51 LOC
- callers: _phase6_apply_setting_updates, _phase6_on_baseline_model_changed
- same function recalculates dimensions, build/merges BoxBody profile, runs derived sync, stashes profiles, projects active profile, and calls bend_ui.render
- T3 must establish pure planning and keep workspace identity/mutation/render outside the planner

R3 — Baseline/model semantic plan plus cross-owner effects
- _phase6_on_baseline_model_changed: lines 2037-2155, 119 LOC
- callers: SettingsPanel baseline callback, external-model path, facade/update queue
- direct bridge writes include corner editable/stash state, baseline last model, last W/D, non-receiving structure state
- semantic plan already comes from transactions.commit_family_model_transition
- bridge still executes editor value storage, W/H/D projection, profile reset, derived sync, topology/persistent-control refresh, Settings context rerender, status, update intent or forced live publish, and Corner Data refresh
- T4 must keep family/model semantics in the controller and move application effect sequencing to the coordinator

R4 — Factory reset bypasses a common typed application seam
- _phase6_reset_initial_values: lines 5073-5176, 104 LOC
- direct evidence includes settings_values.update, input_snapshot.update, box_whd writes, profile rebuild/stash, Tk projection, workspace dirty, Bending render, SettingsPanel refresh, and do_update
- T4 must route reset through typed Settings application sequencing without changing factory-source authority or unrelated baseline/corner state

R5 — Editor-value commit remains inside protected Part Editor path
- _phase6_store_editor_values: lines 6986-7068, 83 LOC
- callers: baseline-model transition, box-body physical-piece commit, multiple branches of protected _fix11_save_current_part
- direct bridge mutation includes input snapshot/settings/box WHD and settings guard
- current semantic/effect calls include commit_box_fw, recalculate dimensions, refresh linked profiles, and host callback
- T5 may extract the Settings/dataflow commit seam only; it must not move protected Part Editor orchestration or the Linked Endcap KEEP seam

R6 — Live-sync plan mixed with callback/bookkeeping effects
- _phase6_publish_live_state: lines 2449-2516, 68 LOC
- callers: corner-change notification, baseline transition, remove-part, update-intent publish path, facade
- direct writes: live-sync guard, revision, last-live state/fingerprint/payload, input_snapshot assembly_relief
- current function combines fingerprint, host-relief force/anti-echo decision, mapping delta, revision/transaction id, envelope assembly, host callback, success bookkeeping, and error status
- existing phase6_sync_envelope.py only owns stable_fingerprint, actual_delta, mapping_delta
- T6 must deepen this into a pure publication plan and keep callback/bookkeeping in the effect layer

Architecture / protected decisions baseline
- Root-owner reverse-import bridge count for listed Settings/application owners: 0
- install_fold_designer_bridge_facade binding count: 69
- phase6_workspace_shell.py: ABSENT
- phase6_part_editor_session.py: ABSENT
- Linked Endcap = KEEP_COMPATIBILITY
- Settings exact-six = KEEP_BRIDGE_COMPATIBILITY
- Workspace Shell = NO_EXTRACTION
- Part Editor = C_KEEP_BRIDGE_COMPATIBILITY
- _fix11_init = bootstrap-only

Current test-oracle blobs
- tests/test_issue366_t2_settings_transaction_owner.py -> faaf963da7348bfff5ce1bba810838c326e5065d
- tests/test_issue366_t2a_settings_stage_controller.py -> b4df02f61a77136cb6a4ac8945ec432db10e15ab
- tests/test_issue390_settings_contracts.py -> d43140f7033cb7d5ea75b92ea2ed5001188200b6
- tests/test_issue391_settings_transitions.py -> 594492fc42015a2e4452c8ea28609c3991ee944a
- tests/test_issue392_settings_service.py -> 10fb64368868cbab3cf3e60f639278529d028698
- tests/test_phase6_settings_service.py -> abf4ec33b4548fae98d51dfbf4887f3b747f804e
- tests/test_phase6_left_global_transaction.py -> 586a04f32d1fd81f5772debccb8e553977610016
- tests/test_gui_fold_designer_transaction_contract.py -> 2f24fd003d97444fe4aa3c30397da65d577401bb
- tests/test_phase6_baseline_operation_alignment.py -> 53ab30ca13b8895452c4171785953330fd9fe809
- tests/test_issue445_settings_presentation_owner.py -> ba60c06b2a1b101cc28923de5cb385ce9aa78315
- tests/test_phase6_settings_panel_ownership.py -> 666a068fab04571c5da0afe6d194eed37c6a1340

Protected Git-object baseline
- config.ini blob 3165d9f4192ac80fcfdca54fbbe7d1a22900a0d1, size 983
- DXF blob count 10
- 基準檔/指示燈/123.dxf -> f7486cd1fee6ff9b7aa3b1cf73565d6a6787f127
- 基準檔/指示燈/小門 - 複製.dxf -> 171406f2609032bf917fea62f0588e6d9d94c99b
- 基準檔/指示燈/小門.dxf -> 171406f2609032bf917fea62f0588e6d9d94c99b
- 基準檔/指示燈/盒子.dxf -> 195c710ab5e7700b1574f48191f9869fd9effa1e
- 基準檔/通用/19門.dxf -> c9ffd7b7b528a04d89ec36fb66e07d7b61d05b9a
- 基準檔/金庫型/中隔.dxf -> 9d54945080e4780bf9c19d48b0d55e630a64968d
- 基準檔/金庫型/封頭尾.dxf -> 55da4e4bd607315eaad59a2e57f6e3eb1702d7f0
- 基準檔/金庫型/箱身.dxf -> acdb2c800166d220de1fc38a78b4ba50f0efd825
- 基準檔/金庫型/門.dxf -> ca65d3d8aa40746c2177ea5aa5df329bd0544751
- 基準檔/開孔/AS&VS.dxf -> cb60c770999f72ba2c8b62b6b987d53fe44ff7d2

T0 handoff to T1
- Reuse/deepen phase6_settings_contracts.py
- Establish Phase6FoldDesignerSettingsCoordinator
- Inject through existing Phase6FoldDesignerComposition
- Use bounded ports, not a whole app/bridge service bag
- Preserve reverse-import=0, one composition root, facade ratchet <=69
- Preserve Main-GUI committed Settings owner vs Designer transaction owner split
- Current line counts/callers/test expected values are diagnostic only, not domain truth
