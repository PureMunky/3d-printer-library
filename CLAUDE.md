# 3D printer library — Anycubic Kobra 2 Plus

A library of parametric, printable models plus `printlib`, a small Python
toolkit for designing and verifying STLs for **one printer: the Anycubic
Kobra 2 Plus** (320×320×400, 0.4 mm nozzle, direct drive, PEI bed, open frame).

## Layout

- `printlib/` — the toolkit
  - `profiles/kobra2plus.yaml` — printer limits, design rules, fit clearances,
    materials. **Single source of truth for numbers**; read from it, don't hard-code.
  - `shapes.py` — manifold3d modeling helpers (boxes, chamfers, holes,
    teardrops, metric hardware, text, face labels)
  - `check.py` — printability report; `orient.py` — auto-orientation;
    `render.py` — PNG previews; `estimate.py` — grams/time; `build.py` — model builder
- `models/<slug>/` — one dir per model: `model.py` (META, PARAMS, `build()`),
  generated `*.stl`, `preview*.png`, `PRINT.md`, and a hand-written `README.md`
- `.claude/skills/` — `design-stl` (new models), `check-stl` (vet existing
  files), `print-settings` (slicer settings & troubleshooting)
- `tests/` — pytest; every model must build to a PRINTABLE report

## Commands

```bash
pip install -r requirements.txt          # done automatically in cloud sessions
python -m printlib info                  # printer profile
python -m printlib new <slug>            # scaffold a model
python -m printlib build <slug> [--set k=v] [--out dir]
python -m printlib check file.stl        # printability report
python -m printlib render file.stl       # PNG preview
python -m printlib orient file.stl       # best print orientation
python -m printlib bundle <slug>[:part] ... --name job   # zip for printing → bundles/
python -m pytest -q
```

## Rules

- Units are mm, +Z up, bed at z=0. Every part ends `on_bed`.
- Don't deliver an STL without running the checker **and viewing the preview
  PNG** (Read tool). Fix all ERRORs; fix or document every WARN in META notes.
- Generated files (`*.stl`, `preview*.png`, `PRINT.md`) are committed but
  never hand-edited — change `model.py` and rebuild.
- Scratch variants go in `scratch/` (gitignored) via `--out`.
- Printing hand-off: the printer is on Anycubic Cloud, which this cloud session
  can't reach (and has no official API). Deliver jobs with `printlib bundle`
  and send the zip to the user; they slice/send in Anycubic Slicer Next or the app.
- Run `python -m pytest -q` before committing; add a test when changing `printlib`.
