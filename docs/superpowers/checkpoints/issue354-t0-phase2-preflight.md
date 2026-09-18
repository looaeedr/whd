# Issue #354 T0 — Phase 2 preflight

Fixed semantic baseline: `7a8b87f8cbb50a34c5038aa196fa137b301702a4`

This checkpoint is intentionally seeded before terminal classification so the
branch-only T0 workflow has a deterministic trigger path. Final inventory and
classification are appended only after the machine gate reaches terminal.


Classification rerun trigger:
- gate commit: `9c0a369734b20760cfc5674dc7753da598090453`
- requires state ownership + wiring lifecycle + Tk-pump candidate classification
