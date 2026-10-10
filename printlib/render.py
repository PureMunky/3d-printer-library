"""Headless PNG previews so a model can be eyeballed (by a human, or by Claude
reading the image) without opening a slicer.

A tiny orthographic z-buffer rasterizer in numpy: correct occlusion, flat
shading, outlined creases, and overhang faces (that would need support)
tinted red. No GPU/OpenGL needed.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .meshio import to_trimesh
from .profile import load_printer

# name: (elevation, azimuth) in degrees, matplotlib-style camera placement.
VIEWS = {
    "iso": (30, -55),
    "front": (0, -90),
    "back": (0, 90),
    "right": (0, 0),
    "left": (0, 180),
    "top": (90, -90),
    "bottom": (-90, -90),
    "iso-back": (30, 125),
}
BLUE = np.array([70, 130, 200], float)
RED = np.array([215, 70, 55], float)
BG = (255, 255, 255)


def _camera(elev: float, azim: float):
    e, a = math.radians(elev), math.radians(azim)
    to_viewer = np.array([math.cos(e) * math.cos(a), math.cos(e) * math.sin(a), math.sin(e)])
    right = np.array([-math.sin(a), math.cos(a), 0.0])
    up = np.cross(to_viewer, right)
    return right, up, to_viewer


def _raster(verts, faces, normals, colors, view, size, ctr, half):
    right, up, fwd = _camera(*view)
    scale = (size / 2 - 8) / half
    rel = verts - ctr
    px = (rel @ right) * scale + size / 2
    py = size / 2 - (rel @ up) * scale
    pz = rel @ fwd

    vis = normals @ fwd > 1e-6  # back-face cull (closed meshes)
    zbuf = np.full((size, size), -np.inf)
    nbuf = np.zeros((size, size, 3))
    img = np.zeros((size, size, 3))
    light = fwd + 0.6 * up + 0.4 * right
    light /= np.linalg.norm(light)
    shade = 0.35 + 0.65 * np.clip(normals @ light, 0, 1)

    for i in np.nonzero(vis)[0]:
        f = faces[i]
        x, y, z = px[f], py[f], pz[f]
        x0, x1 = max(int(x.min()), 0), min(int(math.ceil(x.max())), size - 1)
        y0, y1 = max(int(y.min()), 0), min(int(math.ceil(y.max())), size - 1)
        if x0 > x1 or y0 > y1:
            continue
        gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        d = (y[1] - y[2]) * (x[0] - x[2]) + (x[2] - x[1]) * (y[0] - y[2])
        if abs(d) < 1e-12:
            continue
        w0 = ((y[1] - y[2]) * (gx - x[2]) + (x[2] - x[1]) * (gy - y[2])) / d
        w1 = ((y[2] - y[0]) * (gx - x[2]) + (x[0] - x[2]) * (gy - y[2])) / d
        w2 = 1 - w0 - w1
        inside = (w0 >= -1e-4) & (w1 >= -1e-4) & (w2 >= -1e-4)
        if not inside.any():
            continue
        zz = w0 * z[0] + w1 * z[1] + w2 * z[2]
        sub = zbuf[y0 : y1 + 1, x0 : x1 + 1]
        upd = inside & (zz > sub)
        sub[upd] = zz[upd]
        img[y0 : y1 + 1, x0 : x1 + 1][upd] = colors[i] * shade[i]
        nbuf[y0 : y1 + 1, x0 : x1 + 1][upd] = normals[i]

    hit = np.isfinite(zbuf)
    out = np.where(hit[..., None], img, np.array(BG, float))
    # Outline silhouettes and creases.
    edge = np.zeros_like(hit)
    zf = np.where(hit, zbuf, -1e9)
    for dy, dx in ((0, 1), (1, 0)):
        a_hit, b_hit = hit[: size - dy, : size - dx], hit[dy:, dx:]
        na, nb = nbuf[: size - dy, : size - dx], nbuf[dy:, dx:]
        za, zb = zf[: size - dy, : size - dx], zf[dy:, dx:]
        e = (a_hit != b_hit) | (a_hit & b_hit & ((na * nb).sum(-1) < 0.95))
        edge[: size - dy, : size - dx] |= e
        # Depth steps (raised/engraved detail on parallel faces): the second
        # difference of depth is ~0 across any plane, sloped or not, and large
        # across a step — so this catches sub-mm relief at any zoom.
        z0, z1, z2 = zf[: size - 2 * dy, : size - 2 * dx], zf[dy : size - dy, dx : size - dx], zf[2 * dy :, 2 * dx :]
        all_hit = hit[: size - 2 * dy, : size - 2 * dx] & hit[dy : size - dy, dx : size - dx] & hit[2 * dy :, 2 * dx :]
        step = all_hit & (np.abs(z0 - 2 * z1 + z2) > 0.3)
        edge[dy : size - dy, dx : size - dx] |= step
    out[edge] = out[edge] * 0.35
    return Image.fromarray(out.clip(0, 255).astype(np.uint8))


def _font(size: int):
    try:
        from matplotlib import font_manager

        return ImageFont.truetype(font_manager.findfont("DejaVu Sans"), size)
    except Exception:
        return ImageFont.load_default()


def render(
    mesh,
    out: str | Path,
    views: tuple[str, ...] = ("iso", "front", "right", "top"),
    title: str | None = None,
    highlight_overhangs: bool = True,
    size: int = 480,
) -> Path:
    p = load_printer()
    mesh = to_trimesh(mesh)
    verts = np.asarray(mesh.vertices, float)
    faces = np.asarray(mesh.faces)
    normals = np.asarray(mesh.face_normals, float)
    colors = np.tile(BLUE, (len(faces), 1))
    lo, hi = mesh.bounds
    if highlight_overhangs:
        lim = math.sin(math.radians(float(p.design["max_overhang_deg"])))
        oh = (normals[:, 2] < -lim - 1e-6) & (mesh.triangles_center[:, 2] > lo[2] + 0.05)
        colors[oh] = RED
    ctr = (lo + hi) / 2
    half = max(float(np.linalg.norm(hi - lo)) / 2, 1.0)  # fits any view direction

    cols = 2 if len(views) > 1 else 1
    rows = (len(views) + cols - 1) // cols
    head = 44
    sheet = Image.new("RGB", (cols * size, rows * (size + 18) + head), BG)
    draw = ImageDraw.Draw(sheet)
    font = _font(14)
    small = _font(12)
    for k, v in enumerate(views):
        tile = _raster(verts, faces, normals, colors, VIEWS[v], size, ctr, half)
        x, y = (k % cols) * size, head + (k // cols) * (size + 18)
        sheet.paste(tile, (x, y + 18))
        draw.text((x + 8, y + 2), v, fill=(60, 60, 60), font=small)
    ext = hi - lo
    caption = f"{ext[0]:.1f} × {ext[1]:.1f} × {ext[2]:.1f} mm    red = overhang > {p.design['max_overhang_deg']}°"
    draw.text((8, 6), title or "", fill=(0, 0, 0), font=font)
    draw.text((8, 24), caption, fill=(80, 80, 80), font=small)
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out)
    return out
