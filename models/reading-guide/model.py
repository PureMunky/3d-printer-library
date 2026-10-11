"""Reading tracking guides: a flat strip with a one-line window that shows
the line being read and masks the lines above and below it.

Used in reading intervention for students who lose their place, skip lines,
or are overwhelmed by a full page (dyslexia, ADHD, tracking difficulties).

A set of window heights is exported, one STL per size, so a student can use
the one that matches the text. Window edges have a 45° bevel on the top side
so the strip doesn't cast a shadow over the line, and the window size is
engraved in the corner.
"""

from manifold3d import Manifold

from printlib.profile import load_printer
from printlib.shapes import box, difference, label_face, rect, text2d

P = load_printer()

META = {
    "title": "Reading tracking guides",
    "description": "One-line reading windows in several sizes for reading intervention.",
    "material": "PLA",
    "infill": 1.0,
    "supports": False,
    "notes": [
        "Window heights: ~6 mm suits 12 pt text, ~8 mm suits 14-16 pt leveled readers, ~11 mm suits large print.",
        "Print in a translucent coloured PLA/PETG (yellow, blue or rose) to make the strips double as colour overlays.",
        "Prints flat as exported; beveled side up is the side you look at.",
        "Size is engraved in the bottom-left corner so strips stay sorted.",
    ],
}

PARAMS = {
    "window_heights": [6.0, 8.0, 11.0],  # one guide per height
    "length": 180.0,      # overall strip length (fits a book page or worksheet)
    "height": 44.0,       # overall strip height: masks ~2 lines above and below
    "window_len": 150.0,  # visible line length
    "thickness": 1.6,     # stiff enough at 18 cm, thin enough to sit flat
    "bevel": 0.8,         # top-side 45° bevel on the window edge
    "corner_r": 5.0,
}


def build(window_heights, length, height, window_len, thickness, bevel, corner_r):
    chamfer = P.design["first_layer_chamfer"]
    parts = {}
    for wh in window_heights:
        if wh >= height - 10:
            raise ValueError(f"window {wh} mm leaves too little strip in a {height} mm guide")
        strip = box(length, height, thickness, r=corner_r, bottom_chamfer=chamfer)
        strip = difference(strip, _window(window_len, wh, thickness, bevel))
        label = text2d(f"{wh:g} mm", 4.5)
        x = -length / 2 + 6 + _width(label) / 2
        y = -height / 2 + 3.5 + 2.25
        strip = label_face(strip, label, "+z", depth=0.6, offset=(x, y))
        parts[f"{wh:g}mm"] = strip
    return parts


def _window(w, h, t, bevel):
    """Through-window cutter with a 45° bevel opening up toward the top face."""
    straight = box(w, h, t + 0.02, r=min(1.5, h / 2 - 0.01)).translate((0, 0, -0.01))
    b = min(bevel, t - 0.4)
    cs = rect(w, h, r=min(1.5, h / 2 - 0.01))
    flare = Manifold.extrude(cs, b + 0.02, scale_top=((w + 2 * b) / w, (h + 2 * b) / h)).translate((0, 0, t - b))
    return straight + flare


def _width(cs):
    x0, _, x1, _ = cs.bounds()
    return x1 - x0
