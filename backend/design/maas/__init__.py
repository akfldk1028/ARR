"""ARR-local MAAS generator.

MAAS is organized as legal-envelope-first generation:

1. ``legal_envelope`` converts ARR constraints into the buildable/capacity
   boundary.
2. ``seed_library`` treats legacy ARR mass algorithms as seed/operator sources.
3. ``legal_mesh_optimizer`` repairs, validates, ranks, and returns candidates.

OpenSCAD export remains an output adapter, not the mass-generation source.
"""

from .geometry_exporter import export_mass_geojson_to_scad, mass_geojson_to_scad
from .legal_envelope import build_legal_envelope
from .legal_mesh_optimizer import generate_legal_mass_variants
from .evidence import SCHEMA_VERSION, build_maas_evidence_bundle

__all__ = [
    "SCHEMA_VERSION",
    "build_legal_envelope",
    "build_maas_evidence_bundle",
    "export_mass_geojson_to_scad",
    "generate_legal_mass_variants",
    "mass_geojson_to_scad",
]
