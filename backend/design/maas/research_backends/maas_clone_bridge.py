"""Bridge to the cloned MAAS reference code.

ARR keeps legal geometry in its own Shapely/legal pipeline, but the paper
baseline should still be executable from the checked-out ``clone/MAAS`` source.
This module imports the clone as an external reference and reports failures as
evidence instead of breaking ARR massing.
"""

from __future__ import annotations

import hashlib
import importlib
import os
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[5]


def maas_clone_source_path() -> Path:
    return _repo_root() / "clone" / "MAAS" / "src"


def maas_clone_labels_path() -> Path:
    return _repo_root() / "clone" / "MAAS" / "data" / "case_studies" / "labels.json"


def maas_clone_reference_sequence() -> dict[str, Any]:
    return {
        "name": "arr_reference_simple_cave_taper",
        "calls": [
            {"verb": "base", "params": {"proportion": "1/1"}},
            {"verb": "cave", "params": {"face": "+y", "depth": 0.3}},
            {"verb": "taper", "params": {"top_ratio": 0.7}},
        ],
    }


def maas_clone_license_summary() -> dict[str, Any]:
    return {
        "name": "MAAS",
        "source": "clone/MAAS",
        "mode": "external_clone_bridge",
        "integration_rule": "Use clone/MAAS/src directly as the reference baseline; ARR remains the legal geometry source.",
    }


@lru_cache(maxsize=2)
def _inspect_maas_clone_cached(should_import: bool) -> dict[str, Any]:
    src = maas_clone_source_path()
    labels = maas_clone_labels_path()
    info: dict[str, Any] = {
        **maas_clone_license_summary(),
        "source_path": str(src),
        "exists": src.exists(),
        "labels_path": str(labels),
        "labels_exists": labels.exists(),
        "labels_status": "available" if labels.exists() else "missing_artifact",
        "status": "missing" if not src.exists() else "available_not_imported",
        "interfaces": {
            "verb_sequence": "maas.grammar.verb_sequence.VerbSequence",
            "verb_call": "maas.grammar.verb_sequence.VerbCall",
            "compiler": "maas.grammar.compiler.compile_sequence",
            "metrics": "maas.eval.metrics.compare_sequences",
        },
    }
    if not src.exists() or not should_import:
        return info

    inserted = False
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))
        inserted = True
    try:
        verb_sequence = importlib.import_module("maas.grammar.verb_sequence")
        compiler = importlib.import_module("maas.grammar.compiler")
        metrics = importlib.import_module("maas.eval.metrics")
        info["status"] = "imported"
        info["imported"] = {
            "VerbSequence": hasattr(verb_sequence, "VerbSequence"),
            "VerbCall": hasattr(verb_sequence, "VerbCall"),
            "compile_sequence": hasattr(compiler, "compile_sequence"),
            "compare_sequences": hasattr(metrics, "compare_sequences"),
            "token_f1": hasattr(metrics, "token_f1"),
            "ordered_lcs": hasattr(metrics, "ordered_lcs"),
        }
    except Exception as exc:  # pragma: no cover - dependency/path dependent.
        info["status"] = "import_failed"
        info["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        if inserted:
            try:
                sys.path.remove(str(src))
            except ValueError:
                pass
    return info


def inspect_maas_clone_backend(*, enable_import: bool | None = None) -> dict[str, Any]:
    should_import = enable_import if enable_import is not None else os.getenv("MAAS_CLONE_IMPORT", "1") != "0"
    return dict(_inspect_maas_clone_cached(bool(should_import)))


def run_maas_clone_reference_baseline(*, enable_import: bool | None = None) -> dict[str, Any]:
    backend = inspect_maas_clone_backend(enable_import=enable_import)
    result: dict[str, Any] = {
        "name": "MAAS",
        "source": "clone/MAAS",
        "backend": backend,
        "sequence_source": "clone/MAAS/tests/test_grammar.py::make_simple_seq",
        "missing_artifacts": [],
        "status": backend["status"],
    }
    if not backend.get("labels_exists"):
        result["missing_artifacts"].append({
            "path": backend.get("labels_path"),
            "expected_by": "clone/MAAS/src/maas/eval/case_studies.py",
            "impact": "book case-study labels cannot be used until restored",
        })
    if backend.get("status") != "imported":
        return result

    src = maas_clone_source_path()
    inserted = False
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))
        inserted = True
    try:
        verb_sequence_mod = importlib.import_module("maas.grammar.verb_sequence")
        compiler = importlib.import_module("maas.grammar.compiler")
        metrics = importlib.import_module("maas.eval.metrics")
        sequence_data = maas_clone_reference_sequence()
        seq = verb_sequence_mod.VerbSequence.from_dict(sequence_data)
        errors = seq.validate()
        result["sequence"] = sequence_data
        result["validate_errors"] = errors
        if errors:
            result["status"] = "validation_failed"
            return result
        scad = compiler.compile_sequence(seq)
        result["status"] = "compiled"
        result["scad_compile_status"] = "compiled"
        result["scad_text_hash"] = hashlib.sha256(scad.encode("utf-8")).hexdigest()
        result["scad_text_length"] = len(scad)
        result["scad_contains"] = {
            "cube": "cube" in scad,
            "difference": "difference" in scad,
            "hull": "hull" in scad,
        }
        comparison = metrics.compare_sequences(seq, seq)
        result["metric_summary"] = {
            "pred_len": comparison.pred_len,
            "gold_len": comparison.gold_len,
            "jaccard": comparison.jaccard,
            "token_f1": comparison.f1,
            "ordered_lcs": comparison.lcs,
            "lcs_score": comparison.lcs_score,
            "pred_verbs": comparison.pred_verbs,
            "gold_verbs": comparison.gold_verbs,
        }
    except Exception as exc:
        result["status"] = "baseline_failed"
        result["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        if inserted:
            try:
                sys.path.remove(str(src))
            except ValueError:
                pass
    return result


__all__ = [
    "inspect_maas_clone_backend",
    "maas_clone_labels_path",
    "maas_clone_license_summary",
    "maas_clone_reference_sequence",
    "maas_clone_source_path",
    "run_maas_clone_reference_baseline",
]
