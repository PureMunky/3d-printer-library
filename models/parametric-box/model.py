"""Rounded storage box with a press-in lid and optional dividers and label.

The lid is printed upside down (its top face on the bed, lip pointing up),
so the label is engraved into the bed side and comes out perfectly flat.
"""

from printlib.profile import load_printer
from printlib.shapes import box, difference, label_face, text2d

P = load_printer()

META = {
    "title": "Parametric box with lid",
    "description": "Rounded box + lid. Change width/depth/height, walls, dividers, label.",
    "material": "PLA",
    "infill": 0.15,
    "supports": False,
    "notes": [
        "Lid prints top-face-down; the label is engraved into that face.",
        "Lid fit uses the `snug` tolerance from the printer profile; use --set fit=slide for a looser lid.",
    ],
}

PARAMS = {
    "width": 80.0,       # outer X
    "depth": 60.0,       # outer Y
    "height": 40.0,      # outer Z of the box body (lid adds lid_t)
    "wall": 1.6,
    "floor": 1.2,
    "radius": 5.0,       # outer vertical corner radius
    "lid_t": 2.0,
    "lip_h": 4.0,
    "fit": "snug",       # press | snug | slide | loose
    "dividers_x": 0,     # number of internal dividers across X
    "label": "",
}


def build(width, depth, height, wall, floor, radius, lid_t, lip_h, fit, dividers_x, label):
    if wall < P.design["min_wall"]:
        raise ValueError(f"wall {wall} < printer min_wall {P.design['min_wall']}")
    chamfer = P.design["first_layer_chamfer"]
    iw, idp, ir = width - 2 * wall, depth - 2 * wall, max(radius - wall, 0.5)

    body = box(width, depth, height, r=radius, bottom_chamfer=chamfer)
    cavity = box(iw, idp, height, r=ir).translate((0, 0, floor))
    body = difference(body, cavity)
    if dividers_x > 0:
        pitch = iw / (dividers_x + 1)
        for i in range(1, dividers_x + 1):
            x = -iw / 2 + i * pitch
            # Dividers stop 1 mm under the rim so the lid lip still seats.
            body = body + box(wall, idp + 0.2, height - floor - lip_h - 1).translate((x, 0, floor))

    gap = P.tol(fit)
    lid = box(width, depth, lid_t, r=radius, bottom_chamfer=chamfer)
    lw, ld, lr = iw - 2 * gap, idp - 2 * gap, max(ir - gap, 0.5)
    lip = difference(box(lw, ld, lip_h, r=lr), box(lw - 2 * wall, ld - 2 * wall, lip_h + 1, r=max(lr - wall, 0.5)).translate((0, 0, -0.5)))
    lid = lid + lip.translate((0, 0, lid_t))
    if label:
        size = min(12.0, 0.6 * depth, 1.6 * width / max(len(label), 1))
        lid = label_face(lid, text2d(label, size), "-z", depth=0.6)
    return {"box": body, "lid": lid}
