---
whd_doc_role: CURRENT
whd_contract: ci-test-sharding-parallelization-revision-notes
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# WHD CI Test Sharding / Parallelization — Revision Notes

Date: 2026-09-16 (Asia/Taipei)
Applies to: `2026-09-16-ci-test-sharding-parallelization-design.md`
Status: approved design corrections; implementation not yet authorized

These revision notes are normative. They tighten the parent specification in four areas discovered during review: shard-assignment stability, flaky retry visibility, unified aggregation reporting, and GitHub Actions `bash -e` result-classification safety.

## R1 — Stable deterministic shard assignment

The authoritative shard algorithm must not use collection position/index modulo shard count. Adding or removing one test must not cause broad remapping of unrelated later tests.

The implementation must also not use Python's built-in `hash()`, because its process randomization makes it unsuitable as a cross-run shard authority.

Preferred v1 rule:

1. Canonicalize pytest node id.
2. Use a fixed language-independent digest such as SHA-256.
3. Assign nodes with Rendezvous / Highest-Random-Weight (HRW) hashing over configured shard ids using stable input equivalent to `lane + node_id + shard_id`.
4. Persist node-to-shard ownership and a digest of the canonical manifest.
5. Same commit + same node set + same shard configuration must reproduce the same ownership mapping.

If HRW is later replaced, migration evidence must prove deterministic ownership, zero missing/duplicate nodes, and measured remap rate.

## R2 — Flaky retry evidence

Automatic rerun is diagnostic only. A first-run RED cannot be erased because a retry passes.

Any node with first-run RED and retry GREEN must be emitted as `[FLAKY-WARNING]` in both structured aggregation data and human-readable output.

Required fields include:

- node id;
- owning shard;
- first-run result;
- retry result;
- first-run failure signature;
- classification;
- whether the node is allowed to affect acceptance.

Repeated `[FLAKY-WARNING]` events must remain queryable from artifacts so intermittent failures do not become normalized noise.

## R3 — Unified Markdown Summary

Stage D aggregation must generate `unified-summary.md` and publish the same content to GitHub Actions `$GITHUB_STEP_SUMMARY`.

A developer must be able to understand a RED run without opening every shard job.

The summary must include at minimum:

- tested commit SHA and expected reference/authority SHA where applicable;
- collection count and full-union reconciliation state;
- overall acceptance state;
- per-lane PASS / FAIL / SKIP counts and duration;
- per-shard duration and terminal state;
- every failed node id and owning shard;
- classification;
- first-run and retry result;
- `[FLAKY-WARNING]` marker when applicable;
- bounded assertion/error excerpt;
- artifact names or workflow references for complete logs.

The summary is an index into full evidence, not a substitute for complete artifacts.

## R4 — Xvfb non-zero rc is not a hang

Observed failure mode: `xvfb-run` can run for roughly 10 minutes, terminate normally with `rc=1`, and still prevent classification because GitHub Actions shell fail-fast semantics (`bash -e`) exit the step before `status=$?` and before the classification program executes.

Therefore a non-zero Xvfb/pytest exit code is not, by itself, a hang.

The workflow must distinguish:

- child process still running;
- child process completed with non-zero rc;
- shell exited before rc capture/classification;
- classifier started and returned a classification;
- classifier itself failed or timed out.

The following pattern is forbidden under fail-fast shell semantics:

```bash
xvfb-run -a python -m pytest ...
status=$?
python classify.py --pytest-rc "$status"
```

If pytest returns `1`, `bash -e` may exit before `status=$?`, so no classifier result exists.

A valid wrapper must deliberately capture child rc before fail-fast behavior resumes, for example:

```bash
set +e
xvfb-run -a python -m pytest ... >xvfb-pytest.log 2>&1
pytest_rc=$?
set -e

python tools/classify_test_result.py \
  --pytest-rc "$pytest_rc" \
  --log xvfb-pytest.log
classifier_rc=$?

exit "$classifier_rc"
```

If output is piped through `tee`, the wrapper must preserve the child command's rc with `PIPESTATUS[0]`, not `$?` from `tee`.

Required evidence fields:

- `child_started=true`;
- child start timestamp;
- child end timestamp;
- `child_rc`;
- `classifier_started=true|false`;
- `classifier_rc` when started;
- final classification;
- log/artifact path.

Fail-closed classification rules:

1. `child_rc != 0` and `classifier_started=false` => `CLASSIFICATION_NOT_RUN`, never `HANG`.
2. Child has no terminal rc and exceeds the configured timeout => timeout/hang classification with timeout evidence.
3. `classifier_started=true` but no terminal classifier result => classifier/infrastructure failure.
4. Inherited/baseline RED may be reported only after the classifier actually runs against captured evidence.
5. The shell wrapper must have regression coverage for at least child rc `0`, child rc `1`, and an explicit timeout case.

## R5 — Definition-of-Done additions

The CI optimization cannot be accepted until all of these are also true:

- shard keys are stable under ordinary inventory changes and are not based on collection index or Python built-in `hash()`;
- first-run RED → retry GREEN remains visible as `[FLAKY-WARNING]`;
- `$GITHUB_STEP_SUMMARY` contains the unified failure/acceptance summary;
- every non-zero pytest/Xvfb child rc is captured and reaches classification;
- GitHub shell fail-fast behavior cannot bypass classifier execution or artifact emission;
- `CLASSIFICATION_NOT_RUN` and `HANG` are separate states and cannot be conflated.

## Permanent operating rule

**Non-zero child rc is evidence, not permission for the shell to abort classification.** CI wrappers must capture pytest/Xvfb rc explicitly before fail-fast semantics resume. A completed `xvfb-run` with `rc=1` is a completed test execution; if the classifier did not run because of `bash -e`, classify the workflow defect as `CLASSIFICATION_NOT_RUN`, not as an Xvfb hang.
