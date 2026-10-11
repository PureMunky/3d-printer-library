"""Fraction tiles (fraction bars) with a storage/working tray.

Rows for 1, 1/2, 1/3, 1/4, 1/5, 1/6, 1/8, 1/10 and 1/12 — the denominators in
the 4th-grade standards (equivalence, comparing, adding like denominators).
Every tile in a row is exactly whole/d long minus a tiny gap, so ½ lines up
with 2 × ¼ and 3 × ⅙.

Each denominator is its own STL so every row can be printed in a different
colour (the usual convention for fraction tiles). Labels are raised stacked
fractions — readable by touch as well as sight.
"""

from manifold3d import CrossSection, Manifold

from printlib.profile import load_printer
from printlib.shapes import arrange, box, difference, offset, on_bed, rect, text2d

P = load_printer()

META = {
    "title": "Fraction tiles and tray",
    "description": "Labelled fraction bars (1 to 1/12) with a tray that holds a full set in order.",
    "material": "PLA",
    "infill": 0.15,
    "supports": False,
    "notes": [
        "Print each `tiles-N` file in its own colour; the tray in a neutral colour.",
        "Tiles are whole/d long minus a 0.15 mm gap so a full row drops into the tray without jamming; "
        "twelve twelfths come out ~1.8 mm shorter than the whole bar, which doesn't show in use.",
        "Labels are raised 0.8 mm so students can feel them; set label_raise=0 for flat tiles.",
        "Full set: 51 tiles (~3.3 h, ~120 g) + tray (~1.9 h, ~75 g). Print the rows the students need first.",
    ],
}

PARAMS = {
    "denominators": [1, 2, 3, 4, 5, 6, 8, 10, 12],
    "whole": 160.0,        # length of the "1" bar
    "tile_h": 18.0,        # bar height (Y)
    "tile_t": 5.0,         # tile thickness
    "gap": 0.15,           # subtracted from each tile's length
    "label_size": 5.5,     # cap height of numerator/denominator
    "label_raise": 0.8,
    "tray": True,
    "tray_wall": 2.0,
    "tray_floor": 1.6,
}


def build(denominators, whole, tile_h, tile_t, gap, label_size, label_raise, tray, tray_wall, tray_floor):
    if whole / max(denominators) < 2.2 * label_size:
        raise ValueError("tiles too short for their labels: raise `whole` or lower `label_size`")
    chamfer = P.design["first_layer_chamfer"]
    parts = {}
    for d in denominators:
        tile_len = whole / d - gap
        tile = box(tile_len, tile_h, tile_t, bottom_chamfer=chamfer, top_chamfer=0.6)
        if label_raise > 0:
            tile = tile + Manifold.extrude(_fraction_label(d, label_size), label_raise).translate((0, 0, tile_t))
        parts[f"tiles-{d}"] = arrange([tile] * d, gap=3.0) if d > 1 else on_bed(tile)

    if tray:
        parts["tray"] = _tray(denominators, whole, tile_h, tile_t, tray_wall, tray_floor)
    return parts


def _fraction_label(d: int, size: float) -> CrossSection:
    """Stacked fraction, strokes thickened so they clear the printer's min wall."""
    return offset(_stacked(d, size), 0.2)


def _stacked(d: int, size: float) -> CrossSection:
    if d == 1:
        return text2d("1", size * 1.2)
    num, den = text2d("1", size), text2d(str(d), size)
    bar_w = max(_w(num), _w(den)) + 1.0
    bar_t = max(0.9, size * 0.16)
    pitch = size / 2 + bar_t / 2 + 1.0
    return num.translate((0, pitch)) + rect(bar_w, bar_t) + den.translate((0, -pitch))


def _tray(denominators, whole, tile_h, tile_t, wall, floor):
    """One channel per row, in order. Channels are half a tile deep, so tiles
    stand proud and can be pinched out."""
    clear = P.tol("slide")
    ch_w, ch_l = tile_h + 2 * clear, whole + 2 * clear
    rows = len(denominators)
    depth = tile_t / 2
    W = ch_l + 2 * wall
    H = rows * ch_w + (rows + 1) * wall
    base = box(W, H, floor + depth, r=3, bottom_chamfer=P.design["first_layer_chamfer"])
    cuts = []
    for i in range(rows):
        y = H / 2 - wall - ch_w / 2 - i * (ch_w + wall)
        cuts.append(box(ch_l, ch_w, depth + 1).translate((0, y, floor)))
    return difference(base, cuts)


def _w(cs):
    x0, _, x1, _ = cs.bounds()
    return x1 - x0

