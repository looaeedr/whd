# CADSplit → WHD-Engine Worker CLI — W-01 boundary (#2377)

Source of truth for the wire contract: [CADSplit_WHD_Contract.md](../docs/integrations/CADSplit_WHD_Contract.md) and `schemas/`.
This folder **does not duplicate** any WHD manufacturing formula or Registry.

## Three public operations only

```text
WHD-Engine capabilities --response C:\Jobs\capabilities.json
WHD-Engine prepare --request C:\Jobs\request.json --response C:\Jobs\prepare.json
WHD-Engine export --request C:\Jobs\request.json --response C:\Jobs\export.json
```

Source-only development entry point:

```text
python /absolute/path/to/whd/integration_cli/cadsplit_worker.py capabilities --response /outside-repo/capabilities.json
```

The Worker does not import Tk, `ae_engine`, or CADSplit just to parse CLI
arguments, validate wire JSON, or return disabled capabilities. It works from
a current working directory that is **not** the installation root.
The source-only handler derives the exact Git commit from Git metadata
and hashes its `ae_engine/**/*.py` plus Worker entrypoint. It labels its
build `source-only-unreleased`: this is a source fingerprint, **not a certified
EXE hash or release manifest**. If Git/build identity is unavailable the
source CLI rejects instead of inventing a hash. W-05 must supply a verified
packaged manifest and resource/binary integrity logic.

`capabilities` currently reports **all flags false**, zero supported
part kinds, and unverified Registry/baseline/policy (null resource hashes).
`prepare/export` validate schema and up to 20 items once in one Worker
process, then explicitly return `WHD_OPERATION_NOT_IMPLEMENTED` and
`manufacturing_verified=false`. There is no export, no Tk initialization,
no Registry initialization, no DXF write, and **no claim of working W-03/04**.
W-03 connects target Frame, canonical dimensions, policy and prepare tokens.
W-04 connects WHD FinalScene manufacturing, Save→Reload and export.
W-06 owns durable idempotency, job/output path locks, crash recovery and cancel.

## Output and failure semantics

- `stdout`: reserved/empty for these operations. The response JSON file is
  the only machine-readable payload; failures also print a short diagnostic
  to `stderr` only if no valid response can be written.
- Exit `0`: a capabilities response was written. **It does not mean
  manufacturing is supported.**
- Exit `2`: invalid UTF-8/JSON, unknown operation, protocol/schema/limit
  rejection.
- Exit `3`: request is valid but its manufacturing handler is not ready.
- Exit `4`: request or response path/build identity/IO cannot be trusted.
- A newly created `*.json` response is UTF-8, fully flushed and installed
  through same-directory hard-link atomic creation. An existing response
  file is **never overwritten**, including on retry; callers use a new
  response pathname and the original semantic job identity.
- Request JSON is size-bounded; duplicate JSON keys, NaN/Infinity, invalid
  Unicode, unsafe IDs and unsupported schema fields fail closed. Paths may
  contain Chinese and spaces; response targets inside the source/install
  tree are rejected. Customer `config.ini`, original DXF/CSV and all
  manufacturing outputs are untouched.

These are W-01 transport tests, not the Windows onedir EXE or Gate A.
W-05 must verify Windows hard-link semantics or provide an equally safe
no-clobber atomic method; W-07 separately validates real packaging/GUI.

## W-03 partial preflight (#2378, not a working prepare handler)

`prepare_evidence.py` is a **non-authorizing** building block. It hashes the
actual bytes of an explicitly selected Certified Registry and WHD-resolved
baseline list, locks the exact build/source hash, current
`manufacturing_api.resolve_policy` snapshot and item dimensions, and compares
those immutable inputs before a later export. It refuses missing, empty,
symlinked or escaping resources rather than replacing a missing source with
placeholder hashes. It must be given paths selected by WHD's
`expected_baseline_path_for`; it does **not** discover baseline filenames
from CADSplit source data. `resolve_authoritative_door_inputs` calls WHD's
own `door_finished_face_size` on a previously verified `DoorPartSpec`; it
does not infer `frame_edges`, original DXF coordinates, or a physical
part ID from source drawing names.

The `environment_fingerprint` here is an **internal resource-input evidence
digest**, not the RFC 8785 wire `request_digest`, a durable transaction or an
issued `prepare_token`. It is **not** an attestation of a Windows binary.
A real W-03 `prepare` response remains blocked on independently verified
per-face 3D frame origin/basis/normal and on durable token binding. The
existing `cadsplit_worker.py prepare` intentionally continues returning
`WHD_OPERATION_NOT_IMPLEMENTED` until that acceptance is implemented.
Neither this module nor its test cases enable manufacturing. Only W-06/04
can own export stale-revalidation and final commit.



## W-03 certified *local* Door frame and in-process prepare

The subsequent W-03 implementation now provides:

- `prepare_frame.resolve_door_finished_local_frame`: a Door **local**
  finished-face frame with bottom-left local origin, +X right and +Y up,
  checked against `ae_engine.sheetmetal_feature_core.feature_finished_point`.
  `origin_xyz_mm=[0,0,0]` and +Z are a right-handed **local plane
  embedding**, never an assembly-world position, installation orientation,
  mirror guess or proof of another physical face. The flattened DXF mapping
  remains owned by WHD's `build_finished_reference_guide`.
- `request_canonical`: RFC 8785 digest excluding exactly
  `request_id`/`request_digest`, so changing transport correlation cannot
  change job identity but changing material inputs does.
- `prepare_binding`: a worker-secret HMAC covering job, source identity,
  canonical physical-part identity, target Frame, locked dimensions and
  environment, including independent per-item preparation digests.
- `prepare_batch.prepare_trusted_door_batch`: in-process, schema-validated
  **Door plus WHD-derived Indicator Small Door** prepare. Ordinary Door uses
  `resolve_policy`, `door_finished_face_size`, four explicit layout
  `frame_edges` and its own baseline. `indicator_small_door` requires
  `part_formed_outer`, exact asserted finished-face width/height/thickness,
  explicit `indicator_groups`, and **no** caller fold/gap/frame overrides.
  WHD's `indicator_small_door_spec` + linked finished-face owner provide
  the authoritative physical geometry and shared `指示燈/小門.dxf` baseline.
  The same content-attested Registry/baseline, HMAC token and recheck apply;
  it returns `manufacturing_verified=false`, never emits DXF or enables
  a public EXE.

**Remaining acceptance boundary:** the public Worker CLI is still not
connected to this function; the trusted installation key's durable custody,
atomic journal, verified package resource manifest and no-clobber retries are
W-06/W-05, and Windows Gate A is W-07. W-03 cannot claim public `prepare`
support or a certified EXE until those verified dependencies are available.
The present local Door frame MUST NOT be silently reused for EndCap,
IndicatorBox, BoxBody or back/mirrored faces; the **shared small door** is
different: WHD explicitly represents it with its own `DoorPartSpec`
helper, uses the verified front/local finished-face basis, and never claims
a cabinet-world or arbitrary face datum. The CADSplit-side original DXF
source frame/transform remains CADSplit's responsibility.


## W-03 versioned draft (not a public capability)

The **published/source-only W-01 CLI remains wire 1.0.0** and returns
`prepare/export` as unsupported. The W-03 Door frame evidence needs an
explicit `part.frame_edges` member not present in the immutable 1.0.0
contract. The in-process W-03 test boundary therefore uses the separate
`request_v1_1.schema.json` and `response_v1_1.schema.json`
(**protocol 1.1.0**, optional additive Door edges); it MUST NOT mutate
`request_v1.schema.json` or claim 1.1.0 public capabilities. A future
packaged Worker may only negotiate 1.1.0 after the W-04/W-06/W-05 gates.


## W-03 pre-export recomputation (internal, not public)

`prepare_recheck.recheck_trusted_door_export` is a pure fail-closed
pre-export guard. The **original prepare request and receipt must come
from a Worker-owned authenticated durable store**, not be supplied by the
external export body. It verifies separate RFC8785 request digests,
original physical item/source/Frame/dimension identity, target-frame
ownership and sealed token, then calls WHD's actual Door-only prepare
again against the **current Registry, baseline DXF, Factory Policy, build
and engine**. A change refuses the *entire batch* with
`WHD_PREPARE_STALE` before output staging.

This guard is not a transaction journal, geometry validator or DXF
exporter. W-04 must own feature/source geometry verification and
Save→Reload acceptance; W-06 must store the original authenticated
request/receipt, enforce idempotency and re-run this guard at the final
commit barrier (or prove an immutable snapshot). The W-01 public CLI
keeps all manufacturing capabilities disabled.

## W-06 private durable job-identity ledger (NOT public, #2380)

`job_identity_ledger.DurableJobIdentityLedger` is a **Worker-internal**
SQLite/WAL/FULL-sync identity reservation and completed-result readback seam.
Its **installation-store root is trusted local Worker configuration**, never a
wire request path. It recomputes the existing RFC 8785 request digest and
reserves a unique `(client_installation_id, job_id, operation)` key with an
immediate database transaction. Changing any semantic request value under the
same key fails `WHD_JOB_ID_CONFLICT`; retrying an unfinished identity returns
`WHD_JOB_RECOVERY_REQUIRED` and **does not render a second batch**. A
completed result may be replayed unchanged only if its persisted receipt
digest and all Worker-owned artifact file SHA256/size/mtime evidence still
match; missing, changed or symlinked artifacts require recovery. An export
cannot record completion with zero verified physical artifacts. A changed
transport-only `request_id` cannot change job identity.

An **additional private W-06 output-directory lease seam** reserves every
Worker-selected, pre-existing absolute destination directory in one SQLite
`BEGIN IMMEDIATE` transaction. Paths are locally canonicalized and sorted,
and each is exclusively held by a single unfinished export job across process
restarts. The SQLite reservation also pins the actual directory `st_dev`
and `st_ino`; replacing a destination with a new directory at the **same
path** refuses `WHD_JOB_RECOVERY_REQUIRED` rather than authorizing new
customer files. Older persisted leases without a matching physical-directory
witness fail closed until trusted journal recovery. A collision fails with
`WHD_OUTPUT_PATH_LOCKED` **without acquiring a partial batch**. A completed job releases its leases in the **same durable
database transaction** as its immutable result record. Failed or interrupted
jobs do not release leases on timeout or restart. This deliberately locks the
whole output directory, not just a filename, so two different jobs cannot
stage separate files into the same batch destination concurrently.

A **private W-06 precommit stage snapshot** now records a verified original
output file proof (or its original absence) alongside each separately saved
staged DXF's SHA256/size/mtime in the same Worker-owned SQLite store, indexed
by the reserved export job and its RFC 8785 digest. The stage files must
belong to a direct, Worker-owned `.whd-dxf-stage-*` child of the already
exclusively leased destination, with an exact physical `.dxf` filename and
the same target filesystem; symlinks, hardlinks, unexpected destinations,
missing or altered old outputs, changed stage bytes, and a caller attempt to
override the signed `overwrite` flag are rejected. Retrying the snapshot
cannot substitute another inventory. Independent process restart readback
rehashes both stage and customer output bytes and compares exact sizes and
mtimes; it **never mutates any customer DXF**.

**Precommit is not commit:** if a staged journal exists,
`DurableJobIdentityLedger.complete` **refuses** to mark the export successful
or release its destination lease until a later W-06 durable multi-file commit
journal and recovery owner is actually implemented. This is intentionally a
fail-closed, non-public building block; neither stages nor manifest existence
prove customer manufacturing completion. Existing in-process W-04 export
still owns its own Save→Reload verifier and separate normal-exception rollback.

A further **private W-06 original-file backup proof** is available in
`original_backup_manifest.DurableOriginalBackupEvidence`. Only after the
job's per-item precommit stage evidence and physical-directory lease have
passed, it copies each **existing original customer DXF** (not the staged
new output) into a newly generated private `.whd-w06-original-backup-*`
directory on that same destination filesystem. It writes and fsyncs each
backup and directory, verifies actual SHA256/size/mtime parity with the
unchanged original, and commits an immutable, checksummed backup manifest
into the trusted SQLite store. It never moves, deletes or replaces any
customer or staged DXF, and a transport-only retry cannot rewrite a prior
verified backup. Independent process readback checks the original
precommit stage, output directory device/inode and physical backup files.
A missing/changed backup, altered customer file, untrusted path or corrupt
manifest refuses further processing.

**This is still not a durable multi-file commit or recovery feature.**
A crash before a manifest is recorded may leave a private, unclaimed
backup directory, but it cannot modify an existing customer DXF.
Incomplete jobs retain their reservation and `complete` continues to
refuse success until a real backup/replace journal with recovery semantics
is implemented and independently tested. No public capabilities turn true.

A further **private W-06 all-or-nothing multi-DXF replacement journal**
(`batch_commit_journal.DurableMultiDXFRollbackJournal`) uses the already
verified staged DXF Save→Reload evidence, output-directory inode-pinned lease,
and fsynced copies of **every existing customer original DXF**. It commits
a checksummed write-ahead intent in the trusted SQLite store **before any**
customer output rename. For `all_or_nothing` only, it then verifies each
original/staged byte proof, `os.replace`s one physical DXF at a time and
fsyncs its output directory. After all outputs match the original intent,
the existing ledger `complete` verifies **every exact final file** and
atomically records a durable success result and releases the batch lease.

If the process terminates between replacements or after the last rename but
before its success receipt, another private Worker instance can run the
explicit `recover_rollback`: verify the pinned original output directory,
immutable original backups, and that each customer output is **exactly**
either the expected old file or the expected newly staged file; otherwise
refuse recovery and retain the lock. It restores existing originals through
fsynced temporary copies and removes only new files that match the exact
staged bytes. It then fsyncs, verifies the whole batch is restored and
atomically marks `rolled_back` and releases the leases. The same job ID is
terminal; it never triggers another manufacturing attempt. The test suite
injects hard `SystemExit` at individual renames and a real subprocess
`os._exit`, followed by fresh-process rollback and byte/mtime checks.
Unexpected customer modifications or missing backup bytes **cannot** be
silently overwritten. A **second hard stop during rollback** leaves the
journal in persistent `rolling_back`, retains the output directory lease,
and is resumed by another private Worker instance only after re-verifying
all old/new DXF proofs; rollback is idempotent across interrupted restores.
Terminal `rolled_back` replay is independently checked against the
checksummed journal, pinned physical output directory and every original
customer DXF (or its expected absence); a corrupt journal or later customer
file modification returns `WHD_JOB_RECOVERY_REQUIRED` rather than blindly
reporting success or modifying customer files.

**Scope is still private:** no public W-01 Worker/export capability, no
automatic Windows EXE activation, no verified Windows UNC/junction alias
handling, user cancel/progress or Windows Gate A. It is not a certification
for unsupported Head/Tail/Indicator Box Frame or full W-04 mixed physical
manufacturing. Production wiring of the trusted Save→Reload batch, HMAC key
custody, and Windows UAT remain required before public use.

**W-06 Windows alias safety increment:** private directory reservations now fail
closed on UNC/device namespace and NTFS junction or junction ancestors (rather
than treating a resolved destination as safe). In-flight output leases also
check device/inode identity across different lexical keys, avoiding a second
job acquiring the same physical folder through another spelling. The existing
Windows Engine Runner exercises a **real NTFS junction**, alternate physical
lease keys and failure without modifying an original customer file. This is
a conservative *rejection* policy; it is not positive support for valid UNC
deployments or every DOS drive alias.

**Still not full W-06:** support for legitimate UNC/junction/drive-alias workflows, case-equivalence
require physical Gate A evidence; multi-file durable backup/commit journal,
rollback/roll-forward after interrupted `os.replace`, safe cancellation,
progress, source/key custody and recovery decision owner are not implemented.
A stuck lease must be resolved by a future trusted W-06 journal recovery,
never forcibly removed on a retry. The private ledger remains disconnected
from W-01 public `cadsplit_worker.py`; all public readback, path locking,
export and recovery capability flags remain false. No Windows EXE or formal
manufacturing release is certified.

## W-04 private authenticated Door batch → W-06 durable stage handoff (#2380)

`verified_door_finalscene.save_trusted_door_circle_finalscene_batch`
accepts an **optional Worker-owned** `durable_ledger`. Without that opt-in,
the existing W-04 private stage/Save→Reload/normal-exception rollback path
is unchanged. With it, a pre-existing, nonsymlinked trusted output directory
is mandatory; after authenticated W-03 original DXF/source/Frame recheck and
WHD FinalScene construction, the Worker reserves its immutable export job and
exclusive physical output-directory lease. The same WHD export owner stages
and independently Save→Reload verifies **every** produced DXF, calls the
source/fingerprint recheck again before commit, and dispatches the staged
physical inventory to W-06 instead of the legacy in-process commit.
W-06 records the frozen physical staged DXFs, backs up each old customer
original on the same volume, fsyncs a durable multi-DXF intent, applies
the checked renames with directory fsync and persists exact final SHA proofs
with the job's immutable success receipt and lease release in a single
SQLite transaction. A crash between renames is explicitly recoverable by
the original W-06 rollback owner, not by rerendering the job.

This is **PRIVATE and opt-in**, not a public CADSplit CLI capability. Source
document paths, resource root, installation ledger/store and HMAC key must
come from the trusted Worker and cannot be substituted by wire parameters.
Any failed precommit step with an already durable reservation needs trusted
recovery; it does not entitle the caller to steal/release the lease. Public
Worker integration, verified installation key custody, Windows path aliases
and Gate A, broader Head/Tail/IndicatorBox geometries and full mixed-kind
manufacturing remain unsupported.

## W-04 internal real DXF Save→Reload batch

The manufacturing owner now exposes an internal
manufacturing_api.save_verified_final_scene_batch_dxf path for strictly
WHD-owned PartRenderData and physical identities (up to 20). It stages
actual DXF files and verifies each saved file with the independent
manufacturing_verification.verify_saved_part_render_data_dxf owner before
committing the entire set with existing atomic rename/rollback logic.
A mandatory pre_commit_guard runs twice, before staging and after all
Save→Reload checks but before committing, to permit W-03/W-06 trusted
snapshot revalidation.

This is a *real manufacturing DXF staging seam*, **not** a public CADSplit
export. W-03/W-06 still need a trusted persisted request, key custody and
path locking; W-04 must map wire features to canonical PartSpec/FinalScene,
enforce physical inventory and factory source provenance; no external NC sink,
Windows EXE, or official X is certified here.


## W-04 wire Feature preflight (internal and non-manufacturing)

`feature_preflight.validate_wire_features_against_prepared_frame` is now
called by W-03's trusted pre-export recheck. It rejects duplicate feature IDs,
non-finite/Boolean geometry, out-of-face circles/rectangles/profiles, invalid
closed profiles, target-dimension drift, inconsistent unit scale and explicit
rotation/mirror/2×2 matrix evidence before any render or DXF stage. The
WHD-issued Frame remains authoritative; no CADSplit assertion is trusted.

**Boundary:** This only checks the *claimed* feature envelope. It does not
reopen original CADSplit DXF entities or prove the matrix was applied once,
and cannot manufacture a source feature or enable public `prepare/export`.
The outstanding W-04/W-06 source verification, canonical PartSpec mapping,
worker-owned job custody/path locks and Windows Gate A are still mandatory.


## W-04 source DXF CIRCLE verification (internal, read-only)

`source_circle_verification.verify_trusted_original_dxf_circles` now reads
**one original DXF byte snapshot** from a **Worker-owned trusted path** and
checks the exact `source_document_sha256` bound at prepare. It parses that
same snapshot, resolves an original **modelspace CIRCLE handle**, verifies
DXF `$INSUNITS` (mm/inch only), checks the 2D plane, applies the explicit
2×2 matrix and unit conversion **exactly once**, and compares real center
and radius against the finished-face wire claim (1e-6 mm). A source handle
cannot be reused for another Feature in the same item. Altered bytes,
missing paths, symlinks, absent handles, wrong units and mismatched geometry
fail the **entire trusted W-03 export precommit recheck** with
`WHD_SOURCE_UNVERIFIED`. The source file path is supplied only through
the trusted internal `source_documents` map, never from CADSplit JSON.

**Explicit limits:** this evidence is CIRCLE-only and limited to direct
modelspace planar entities and text DXF readable as UTF-8; rectangles,
profiles, INSERT/transformed block contents and unknown source planes
remain fail-closed until their specific certified adapters exist.
The wire's `source_geometry_sha256` does **not** currently specify an
interoperable canonicalization recipe, so this gate does not claim that
digest is verified. The full original **document bytes** hash and actual
source entity geometry are checked; no source receipt is persisted by
this read-only helper. The public Worker/EXE remains disabled; W-06 must
own durable source/path/key custody and commit locking, and W-04 must map
verified Feature geometry to canonical WHD PartSpecs/FinalScene.


### W-04 WHD-native Door CircleFeature handoff (internal)

On successful source-byte/hash/CIRCLE-handle matching, the same verification
owner returns a tuple of **WHD `CircleFeature` instances**, each with
`FeatureAnchor.ABSOLUTE_FINISHED_FACE`, the source-attested mm center,
`diameter=2*verified_radius_mm` and WHD `CUTTING`. This only supports
`process=THROUGH_CUT`; `BLIND_HOLE` and `MARKING` deliberately fail closed
until their fabrication classification and source-layer acceptance exist.
WHD's existing `DoorPartSpec(features=..., feature_space="finished_face")`,
`_door_features_for_legacy_engine` and `manufacturing_api.generate_part`
remain the sole owner of finished-face → unfolded geometry and DXF output.
A permanent test uses a real original source DXF, W-03 recheck, this typed
handoff and a real WHD Door DXF reloaded with ezdxf. This is an internal
partial W-04 acceptance, **not** a packaged Worker or a production release.


**Vault baseline Door DXF coordinate acceptance (2026-10-29, #2379):**
`manufacturing_api.generate_part` delegates to WHD's
`ae.export_stretched_door_dxf`, which maps a verified finished-face
`CircleFeature` onto the unfolded Scene and **mirrors the entire Scene
on the unfolded X axis before serializing DXF**. The independent disk-DXF
regression therefore derives the authoritative unfolded width from WHD's
`get_stretched_door_data(...).params["total_width"]` and compares the
persisted circle at `x=total_width-pre_export_x`, while retaining the
original Y/radius. Comparing the unmirrored internal Feature coordinate
to the final DXF is a false RED. This does not change source geometry,
WHD's mirror policy, PartSpec, or any CNC/DXF manufacturing formula.


## W-04 authenticated Door FinalScene batch handoff (internal only)

`verified_door_finalscene.save_trusted_door_circle_finalscene_batch` closes
one **in-process** W-03 → W-04 gap. The caller supplies original Worker-owned
prepare request/receipt and HMAC key, original source DXF paths, pinned engine
identity and Registry/baseline resource root. The module first rechecks the
entire immutable prepare/Frame/source envelope. It derives each DoorPartSpec
from **the same W-03 policy-based adapter**, then reopens original DXF CIRCLE
entities and creates only `THROUGH_CUT` WHD CircleFeatures with an internal
source marker. The WHD-native scene builder must preserve the exact feature
center, radius and CUTTING layer before any output directory is created.
The batch then goes through the existing `save_verified_final_scene_batch_dxf`:
all parts staged, independently Save→Reload-verified and guarded by W-03
**before staging and again before commit**; a source SHA change at the second
guard rejects the whole batch and preserves previous target DXFs. No per-part
partial mode or original-source-free Door items are accepted.

**Do not infer orientation from legacy `generate_part`:** the direct Door
exporter mirrors X during its own serialization. The canonical FinalScene
batch accepts WHD's pre-export drawing scene and independently tests its
Saved/Reloaded CIRCLE coordinates. The two APIs have different DXF coordinate
views; no second CADSplit mirror has been added.

**Not yet usable as the public `export` operation:** this helper assumes
trustworthy prepared-state and source-file custody supplied by an eventual
W-06 Worker, which must still implement HMAC key protection, persistent job
journal, output-path locks, cancellation, recovery and response manifest.
The wire's `source_geometry_sha256` has no portable per-entity hash recipe;
only the complete pinned source document bytes and measured direct planar
CIRCLEs are verified. Rectangles, profiles, Head/Tail and Indicator remain
fail closed. There is no Windows EXE release or manufacturing certification.


### W-04 source-attested rectangular LWPOLYLINE subset (#2379)

The internal W-03 precommit original-source adapter additionally accepts a
**direct modelspace closed LWPOLYLINE with exactly four straight vertices,
zero constant/per-vertex stroke width, no bulges (including tiny nonzero arcs),
zero DXF extrusion thickness (including tiny nonzero values),
positive XY plane and explicit DXF mm/inch header**. It independently
reads the same pinned original document SHA, resolves the exact entity handle,
applies the declared matrix and unit scale once and proves all four vertices
are an orthogonal rectangle; neither a claimed bounding box nor a matching
center alone suffices. It compares transformed center and width/height with
the rectangle wire's explicit quarter-turn. Only `THROUGH_CUT` is allowed.
The internal WHD-owned `RectFeature` stores source-derived finished-face
bounds. Canonical `ResolvedRect` verifies the actual closed CUTTING contour
in FinalScene; the existing batch boundary performs independent DXF reload
and precommit source recheck. **Curved/open LWPOLYLINE, POLYLINE,
INSERT, arbitrary multi-entity profiles, source subgeometry SHA and public
Worker export remain unsupported.**
Original-source CIRCLEs also require zero DXF extrusion thickness; nonzero
3D-extruded source geometry fails closed before staging.

The internal source-derived RECT FinalScene check compares the **ordered
closed CUTTING edge cycle**, not just four matching corners or bounding
box. Cyclic start shifts and reverse winding are equivalent; a crossed
bow-tie order fails before any output is staged.


### W-04 source-attested simple LWPOLYLINE PROFILE subset (#2379)

In addition to original DXF circles and four-corner rectangles, the **internal**
Door-only authenticated source adapter can admit a direct modelspace closed
LWPOLYLINE as a simple polygon PROFILE with **3–256 vertices**. Original
DXF file SHA and exact handle are mandatory. Every segment must be straight,
zero constant/per-vertex stroke width, zero extrusion thickness, planar +XY,
with an explicit mm/inch header. After applying the declared source-to-mm
scale and 2×2 matrix/translation exactly once, the entire source polygon must
be simple, nondegenerate, and match the wire's `closed` point cycle in both
coordinates **and edge order**. Only cyclic start shifts and reverse winding
are equivalent; matching bbox, center or unordered point sets is insufficient.

The WHD-owned `ProfileFeature` is constructed from **actual source vertices**,
not from the claimed wire polygon. Its final CUTTING `PolylinePrimitive` is
compared to the same full closed edge sequence after WHD's finished-face
mapping, before the batch's independent DXF Save→Reload, precommit source
recheck and staged atomic replacement. Open/arc/width-bearing polylines,
legacy POLYLINE/INSERT, per-entity source geometry hash certification and
public Worker/EXE export are still not supported. This is **not** W-06 durable
job ownership or W-05/07 Windows Gate A acceptance.


### W-03 twenty-item mixed Door / Indicator Small Door preparation evidence (#2378)

The private `prepare_trusted_door_batch` can process **up to 20 authenticated
prepared physical identities** with both supported W-03 kinds in one order-
preserving request. Each actual `DoorPartSpec` is re-derived by the WHD owner;
the small-door subset is linked to WHD's shared indicator source and policy.
The existing job/token binds **all** rows, their distinct source references,
physical part IDs, Frame IDs, per-item digests and Registry/physical baseline
contents. Recomputing the request on export must reject a changed item or
either kind's relevant baseline **for the entire prepare batch**.

This tests only the W-03 prepare and stale recheck boundary: it **does not**
enable W-04 20-kind mixed manufacturing, per-part output, a durable W-06 Worker,
public W-01 commands or a Windows EXE.


## W-06 private Windows HMAC key custody (#2380)

The existing W-03 `prepare_token` uses HMAC, but the approved trusted
Worker installation must own its key; neither CADSplit JSON nor the EXE,
`config.ini`, GitHub artifacts or customer DXFs may contain that plaintext.

`integration_cli.worker_key_custody.load_installation_key` now supplies the
**private** Windows-specific custody implementation. On trusted installation
bootstrap only, `initialize=True` generates a random 32-byte secret and
encrypts it with **current-user Windows DPAPI** (`CryptProtectData`, UI
disabled). The encrypted record is stored under that user's
`%LOCALAPPDATA%/WHD/Engine/install-<installation-id-SHA256>/` with
exclusive creation; it is never baked into PyInstaller output, sent to the
external client or written into WHD user config. Later processes use
`initialize=False` to read the same authenticated key without rotation.
Tampered, missing, cross-installation, hard-linked or reparse-point custody
fails closed as `WHD_PREPARE_KEY_UNAVAILABLE`. Windows CI calls the actual
DPAPI APIs and verifies that a separately started Python process obtains
the same HMAC result; it does not use a crypto mock or print secret bytes.

This is **private custody only**: it does not yet assign a trusted Worker
installer/identity lifecycle, activate persisted W-03 prepare receipts via the public CLI,
support a service account or a remote UNC store, or
make W-06 keys recoverable across Windows user-profile changes. Normal
`cadsplit_worker` public `prepare/export` stays disabled; no machine
certification, Gate A, or `/推推` is implied.

## W-06 original Prepare custody in existing durable ledger (#2380)

Private `DurableJobIdentityLedger.prepare_and_persist` now reserves a W-03
`(client_installation_id,job_id,prepare)` identity **before** any WHD
Prepare work. Its actual `prepare_trusted_door_batch` canonical output,
together with the exact original request, is HMAC-sealed using the Worker-owned
installation key and committed **in the same SQLite transaction** as the
immutable job result. Repeated completed requests (even with a different
transport-only `request_id`) read the original receipt, not rerender.
A crashed/incomplete prepare remains `WHD_JOB_RECOVERY_REQUIRED`.

`load_trusted_prepare` checks the HMAC, job digest, and identical persisted
result on every reopen; legacy completed rows without the original attested
request never gain export authority. `recheck_persisted_prepare_for_export`
retrieves that persisted pair and invokes the existing W-03 source/Frame/
resource/feature recheck. Neither export JSON nor a guessed token can inject
a substitute original Prepare receipt. No customer DXF is written by these
methods. Real WHD baseline/Registry and two-Door tests cover restart,
tamper/recomputed plain SHA, collision and export recheck.

This is **private** and relies on a trusted caller to select the installation
store, actual resource paths, engine build identity and DPAPI-sourced key.
Public `cadsplit_worker` remains disabled until W-03/W-04/W-06 key owner,
source custody, cancel/progress and W-07 Gate A are complete.

## W-01 → W-03/W-04/W-06 private Worker dispatch (#2375/#2380)

The real `integration_cli.cadsplit_worker._execute_request` now has an
**in-process-only** `trusted_context` injection seam. Only a trusted
installation owner may construct `TrustedWorkerExecution` from its
preexisting resource root, W-06 SQLite store, trusted output folder,
trusted per-item original-DXF file mapping, source/build SHA and Worker HMAC
key loaded via Windows DPAPI. No CADSplit JSON field, environment flag, CLI
parameter, or `--private` command can construct this context.

When this trusted context is injected, the *same Worker request entry*
validates schema 1.1 and canonical request digest, executes WHD-owned
`prepare_and_persist` and (for Export) loads the authenticated original
W-03 Prepare request/receipt, rechecks real Registry/Frame/source DXF,
then invokes W-04 real FinalScene Save→Reload with W-06 physical directory
leases, original backups, durable multi-DXF journal, job receipt and
`progress.json`. The Worker handles immutable replay by rehashing actual
manufactured DXF bytes without rendering again; a restarted/unfinished
job is not an authorized retry. A private export receipt retains
`manufacturing_verified=false` and is **never** exposed as a public
schema-1.1 `success` response.

The shipped `WHD-Engine.exe` public parser still accepts **exactly**
`capabilities`, `prepare`, `export`; `main()` never supplies
`trusted_context`, so manufacturing flags stay false and the ordinary
request path continues to decline manufacturing. Windows CI exercises
the actual private request dispatch, real WHD original DXF → Prepare →
durable Export → Save→Reload DXFs, DPAPI key restart and no-rewrite replay.
Windows also continues to smoke-test the installed EXE from a Chinese
path with public `prepare/export` disabled.

**Not Gate A**: an authorized installed Worker bootstrap, trusted CADSplit
source-document mapping and an approved public manufacturing certification
still need independent end-to-end installation acceptance before this
private execution seam may be made public.

## W-06 actual private installed WHD-Engine.exe entry (#2380)

`WHD-Engine.exe` has an **undocumented internal**
`_private_installed prepare|export --installation-id ... --request ...
--response ...` path. This entry is Windows-EXE-only, not the ordinary
CADSplit CLI and not a certified manufacturing feature. It refuses all
source-only calls and missing/invalid installed custody. The trusted
installer-only Python API `private_worker_installation.provision_private_installation`
pins an immutable, HMAC-authenticated source-document map, output folder,
private SQLite store and exact built EXE SHA256. It stores this under the
current Windows user's protected installation profile, using the existing
DPAPI-protected Worker signing key. A regular CLI request cannot provision
these authorities or set a Worker key/path through JSON, env or arguments.
Re-provisioning and tampered installation records fail closed.

The private EXE loads that installed custody, verifies the actual packaged
Engine/Registry/resources, and calls the same W-01 → W-03/W-06/W-04
`_execute_request(..., trusted_context=...)` path as the real private
integration tests. Windows CI additionally **spawns the actual onedir EXE**
after private trusted setup, executes source-attested Prepare, verifies
the persisted original W-03 HMAC receipt after process restart, verifies
idempotent replay, and rejects an unprovisioned installation ID.

This is **not the public CADSplit integration Gate A**. The installer is
not available to external clients, public `prepare/export` and capability
flags remain disabled, and a private successful Prepare is not certification
of completed manufacturing. No customer configuration UI, credential entry,
or automatic installation bootstrap is created.

## W-06 private progress.json from immutable Worker evidence (#2380)

`integration_cli.worker_progress.PrivateWorkerProgress` supplies a
**non-authoritative projection** of the original trusted W-06 SQLite job,
cancel, staged-batch and multi-DXF replacement journal. The Worker alone
chooses its trusted private installation-store root. An atomic, fsynced
`progress/<SHA256 of client+job+operation+digest>/progress.json` is
published at private Prepare claim/verified receipt, cancellation, real
W-04 Save→Reload stage, replacement armed/applying/applied and final
verified export completion. Each write is serialized under SQLite
`BEGIN IMMEDIATE` to avoid two Worker processes publishing out of order.
A startup/restart can always call `read(request)` to derive the current
status directly from SQLite; it **never reads a user-modified progress file
as authority**. Missing or corrupt DB records and wrong request digests
fail closed.

An unfinished/mid-replace/cancelled job cannot produce 100%, a
`manufacturing_verified=true` claim or any output authorization.
`prepared` at 100% means only that this **Prepare operation** has a valid
persisted W-03 HMAC receipt, requiring the Worker-only `worker_key`
on read/publish; it does **not** mean a manufactured DXF exists. An Export
is 100% only after existing W-06 `complete` and true physical DXF
attestation readback. A corrupted customer DXF makes the progress read
fail closed, not return a cached 100%. A crashed `applying` journal
reports `recovery_required`; no automatic replay, rollback or user file
modification is performed by the projection.

This is private Worker progress only. It is **not** a public CADSplit
progress/cancel API, an independent signing authority, or complete W-06
Gate A. The existing public `prepare/export` remain disabled.

## W-06 private durable cancellation safe points (#2380)

The trusted Worker (never CADSplit wire JSON) may call
`DurableJobIdentityLedger.request_cancel(original_request)` after a private
job is claimed. A SQLite WAL/FULL-sync `job_cancel_intents` row pins its
**original canonical digest**; the intent survives process restart, a second
identical cancel is idempotent, and a changed job digest is refused. Private
Prepare and Export check the flag before publishing an immutable success
receipt. W-04 also checks at its source/Save→Reload safe points. The
multi-DXF `DurableMultiDXFRollbackJournal.arm` atomically checks the same
cancel row under `BEGIN IMMEDIATE` before writing any replacement intent.
After arming, a cancel request is refused as recovery-required rather than
interrupting an applying multi-file replacement. A cancelled, unfinished
job is **not automatically rerun**; recovery owns terminal resolution.
This only adds a private cancellation seam; no public cancel CLI,
`progress.json` or full W-06/Gate A claim is made.

## W-05 private Windows Engine onedir candidate (#2381)

The real Windows x64 **separate** `WHD-Engine.exe` candidate is built and
smoke-tested in `.github/workflows/whd-engine-private-windows-exe.yml`.
It is not the WHD GUI `WHD.exe` and does not reuse the GUI release asset.

- PyInstaller builds from **exact PR HEAD**; includes the worker schemas,
  `ae_engine`, the actual `基準檔` DXFs and Certified Registry, and
  packaged factory policy `config.ini` (no customer file modification).
- **After** EXE creation a versioned `WHD_ENGINE_BUILD.json` is written
  alongside the binary. It pins `engine_commit`, actual EXE SHA256,
  the real Registry bytes, sorted baseline DXF inventory and policy bytes.
  At each packaged invocation, missing/modified EXE, Registry, baseline,
  policy or manifest **fails closed with exit 4**; there is no Git fallback
  or manufactured source SHA. Source-only CLI keeps its previous identity.
  The manifest is integrity/readback evidence, **not a code signature**;
  use the trusted GitHub artifact digest for authenticity.
- Windows CI actually runs the packaged binary from a **Chinese/space**
  installation path and a different CWD. `capabilities` reads the real
  package identity and resource hashes, but all public manufacturing flags
  and supported part kinds stay **disabled**. Schema-valid 20-item
  `prepare` and `export` return
  `WHD_OPERATION_NOT_IMPLEMENTED` (exit 3) without DXF output; changing
  the bundled Registry causes a refusal.
- The Windows runner now additionally compiles the existing GUI `WHD.exe`
  **from the same exact source checkout**, starts the actual GUI process,
  and independently hashes both binaries. `SAME_SOURCE_ENGINE_GUI.json`
  records the common source SHA and both actual binary SHA-256 values.
  The two candidates are uploaded separately and are **not an official X
  Release**, nor an assertion of full GUI 2D/3D or manufacturing UAT.
- This is still an **internal W-05 package seam**. The combined official
  same-release GUI+Engine delivery, durable Worker key custody, trusted
  public handlers, Windows junction/UNC/policy overrides and cross-ticket
  Gate A remain pending. No factory NC sink, public manufacturing
  certification or formal `/推推` is implied.

