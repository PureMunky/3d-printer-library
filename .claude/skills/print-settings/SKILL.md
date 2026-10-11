---
name: print-settings
description: Recommend slicer settings (Anycubic Slicer Next / OrcaSlicer / Cura / PrusaSlicer) and troubleshoot print failures for the Anycubic Kobra 2 Plus — temperatures, speeds, layer height, walls, infill, supports, brim, retraction, material choice. Use when the user asks how to print a model, which material/settings to use, or why a print failed (stringing, warping, layer shift, poor adhesion, elephant's foot, etc.).
---

# Slicer settings & troubleshooting — Kobra 2 Plus

Source of truth for numbers: `printlib/profiles/kobra2plus.yaml`
(`python -m printlib info`, `python -m printlib info --material PETG`).
If the user has calibrated something (tolerance test, temps), update the
profile rather than overriding in prose.

## Machine facts

320×320×400 mm build (plan for 310×310×390), 0.4 mm nozzle, 1.75 mm
filament, direct-drive extruder, 260 °C hotend, 110 °C bed, PEI spring-steel
sheet, LeviQ 2.0 auto-levelling, open frame (no enclosure), up to ~500 mm/s
(≈300 mm/s is a sane fast default). Use the slicer's bundled "Anycubic Kobra 2
Plus" printer profile as the base and adjust from there.

## Getting a job to the printer

The printer is set up for remote printing through the user's **Anycubic
account**. This cloud session can't reach it, and there's no official API.
Hand off with `python -m printlib bundle <models...> --name <job>` and send the
zip; they open the STLs in Anycubic Slicer Next or the app, slice with the
stock Kobra 2 Plus profile plus the settings below, and send from there.

## Baseline profiles (0.4 nozzle)

| Purpose | Layer | Walls | Top/Bottom | Infill | Notes |
|---|---|---|---|---|---|
| Draft / test fit | 0.28 | 2 | 3/3 | 10% grid | fastest |
| Standard | 0.20 | 3 | 4/4 | 15% gyroid | default for library models |
| Strong / functional | 0.20 | 4–5 | 5/5 | 25–40% gyroid/cubic | brackets, mounts, hooks |
| Fine / display | 0.12 | 3 | 6/6 | 10–15% | figurines, text-heavy |

More walls beat more infill for strength. Orient so the load runs along layers.

## Materials

| | PLA | PETG | TPU (95A) | ABS / ASA |
|---|---|---|---|---|
| Nozzle °C | 200–215 | 230–245 | 220–230 | 245–255 |
| Bed °C | 55–60 | 75–80 | 45–50 | 95–100 |
| Fan | 100% | 30–50% | 50–70% | 0–15% |
| Speed | fast (200–300) | 120–180 | 20–40 | 120–180 |
| Retraction | ~0.8 mm | ~1.0 mm, slower | 0.3–0.5 mm, slow | ~0.8 mm |
| Watch out | softens ~55 °C | strings; sticks *too* well to PEI → glue stick as release | stringy, no fast moves | warps (open frame) — brim, no drafts, ventilate |

## Supports / adhesion

- Supports: only where the checker reports `overhang`/`long-bridge`.
  Tree/organic supports for curved models, normal supports for flat ceilings;
  0.2 mm Z distance for PLA, 0.25 for PETG.
- Brim 5–8 mm for `tippy` parts, sharp corners on big parts, and any ABS/ASA.
- Clean PEI with IPA; wash with dish soap when PLA stops sticking. Never
  scrape PEI — flex the sheet.

## Troubleshooting

| Symptom | Likely cause → fix |
|---|---|
| Won't stick / first layer patchy | dirty PEI (wash it); re-run LeviQ; Z-offset slightly lower; bed +5 °C; slow first layer to ~50 mm/s |
| Elephant's foot (bulged bottom) | Z-offset too low or bed too hot; models here chamfer 0.4 mm; slicer "elephant foot compensation" 0.15–0.2 |
| Stringing | temp −5 °C, increase retraction 0.2 mm, dry filament (PETG/TPU especially) |
| Warping / corners lift | brim, lower fan for first layers, no drafts; for ABS/ASA consider PETG instead |
| Layer shift | belt tension, print speed/accel too high for tall parts, nozzle hitting curled overhangs |
| Holes too small / fits too tight | run `models/tolerance-test`, update `tolerances` and `hole_compensation` in the profile |
| Under-extrusion at speed | lower speed or raise temp 5–10 °C; hotend volumetric limit (~20 mm³/s PLA) |
| Gaps in thin walls | walls below 0.9 mm; enable "detect thin walls" or thicken the model |
| Blobs/zits | enable scarf/aligned seam, reduce pressure advance overshoot, check wet filament |
| Clicking extruder | clog or too fast; cold pull; lower speed |

When answering, give a concrete settings list for the specific model
(pull dimensions/overhang info from its `PRINT.md` or `printlib check`),
not generic advice.
