"""Word-part (morpheme) tiles: prefixes, base words/roots and suffixes that
physically connect, for building and breaking apart multisyllabic words —
core 4th-grade decoding and vocabulary work in reading intervention.

The connector shape *is* the grammar:
  * prefix tiles have a knob on the right only
  * base tiles have a socket on the left and a knob on the right
  * suffix tiles have a socket on the left only
So a prefix can't go after a base, and nothing attaches after a suffix
(un + help + ful works; ful + help doesn't fit). Suffixes can still stack on
a base in practice (help + less + ness) because base and suffix share the
same socket — when you need that, flip the logic in the lesson, not the tile.

Each category is its own STL so they can be printed in three colours
(a common convention: prefixes green, bases yellow/white, suffixes blue).
"""

from manifold3d import CrossSection, Manifold

from printlib.profile import load_printer
from printlib.shapes import box, extrude, offset, on_bed, rect, text2d, union

P = load_printer()

META = {
    "title": "Word-part tiles",
    "description": "Connecting prefix / base-word / suffix tiles for morphology and decoding practice.",
    "material": "PLA",
    "infill": 0.15,
    "supports": False,
    "notes": [
        "Print prefixes, bases and suffixes in three different colours.",
        "Tiles lie flat; the jigsaw connectors join by pressing one tile down onto the next.",
        "Word lists are parameters — edit them for this week's lesson and rebuild.",
        "Example words: un-help-ful, re-use-able, dis-agree-ment, pre-view, trans-port, play-er, kind-ness.",
        "Raised letters are 0.8 mm tall so students can trace them with a finger.",
    ],
}

SINK = 0.3

PARAMS = {
    "prefixes": ["un", "re", "dis", "pre", "mis", "non", "over", "trans"],
    "bases": ["help", "play", "kind", "read", "use", "agree", "view", "lock", "port", "form"],
    "suffixes": ["ful", "less", "able", "ness", "ly", "er", "ing", "ed", "ment", "s"],
    "text_size": 8.0,      # cap height; lowercase x-height is ~6 mm
    "tile_h": 24.0,
    "tile_t": 5.0,
    "text_raise": 0.8,
    "knob_d": 8.0,
    "knob_reach": 6.0,     # how far the knob sticks out
    "fit": "slide",
    "plate_width": 290.0,  # wrap tiles into rows on a plate this wide
}


def build(prefixes, bases, suffixes, text_size, tile_h, tile_t, text_raise, knob_d, knob_reach, fit, plate_width):
    kw = dict(size=text_size, h=tile_h, t=tile_t, raise_=text_raise, d=knob_d, reach=knob_reach, gap=P.tol(fit))
    return {
        "prefixes": _plate([_tile(w, socket=False, knob=True, **kw) for w in prefixes], plate_width),
        "bases": _plate([_tile(w, socket=True, knob=True, **kw) for w in bases], plate_width),
        "suffixes": _plate([_tile(w, socket=True, knob=False, **kw) for w in suffixes], plate_width),
    }


def _connector(d: float, reach: float) -> CrossSection:
    """Jigsaw knob outline: a neck from x=0 out to a round head, centred on y=0."""
    neck_w = d * 0.55
    head = CrossSection.circle(d / 2).translate((reach - d / 2, 0))
    neck = rect(reach - d / 2 + 0.5, neck_w).translate(((reach - d / 2) / 2 - 0.25, 0))
    return head + neck


def _tile(word, socket, knob, size, h, t, raise_, d, reach, gap):
    label = text2d(word, size)
    x0, _, x1, _ = label.bounds()
    pad = 5.0
    body_w = max(h, (x1 - x0) + 2 * pad + (reach if socket else 0))
    left, right = -body_w / 2, body_w / 2
    chamfer = P.design["first_layer_chamfer"]

    tile = box(body_w, h, t, r=2, bottom_chamfer=chamfer)
    # Connectors are sunk SINK mm into the body so the knob's round head never
    # meets the tile's edge tangentially (coincident faces break the mesh).
    if knob:
        tile = tile + extrude(_connector(d, reach).translate((right - SINK, 0)), t, bottom_chamfer=chamfer)
    if socket:
        # Socket = knob outline grown by the fit clearance, cut in at the left edge,
        # with the first layers relieved so elephant's foot can't pinch the knob.
        cut = offset(_connector(d, reach), gap).translate((left - SINK, 0))
        cut = cut + rect(1.0, d * 0.55 + 2 * gap).translate((left - 0.4, 0))  # clean entry
        relief = Manifold.extrude(offset(cut, chamfer), chamfer + 1).translate((0, 0, -1))
        tile = tile - (Manifold.extrude(cut, t + 2).translate((0, 0, -1)) + relief)

    # Text centred on the solid part of the tile (right of the socket).
    cx = (left + (reach if socket else 0) + right) / 2
    tile = tile + Manifold.extrude(offset(label, 0.15), raise_).translate((cx, 0, t))
    return on_bed(tile, center=False)


def _plate(tiles, width, gap=4.0):
    """Wrap tiles into rows that fit `width`, starting at the bed origin."""
    placed, x, y, row_h = [], 0.0, 0.0, 0.0
    for t in tiles:
        b = t.bounding_box()
        w, h = b[3] - b[0], b[4] - b[1]
        if x > 0 and x + w > width:
            x, y, row_h = 0.0, y - row_h - gap, 0.0
        placed.append(t.translate((x - b[0], y - b[4], 0)))
        x += w + gap
        row_h = max(row_h, h)
    return on_bed(union(placed))

