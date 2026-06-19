"""Supported MAAS verbs for ARR legal massing.

The reference MAAS repo has a larger OpenSCAD grammar. ARR starts with the
subset that can be interpreted directly as legal Shapely operations.
"""

SUPPORTED_VERBS = {
    "base",
    "notch",
    "cave",
    "courtyard",
    "split",
    "branch",
    "pinch",
    "interlock",
    "overlap",
    "bar",
    "lift",
    "taper",
    "grade",
    "step_envelope",
    "shift",
    "inset",
    "expand",
}

PLAN_VERBS = {
    "notch",
    "cave",
    "courtyard",
    "split",
    "branch",
    "pinch",
    "interlock",
    "overlap",
    "bar",
    "shift",
    "inset",
    "expand",
}

SECTION_VERBS = {"lift", "taper", "grade", "step_envelope"}


__all__ = ["PLAN_VERBS", "SECTION_VERBS", "SUPPORTED_VERBS"]
