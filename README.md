# 3D Printer Library

Printable models and tooling for an **Anycubic Kobra 2 Plus**.

Every model here is parametric Python, built to STL, and automatically checked
against the printer's limits (build volume, overhangs, bridges, thin walls,
bed contact) before it's committed — so what's in `models/` should print first time.

## Models

| Model | What | Parts |
|---|---|---|
| [calibration-cube](models/calibration-cube/) | 20 mm XYZ cube for dimensional calibration | 1 |
| [tolerance-test](models/tolerance-test/) | Peg + hole plate to calibrate press/snug/slide fits | 2 |
| [parametric-box](models/parametric-box/) | Rounded box with press-in lid, dividers, engraved label | 2 |
| [claude-buddy](models/claude-buddy/) | Pixel-art Claude mascot desk buddy with press-in eyes | 2 |

Each model folder has the STL(s), a `preview.png`, and a generated `PRINT.md`
with material, temps, estimated time/filament and the printability report.

**Print the tolerance test first** and update `tolerances:` in
[`printlib/profiles/kobra2plus.yaml`](printlib/profiles/kobra2plus.yaml) —
every model that has mating parts reads its clearances from there.

## Quick start

```bash
pip install -r requirements.txt

python -m printlib info                                   # printer limits & design rules
python -m printlib build parametric-box --set width=120 --set label=LEGO --out scratch/lego-box
python -m printlib check ~/Downloads/some-model.stl       # will it print?
python -m printlib orient ~/Downloads/some-model.stl      # best orientation
python -m printlib render models/calibration-cube/calibration-cube.stl
python -m printlib new phone-stand                        # start a new model
```

## Working with Claude

The repo ships Claude Code skills in `.claude/skills/`:

- **design-stl** — "make me a wall hook for a 12 mm dowel" → parametric model,
  STL, checks, preview, print notes.
- **check-stl** — "will this Printables download print?" → report, orientation,
  supports/brim/material advice.
- **print-settings** — slicer settings per material/purpose and troubleshooting
  failed prints on the Kobra 2 Plus.

See [CLAUDE.md](CLAUDE.md) for conventions.

## printlib at a glance

```python
from printlib.profile import load_printer
from printlib.shapes import box, hole, teardrop, screw_hole, label_face, text2d, difference

P = load_printer()
plate = box(60, 30, 5, r=4, bottom_chamfer=P.design["first_layer_chamfer"])
plate = difference(plate, screw_hole("M3", 5, counterbore=3).translate((-20, 0, 0)),
                          screw_hole("M3", 5, counterbore=3).translate((20, 0, 0)))
plate = label_face(plate, text2d("SHELF", 6), "+z")
```
