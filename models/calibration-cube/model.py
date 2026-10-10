"""20 mm XYZ calibration cube.

Measure each axis with calipers after printing. If X/Y read 20.2, check
flow/e-steps or horizontal expansion in the slicer; if Z is off, check layer
height / Z steps. The bottom edge is chamfered, so measure X/Y above the first mm.
"""

from printlib.profile import load_printer
from printlib.shapes import box, label_face, text2d

P = load_printer()

META = {
    "title": "XYZ calibration cube",
    "description": "20 mm cube with engraved axis letters for dimensional calibration.",
    "material": "PLA",
    "infill": 0.15,
    "supports": False,
    "notes": [
        "Measure X/Y above the chamfered first millimetre.",
        "Letters: Z on top, X on the +X face, Y on the -Y face (front).",
    ],
}

PARAMS = {"size": 20.0, "letter_size": 8.0, "depth": 0.6}


def build(size, letter_size, depth):
    cube = box(size, size, size, bottom_chamfer=P.design["first_layer_chamfer"])
    cube = label_face(cube, text2d("Z", letter_size), "+z", depth)
    cube = label_face(cube, text2d("X", letter_size), "+x", depth)
    cube = label_face(cube, text2d("Y", letter_size), "-y", depth)
    return cube
