"""Fit/tolerance calibration: one peg, a plate of holes at increasing clearance.

The holes use the same `hole()` helper (with hole compensation) that every
model in this library uses, so the result maps straight onto the
`tolerances:` section of printlib/profiles/kobra2plus.yaml:

  * tightest hole the peg goes into with firm hand pressure  -> press
  * tightest hole it slides into and stays put               -> snug
  * tightest hole it turns freely in                         -> slide
"""

from printlib.profile import load_printer
from printlib.shapes import box, cylinder, difference, hole, label_face, text2d

P = load_printer()

META = {
    "title": "Tolerance test",
    "description": "Peg + hole plate with labelled per-side clearances for calibrating fits.",
    "material": "PLA",
    "infill": 0.2,
    "supports": False,
    "notes": [
        "Print both parts with the same material/settings you plan to use for real parts.",
        "Numbers engraved under each hole are the per-side clearance in mm.",
        "Update `tolerances:` in printlib/profiles/kobra2plus.yaml with what you find.",
    ],
}

PARAMS = {
    "peg_d": 10.0,
    "clearances": [0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40],
    "plate_t": 5.0,
    "pitch": 16.0,
}


def build(peg_d, clearances, plate_t, pitch):
    n = len(clearances)
    plate = box(n * pitch + 4, pitch + 10, plate_t, r=3, bottom_chamfer=P.design["first_layer_chamfer"])
    x0 = -(n - 1) * pitch / 2
    cuts = [hole(peg_d + 2 * c, plate_t).translate((x0 + i * pitch, 3, 0)) for i, c in enumerate(clearances)]
    plate = difference(plate, cuts)
    for i, c in enumerate(clearances):
        txt = text2d(f"{c:.2f}".lstrip("0"), 4.0)
        plate = label_face(plate, txt, "+z", depth=0.6, offset=(x0 + i * pitch, -(pitch + 10) / 2 + 3.5))

    # Peg: chamfered both ends so the elephant's foot never decides the fit.
    peg = cylinder(peg_d, plate_t + 6)
    lead = 0.6
    peg = difference(peg, _ring_chamfer(peg_d, lead, 0), _ring_chamfer(peg_d, lead, plate_t + 6, top=True))
    peg = peg + box(peg_d + 6, 4, 2, r=1).translate((0, 0, 0))  # grip tab, also keeps it from rolling
    return {"plate": plate, "peg": peg}


def _ring_chamfer(d, c, z, top=False):
    """Cutter that bevels the outer edge of a cylinder end by c mm at 45°."""
    r = d / 2
    outer = cylinder(d + 2, c + 0.02)
    cone = cylinder(d - 2 * c, c + 0.02, d2=d + 0.04) if not top else cylinder(d + 0.04, c + 0.02, d2=d - 2 * c)
    ring = outer - cone
    return ring.translate((0, 0, z - 0.01 if not top else z - c - 0.01))
