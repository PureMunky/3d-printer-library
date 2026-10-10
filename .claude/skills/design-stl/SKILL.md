---
name: design-stl
description: Design a new 3D-printable part and produce a verified STL for the Anycubic Kobra 2 Plus. Use whenever the user asks to make, model, design, or generate a printable object (bracket, box, holder, organizer, name tag, replacement part, gift, etc.) or to change the dimensions/features of an existing model in models/.
---

# Design a printable STL for the Kobra 2 Plus

You write models as **parametric Python** (manifold3d via `printlib.shapes`),
build them to STL, then *prove* they print by running the checker and looking
at the rendered preview. Never hand the user an STL you haven't checked and
looked at.

## 0. Setup (once per session)

```bash
python -c "import manifold3d, trimesh" 2>/dev/null || pip install -q -r requirements.txt
python -m printlib info          # printer limits, design rules, fit clearances
```

## 1. Pin down the requirements

Before modeling, make sure you know (ask only for what you can't sensibly default):

- **What it does & what it touches** — mating parts, screws, the thing it holds.
  Get real measurements in mm; if the user gives "about", add margin.
- **Critical dimensions** vs. ones you can choose.
- **Load / environment** — decorative (PLA), outdoors or hot car (PETG/ASA),
  flexible (TPU).
- **Hardware** — screw size (M2–M6 in `shapes.METRIC`), magnets, inserts.

State your assumptions in the model's META `notes`.

## 2. Scaffold

```bash
python -m printlib new <slug> --title "Human title"   # kebab-case slug
```

This creates `models/<slug>/model.py` (META, PARAMS, `build(**params)`) and a
README. Every dimension a user could want to tweak goes in `PARAMS`.
`build` returns one `Manifold`, or a dict `{"part": Manifold, ...}` for
multi-part prints (one STL each).

## 3. Model with the toolkit

Import from `printlib.shapes` (read it — it's short) and `printlib.profile`:

| Need | Use |
|---|---|
| Rounded box on the bed | `box(x, y, z, r=, bottom_chamfer=P.design["first_layer_chamfer"])` |
| Any 2D outline → solid | `polygon(pts)`, `rect`, `circle`, `text2d` → `extrude(cs, h, bottom_chamfer=)` |
| Vertical hole that measures true | `hole(d, depth)` (adds `hole_compensation`) |
| Horizontal hole, no support | `teardrop(d, length, axis="x"/"y")` |
| Mating parts | size by `P.tol("press"/"snug"/"slide"/"loose"/"print_in_place")` **per side** |
| Screws / nuts / inserts | `screw_hole("M3", depth, counterbore=3)`, `nut_trap("M3")`, `insert_hole("M3", 6)` |
| Text / labels | `label_face(solid, text2d("Hi", 8), "+z"/"-y"/…, raised=False)` |
| Booleans & placement | `+`, `-`, `union`, `difference`, `.translate`, `.rotate`, `on_bed`, `arrange` |

### Kobra 2 Plus design rules (from the profile — don't hard-code)

- **Fit:** usable volume 310 × 310 × 390 mm. Larger → split into parts with
  alignment pins/dovetails, or ask the user to scale.
- **Walls:** ≥ `recommended_wall` (1.6 mm) for anything structural, never
  below `min_wall` (0.9). Prefer multiples of the 0.45 line width.
- **Features:** pins, ribs and text strokes ≥ `min_feature` (0.8 mm). Raised
  text ≥ ~6 mm tall bold; engraved text can be smaller (~4 mm).
- **Overhangs:** ≤ 45° from vertical. Replace flat ceilings with 45° chamfers,
  use teardrops for horizontal holes, and put round holes vertical when you can.
- **Bridges:** ≤ `max_bridge` (15 mm) unsupported span.
- **Bed face:** design a big flat face down. Chamfer (not fillet) bottom
  edges by 0.4 mm to hide elephant's foot — fillets on the bed edge overhang.
- **Heights:** make thicknesses multiples of the 0.2 mm layer height when it
  matters (snap tabs, lids, emboss depth `emboss_height` = 0.6).
- **Strength:** layers are weakest in Z. Orient so loads run along layers;
  e.g. print brackets lying on their side, not standing up.
- **Print-in-place / snap fits:** use `print_in_place` clearance (0.45) and
  check with the tolerance-test model if fits matter.

## 4. Build, check, look

```bash
python -m printlib build <slug>                    # writes STL(s), preview*.png, PRINT.md
python -m printlib build <slug> --set width=90     # try a variant
python -m printlib build <slug> --out scratch/x    # variant without touching committed files
```

Then:

1. **Read the report.** `ERROR` = must fix. `WARN` = fix, or consciously
   accept and record why in META notes (e.g. set `"supports": True` when
   supports are genuinely the right call). `INFO` = fine.
2. **Open every `preview*.png` with the Read tool** and actually look:
   right shape? features where expected? text readable and not mirrored? Red
   faces = overhangs that need support. Use
   `python -m printlib render file.stl --views bottom,iso-back,left` for other angles.
3. Iterate until RESULT is PRINTABLE with no unexplained WARNs.

## 5. Finish

- Fill in `models/<slug>/README.md`: what it is, how to assemble/use, the
  parameters that matter, hardware list.
- Commit `model.py`, the STL(s), `preview*.png`, `PRINT.md`, `README.md`.
- Add the model to the table in the top-level README.
- Tell the user: STL path(s), print orientation, material, estimated time and
  grams (from PRINT.md), and anything to watch (supports, brim, fit to test).
- When they want to print it, run `python -m printlib bundle <slug> --name <job>`
  and send them `bundles/<job>.zip` (the zip is gitignored; don't commit it).

## Pitfalls

- **Use `shapes.offset(cs, d)`, never `cs.offset(...)`.** Raw Clipper offsets
  can leave vertices ~1e-8 mm apart that become zero-length edges and tear
  the exported STL (the check reports `not-watertight` / hundreds of
  `floating-body`).
- **Never let booleans meet tangentially or flush** (a circle touching a
  box face, cutters ending exactly on a face). Sink joined shapes ~0.3 mm into
  each other and overshoot cutters.
- **Same for 3D joins:** a rounded part end grazing a curved wall (handle
  meeting a pan) leaves micro-edges. Run the joined part well into the body
  and cut hollows *after* the union.
- **Many small parts on one plate:** `shapes.pack(parts, width)` shelf-packs
  them and refuses plates that don't fit the bed.
- **Raised text strokes must clear `min_wall`:** small labels (< ~7 mm) need
  `offset(label, 0.15–0.2)` or the thin-wall check (rightly) warns.
- `build` checks the STL **as written to disk**, the way a slicer reads it. If it
  fails there but the in-memory solid looks fine, look for micro-edges.

- `Manifold.cylinder` / `extrude` start at z=0; `teardrop` and cutters are
  centred/overshoot — always `on_bed()` the final part (build does this too).
- Subtract cutters that **overshoot** the faces (`hole` does) or you get
  zero-thickness skins.
- A part that's fine in PLA may be too weak in TPU or warp in ABS — the
  checker warns on big ABS/ASA parts.
- Can't make something watertight from imported geometry? Rebuild it from
  primitives instead of patching triangles.
