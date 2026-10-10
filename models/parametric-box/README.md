# Parametric box with lid

Rounded storage box with a lid that presses in on a lip. Optional internal
dividers and an engraved label on the lid top.

```bash
python -m printlib build parametric-box \
  --set width=120 --set depth=80 --set height=50 \
  --set dividers_x=2 --set label=BEADS --out scratch/beads-box
```

| Param | Default | Notes |
|---|---|---|
| `width`, `depth`, `height` | 80, 60, 40 | outer size of the box body (mm) |
| `wall`, `floor` | 1.6, 1.2 | wall ≥ 0.9 enforced |
| `radius` | 5 | vertical corner radius |
| `lid_t`, `lip_h` | 2, 4 | lid plate thickness and lip height |
| `fit` | `snug` | `press`/`snug`/`slide`/`loose` from the printer profile |
| `dividers_x` | 0 | dividers across X |
| `label` | "" | engraved into the lid top (printed face-down) |

Print the lid top-face-down (as exported). See [PRINT.md](PRINT.md).
