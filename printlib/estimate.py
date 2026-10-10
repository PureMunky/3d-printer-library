"""Rough filament/time estimates. Good for "is this a 20 min or 9 h print?".

The slicer is authoritative; these numbers are within ~±30 % for typical parts.
"""

from __future__ import annotations

import math

import trimesh

from .meshio import to_trimesh
from .profile import Printer, load_printer

# Average volumetric throughput actually achieved over a whole print on the
# Kobra 2 Plus at default "fast" profiles (accel/travel/small perimeters
# included) — far below the hotend's peak.
AVG_FLOW_MM3_S = {"PLA": 9.0, "PETG": 7.0, "TPU": 2.5, "ABS": 7.0, "ASA": 7.0}
SHELL = 1.2  # mm of solid skin (walls/top/bottom) assumed all round


def estimate(mesh, printer: Printer | None = None, material: str = "PLA", infill: float = 0.15) -> dict:
    p = printer or load_printer()
    mat = p.material(material)
    mesh: trimesh.Trimesh = to_trimesh(mesh)
    vol = abs(float(mesh.volume))
    shell = min(vol, float(mesh.area) * SHELL)
    core = max(0.0, vol - shell)
    printed = shell + infill * core  # mm^3
    grams = printed / 1000 * mat.density
    fil_area = math.pi * (float(p.spec["filament_diameter"]) / 2) ** 2
    meters = printed / fil_area / 1000
    secs = printed / AVG_FLOW_MM3_S.get(mat.name, 7.0) + 120  # + heat/level overhead
    hrs, rem = divmod(int(secs), 3600)
    return {
        "printed_mm3": printed,
        "grams": grams,
        "meters": meters,
        "seconds": secs,
        "time_str": f"{hrs}h {rem // 60:02d}m" if hrs else f"{rem // 60}m",
    }
