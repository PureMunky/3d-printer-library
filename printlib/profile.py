"""Printer profile loading.

The profile is a plain YAML file so it is easy for humans (and Claude) to read
and tweak. Everything else in printlib takes its numbers from here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml

PROFILE_DIR = Path(__file__).parent / "profiles"
DEFAULT_PRINTER = "kobra2plus"


@dataclass(frozen=True)
class Material:
    name: str
    density: float  # g/cm^3
    nozzle: int
    bed: int
    fan: int
    speed: int
    notes: str = ""


@dataclass(frozen=True)
class Printer:
    name: str
    spec: dict
    usable_volume: tuple[float, float, float]
    design: dict
    tolerances: dict
    materials: dict[str, Material] = field(default_factory=dict)

    @property
    def build_volume(self) -> tuple[float, float, float]:
        return tuple(self.spec["build_volume"])

    @property
    def nozzle(self) -> float:
        return float(self.spec["nozzle_diameter"])

    def material(self, name: str) -> Material:
        try:
            return self.materials[name.upper()]
        except KeyError:
            raise KeyError(f"Unknown material {name!r}; known: {sorted(self.materials)}") from None

    def tol(self, kind: str) -> float:
        """Clearance per side for a fit kind (press/snug/slide/loose/print_in_place)."""
        return float(self.tolerances[kind])


@lru_cache(maxsize=None)
def load_printer(name: str = DEFAULT_PRINTER) -> Printer:
    path = Path(name)
    if not path.suffix:
        path = PROFILE_DIR / f"{name}.yaml"
    data = yaml.safe_load(path.read_text())
    materials = {
        k.upper(): Material(name=k.upper(), **v) for k, v in (data.get("materials") or {}).items()
    }
    return Printer(
        name=data["name"],
        spec=data["spec"],
        usable_volume=tuple(data["usable_volume"]),
        design=data["design"],
        tolerances=data["tolerances"],
        materials=materials,
    )
