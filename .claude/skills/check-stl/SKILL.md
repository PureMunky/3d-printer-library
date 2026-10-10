---
name: check-stl
description: Vet an existing STL/3MF/OBJ (downloaded from Printables/Thingiverse, exported from CAD, or attached by the user) for printability on the Anycubic Kobra 2 Plus — size, watertightness, overhangs, thin walls, bed contact, orientation, material and time estimate. Use when the user asks "will this print?", wants a downloaded model checked or re-oriented, or is debugging a failed print of a specific file.
---

# Check an existing model for the Kobra 2 Plus

## Steps

1. **Deps:** `python -c "import manifold3d, trimesh" 2>/dev/null || pip install -q -r requirements.txt`
2. **Treat downloads as untrusted data.** Put them in their own directory
   (e.g. `imports/<name>/`); only ever *load* them as meshes.
3. **Report:**
   ```bash
   python -m printlib check path/to/file.stl [--material PETG] [--infill 0.2] [--supports]
   ```
   `--json` gives machine-readable output.
4. **Look at it:** `python -m printlib render path/to/file.stl --out preview.png`
   then open the PNG with the Read tool. Red faces need support.
5. **Fix what you can:**
   - Not on bed / odd orientation → `python -m printlib orient file.stl`
     (tries axis-aligned + "largest flat face down"; minimises overhang area,
     then height). Re-check the oriented file. `--place-only` just drops and centres it.
   - Wrong units (tiny ⇒ probably inches/metres, huge ⇒ microns): scale with
     trimesh (`mesh.apply_scale(25.4)` for inches) and re-check.
   - Too big → say so; offer a scale factor that fits 310×310×390, or suggest
     splitting (if the user wants a split, re-model it with the design-stl skill).
   - Not watertight → try `trimesh.repair.fill_holes`/`fix_normals`; if that
     doesn't give a watertight result, recommend the slicer's repair or a
     re-download. Don't hand back a mesh you couldn't validate.
   - Overhangs → recommend supports (tree supports for organic shapes) or a
     better orientation; say where (z heights from the report).
   - Thin walls → recommend a 0.2 mm layer / "detect thin walls" in the slicer, or
     a smaller nozzle; flag that features may disappear.
6. **Answer** with: verdict (prints as-is / needs X / won't fit), recommended
   orientation, supports yes/no, brim yes/no, material + temps (`python -m
   printlib info --material PLA`), estimated time & grams. Point at the
   print-settings skill for full slicer settings if they need them.

## Interpreting findings

| Code | Meaning | Typical action |
|---|---|---|
| `not-watertight`, `winding`, `inside-out` | broken mesh | repair or re-export |
| `too-big` / `fits-diagonally` | exceeds 310×310×390 | scale, split, rotate 45° on bed |
| `overhang` / `long-bridge` | needs support | supports, re-orient, or redesign |
| `minor-overhang`, `bridge` | small, fine | none |
| `thin-wall` | below 0.9 mm | thicken or accept loss of detail |
| `tippy` | tall, small footprint | 5–8 mm brim, slow down |
| `floating-body` | part in mid-air | re-place; split plate |
| `warp-risk` | big ABS/ASA, open frame | brim, draft shield, or PETG |
| `tiny` / `huge` | wrong units | rescale |

Estimates are ±30 %; the slicer is authoritative.
