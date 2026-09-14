# #206 / T2 Checkpoint

- Parent: #203
- Depends on: #205 CLOSED / completed
- Current role: T2 實作者
- Baseline: `cleanup/2d-3d-sync @ 82d1763f02ab44d6e6138b3d626193da87550687`
- Branch: `test/issue206-characterization-20260914`

## Approved seams
- `_corner_preview_canvas_point`
- `_corner_preview_flip_y_for_target`
- `_project_toolbar_presentation`
- `render_drawing_scene`

## Completed
- fresh branch from exact production baseline;
- Python測試實務 and tdd reread;
- global pitfall + skill rules references reread;
- primitive public contract in `ae_engine.sheetmetal_drawing` reread;
- T2 preflight evidence recorded;
- preflight-only run `34807337493` GREEN before test creation;
- characterization test added at `tests/test_issue206_gui_modularization_characterization.py`;
- run `34807382244` failed during collection because temporary QA harness lacked `matplotlib`; no characterization assertion executed and production drift gate was GREEN;
- harness-only dependency fix added `matplotlib`; neither test expectations nor production changed;
- final characterization run `34807475278 @ f9490e714e6e3587c4e895e001b50c1ff465c736` GREEN;
- exact focused result: **13 PASS / 0 FAIL**;
- `config.ini` before/after SHA invariant GREEN;
- protected `基準檔/**` before/after manifest invariant GREEN;
- production-source branch drift gate GREEN;
- artifact `10333821511` captured;
- temporary workflow removed at `c9c2f6cf255808e7c8d6b5a357795a7ebe3b38dd`.

## Pending
1. tested→cleaned and production→cleaned drift audit;
2. transfer to total-control review and close #206 if diff is test/evidence-only;
3. carry the permanent characterization contract into #207/T3 fresh branch before move-only extraction.

## No-go maintained
- no production code modification;
- no expected value fed back into production;
- no mock of manufacturing geometry; renderer characterization uses explicit public primitives and a recording Canvas boundary;
- no HOLD candidates included.
