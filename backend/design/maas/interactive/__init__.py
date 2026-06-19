"""Interactive MAAS operation layer.

This package keeps user-facing direct manipulation separate from the legal
MAAS generator. UI gestures become operation specs here, then every accepted
operation is routed through legal review/repair before returning to the client.
"""

from .orchestrator import apply_interactive_mass_operation

__all__ = ["apply_interactive_mass_operation"]
