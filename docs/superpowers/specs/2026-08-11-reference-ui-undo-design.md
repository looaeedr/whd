# Reference UI and Undo Design

## Goal
Simplify hole reference editing so right-click is the only nine-anchor selector, keep compact X/Y distance controls and confirm/cancel attached to the active crosshair, add multi-step Undo/Ctrl+Z, and restore all pytest files under `tests/`.

## Interaction
- Remove the visible reference-anchor combobox/menu from the unified hole editor.
- Right-click a placed feature opens the nine-anchor context menu: center, top-center, bottom-center, left-center, right-center, top-left, bottom-left, top-right, bottom-right.
- The active crosshair remains visible and its distance controls move with it.
- Distance controls use a smaller font (12-13pt) and avoid the feature footprint and each other.
- The active feature confirm/cancel controls are part of the same floating reference group and move with the crosshair.
- Undo button and Ctrl+Z undo the latest committed editor action; keep at most 50 snapshots.
- Undo covers insert, delete/process toggle, move/reference edits, anchor changes, rotation, and committed round-pattern edits.
- Local cancel still restores the current edit transaction; Undo is independent and can be repeated.

## Tests
- Move every root `test_*.py` to `tests/` preserving filenames.
- Pytest discovery from project root remains green.
- Add regression coverage for no anchor combobox, right-click anchor selection, floating compact controls, Undo/Ctrl+Z and 50-step cap.
