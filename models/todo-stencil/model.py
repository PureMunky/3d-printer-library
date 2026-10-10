"""Post-it to-do stencil: lay it on a sticky note and trace to get a column of
checkboxes, each with a writing line (plus an optional title line).

How it works:
  * Checkboxes are square holes; trace the inside edge to draw a box.
  * Lines are narrow slots; run a pen tip along the slot.
  * An L-shaped lip on the paper side hooks over the note's top and left
    edges, so every note comes out in the same place.

Modeled in "use" orientation (paper side at z = 0, lip hanging below), then
flipped so the lip points up for printing and the pen side is the smooth
bed-side face.
"""

from printlib.profile import load_printer
from printlib.shapes import box, difference, on_bed, union

P = load_printer()

META = {
    "title": "Post-it to-do stencil",
    "description": "Checkbox + line stencil for 76 mm (3\") sticky notes, with a corner lip for alignment.",
    "material": "PLA",
    "infill": 1.0,
    "supports": False,
    "notes": [
        "Prints lip-up, as exported; the smooth bed side becomes the pen side.",
        "Flip it over to use: lip down, hooked over the note's top (sticky) edge and left edge.",
        "Trace the inside of each square for a checkbox; run the pen along each slot for the line.",
        "Fine-tip pens (0.5-1 mm) work best. Wipe ink off with alcohol.",
        "Defaults fit standard 3x3 in (76 mm) notes; set note_w/note_h for other sizes (e.g. 127 x 76 for 3x5).",
    ],
}

PARAMS = {
    "note_w": 76.0,       # sticky note width (X)
    "note_h": 76.0,       # sticky note height (Y), sticky strip at the top
    "rows": 5,            # number of checkbox rows
    "box_size": 6.0,      # checkbox size
    "slot_w": 2.0,        # line slot width (pen tip runs in it)
    "margin": 6.0,        # left/right/bottom margin on the note
    "title_line": True,   # a full-width line across the sticky strip
    "title_gap": 16.0,    # space from the top edge reserved for the title
    "thickness": 1.2,     # plate (6 layers): thin so the pen reaches the paper
    "lip_h": 1.6,         # how far the lip hangs over the note edge
    "lip_w": 2.4,         # lip wall thickness
}


def build(note_w, note_h, rows, box_size, slot_w, margin, title_line, title_gap, thickness, lip_h, lip_w):
    b, t = box_size, thickness

    # Plate covers the note; lip sits just outside the top and left note edges.
    plate = box(note_w + lip_w, note_h + lip_w, t).translate((-lip_w / 2, lip_w / 2, 0))
    lip_top = box(note_w + lip_w, lip_w, lip_h + t).translate((-lip_w / 2, note_h / 2 + lip_w / 2, -lip_h))
    lip_left = box(lip_w, note_h + lip_w, lip_h + t).translate((-note_w / 2 - lip_w / 2, lip_w / 2, -lip_h))
    stencil = union(plate, lip_top, lip_left)

    # Coordinates below are on the note: x in [-note_w/2, note_w/2], y top = +note_h/2.
    left, right = -note_w / 2 + margin, note_w / 2 - margin
    cuts = []
    if title_line:
        y = note_h / 2 - title_gap + 4
        cuts.append(_slot(left, right, y, slot_w, t))
        top_of_rows = note_h / 2 - title_gap - 4
    else:
        top_of_rows = note_h / 2 - margin
    bottom = -note_h / 2 + margin
    pitch = (top_of_rows - bottom) / rows
    if pitch < b + 3:
        raise ValueError(f"{rows} rows of {b} mm boxes don't fit; reduce rows or box size")
    for i in range(rows):
        y_base = top_of_rows - (i + 1) * pitch + (pitch - b) / 2  # bottom edge of the checkbox
        bx = left + b / 2
        cuts.append(box(b, b, t + 2).translate((bx, y_base + b / 2, -1)))
        # Writing line sits on the checkbox's baseline.
        cuts.append(_slot(left + b + 3, right, y_base + slot_w / 2, slot_w, t))

    stencil = difference(stencil, cuts)
    return on_bed(stencil.rotate((0, 180, 0)))  # lip up for printing


def _slot(x0, x1, y, w, t):
    """Through-slot with rounded ends from x0 to x1, centred on y."""
    return box(x1 - x0, w, t + 2, r=w / 2 - 0.01).translate(((x0 + x1) / 2, y, -1))
