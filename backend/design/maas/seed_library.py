"""MAAS seed/operator library.

Legacy ARR mass results enter MAAS here only as seed geometry. The legal
envelope still owns capacity; this library supplies diverse shapes/operators
that can be repaired and ranked against that envelope.
"""

from __future__ import annotations

from typing import Any

from shapely.geometry import Polygon

from design.maas.legal_envelope import LegalEnvelope
from design.maas.grammar import generate_grammar_variants
from design.maas.morphology_operators import MorphologyVariant, generate_morphology_variants


def generate_seed_variants(
    base_footprint: Polygon,
    envelope: LegalEnvelope,
    *,
    include_interactive_seed: bool = False,
) -> list[MorphologyVariant]:
    variants: list[MorphologyVariant] = []
    if include_interactive_seed:
        variants.append(MorphologyVariant(
            "interactive_seed_repaired",
            base_footprint,
            notes=("사용자 조작 seed를 법규 repair 후 보존",),
        ))
    if envelope.buildable_footprint is not None:
        variants.append(MorphologyVariant(
            "legal_buildable_max",
            envelope.buildable_footprint,
            notes=("법규 envelope 기준 최대 footprint anchor",),
        ))
        variants.extend(generate_grammar_variants(envelope.buildable_footprint))
        variants.extend(generate_morphology_variants(envelope.buildable_footprint))
    variants.extend(generate_grammar_variants(base_footprint))
    variants.extend(generate_morphology_variants(base_footprint))
    return variants


def seed_library_metadata() -> dict[str, Any]:
    return {
        "role": "seed_operator_library",
        "grammar_sequences": "enabled_as_composite_maas_seeds",
        "legacy_algorithms": "demoted_to_seed_sources",
        "capacity_source": "legal_envelope",
    }


__all__ = ["generate_seed_variants", "seed_library_metadata"]
