"""ARR MAAS grammar adapter."""

from .intent import load_term_ontology, resolve_intent_to_sequence
from .legal_interpreter import generate_grammar_variants, interpret_sequence
from .sequence_library import SEQUENCES, get_sequence_label
from .verb_sequence import VerbCall, VerbSequence

__all__ = [
    "SEQUENCES",
    "VerbCall",
    "VerbSequence",
    "generate_grammar_variants",
    "get_sequence_label",
    "interpret_sequence",
    "load_term_ontology",
    "resolve_intent_to_sequence",
]
