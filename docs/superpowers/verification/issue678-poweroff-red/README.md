# Issue #678 — Power-Off Requirement RED Durable Anchor

Status: repository-owned evidence candidate for WI-0.

Baseline authority:
`cleanup/2d-3d-sync @ 87eb35b3f5ae5211673c941cb56c4c4343fa5405`

This directory preserves the exact approved local probe sources/raw outputs/manifests from the
human-approved RED gate and adds a portable reproduction wrapper.

Approved surface:
- v4 gap characterization: R0, R0A, R1, R2, R7, R8, R9, R11.
- v5 behavioral coverage: 28 nodeids covering T3=5, T4=6, T5=3, T6=8, T10=6.
- Adversarial sentinels: always-SAFE and always-NOT-SAFE.

The files under `approved/` are preserved evidence bytes. Their original hashes are recorded in
`provenance.json`.

Portable replay:

```bash
python docs/superpowers/verification/issue678-poweroff-red/reproduce.py
```

Optional explicit repository root:

```bash
python docs/superpowers/verification/issue678-poweroff-red/reproduce.py --repo-root /path/to/whd
```

`reproduce.py` runs only against the immutable baseline SHA embedded in the approved probes. It
copies the preserved probes into a temporary directory, patches only machine-local path bindings,
runs the v4/v5 matrix runners, and exits non-zero unless all intended RED and adversarial failures
are reproduced. It performs no production mutation.

WI-0 changes evidence only; it must not change WHD production behavior.
