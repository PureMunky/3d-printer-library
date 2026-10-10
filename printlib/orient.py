"""Placement and orientation helpers for existing meshes."""

from __future__ import annotations

import math

import numpy as np
import trimesh

from .meshio import to_trimesh
from .profile import Printer, load_printer


def place_on_bed(mesh: trimesh.Trimesh, center: bool = True) -> trimesh.Trimesh:
    mesh = to_trimesh(mesh).copy()
    lo, hi = mesh.bounds
    shift = np.array([-(lo[0] + hi[0]) / 2 if center else 0, -(lo[1] + hi[1]) / 2 if center else 0, -lo[2]])
    mesh.apply_translation(shift)
    return mesh


def _score(mesh: trimesh.Trimesh, p: Printer) -> tuple[float, dict]:
    lo, hi = mesh.bounds
    n, a, c = mesh.face_normals, mesh.area_faces, mesh.triangles_center
    on_bed = c[:, 2] < lo[2] + 0.05
    contact = float(a[on_bed & (n[:, 2] < -0.99)].sum())
    limit = math.sin(math.radians(float(p.design["max_overhang_deg"])))
    overhang = float(a[(n[:, 2] < -limit) & ~on_bed].sum())
    height = float(hi[2] - lo[2])
    uv = p.usable_volume
    ext = hi - lo
    fits = ext[2] <= uv[2] and ((ext[0] <= uv[0] and ext[1] <= uv[1]) or (ext[1] <= uv[0] and ext[0] <= uv[1]))
    # Lower is better: overhang area dominates, then height (time/stability),
    # contact area rewarded. Not fitting is disqualifying.
    score = overhang + 0.5 * height - 0.05 * contact + (0 if contact > 1 else 1e6) + (0 if fits else 1e7)
    return score, {"overhang_mm2": overhang, "contact_mm2": contact, "height": height, "fits": fits}


def candidate_rotations(mesh: trimesh.Trimesh, max_hull_faces: int = 12) -> list[np.ndarray]:
    """Axis-aligned orientations plus 'lay this big flat face down' candidates."""
    downs = [np.array(v, float) for v in ([0, 0, -1], [0, 0, 1], [1, 0, 0], [-1, 0, 0], [0, 1, 0], [0, -1, 0])]
    try:
        hull = mesh.convex_hull
        facets = sorted(zip(hull.facets_area, hull.facets_normal), key=lambda t: -t[0])[:max_hull_faces]
        downs += [np.asarray(nrm, float) for _, nrm in facets]
    except Exception:
        pass
    mats, seen = [], []
    for d in downs:
        d = d / np.linalg.norm(d)
        if any(np.allclose(d, s, atol=1e-3) for s in seen):
            continue
        seen.append(d)
        mats.append(trimesh.geometry.align_vectors(d, [0, 0, -1]))
    return mats


def best_orientation(mesh: trimesh.Trimesh, printer: Printer | None = None) -> tuple[trimesh.Trimesh, dict]:
    """Try candidate orientations; return the re-oriented mesh and its metrics."""
    p = printer or load_printer()
    mesh = to_trimesh(mesh)
    best = None
    for R in candidate_rotations(mesh):
        m = mesh.copy()
        m.apply_transform(R)
        s, info = _score(m, p)
        if best is None or s < best[0]:
            best = (s, m, info, R)
    _, m, info, R = best
    info = {k: round(v, 1) if isinstance(v, float) else v for k, v in info.items()}
    info["transform"] = np.round(R, 4).tolist()
    return place_on_bed(m), info
