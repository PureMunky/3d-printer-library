"""Conversions between manifold3d solids, trimesh meshes and STL files."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import trimesh
from manifold3d import Manifold, Mesh


def to_trimesh(solid: Manifold | trimesh.Trimesh) -> trimesh.Trimesh:
    if isinstance(solid, trimesh.Trimesh):
        return solid
    mesh = solid.to_mesh64()  # float32 can merge distinct nearby vertices
    verts = np.asarray(mesh.vert_properties, dtype=np.float64)[:, :3]
    faces = np.asarray(mesh.tri_verts, dtype=np.int64)
    return trimesh.Trimesh(vertices=verts, faces=faces, process=True)


def to_manifold(mesh: trimesh.Trimesh) -> Manifold:
    m = Manifold(
        Mesh(
            vert_properties=np.ascontiguousarray(mesh.vertices, dtype=np.float32),
            tri_verts=np.ascontiguousarray(mesh.faces, dtype=np.uint32),
        )
    )
    if m.status().name != "NoError":
        raise ValueError(f"Mesh is not a valid 2-manifold: {m.status().name}")
    return m


def load_mesh(path: str | Path) -> trimesh.Trimesh:
    mesh = trimesh.load_mesh(str(path), force="mesh")
    if not isinstance(mesh, trimesh.Trimesh):
        raise ValueError(f"{path} did not load as a single triangle mesh")
    return mesh


def export_stl(solid: Manifold | trimesh.Trimesh, path: str | Path) -> Path:
    """Write a binary STL (millimetre units). Creates parent dirs."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    mesh = to_trimesh(solid)
    if len(mesh.faces) == 0:
        raise ValueError(f"Refusing to write empty mesh to {path}")
    mesh.export(str(path), file_type="stl")
    return path
