# Post-it to-do stencil

A thin stencil for standard 3×3 in (76 mm) sticky notes. Trace it to get a
title line plus five checkboxes, each with a writing line.

![preview](preview.png)

## Using it

1. Flip it so the lip points down, and hook the lip over the note's **top
   (sticky) edge and left edge**. That puts every note in the same place.
2. Trace the **inside** of each square to draw a checkbox.
3. Run the pen tip along each slot to draw the lines.

A fine-tip pen (0.5–1 mm) works best. Clean off ink with rubbing alcohol.

## Printing

Print as exported, lip up. The smooth bed-side face is the side you write
on. No supports; about 14 minutes and 9 g of PLA. 100% infill because the
plate is only 1.2 mm thick.

## Parameters

| Param | Default | Notes |
|---|---|---|
| `note_w`, `note_h` | 76, 76 | note size. Use `note_w=127` for 3×5 in notes |
| `rows` | 5 | checkbox rows (errors out if they don't fit) |
| `box_size` | 6 | checkbox size |
| `slot_w` | 2.0 | line slot width |
| `margin` | 6 | left/right/bottom margin |
| `title_line`, `title_gap` | true, 16 | title line across the sticky strip |
| `thickness` | 1.2 | plate thickness |
| `lip_h`, `lip_w` | 1.6, 2.4 | alignment lip drop and wall thickness |

```bash
python -m printlib build todo-stencil --set rows=6 --set title_line=false --out scratch/six-rows
```
