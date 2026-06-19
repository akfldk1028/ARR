from __future__ import annotations

import os
from pathlib import Path

from django.core.management.base import BaseCommand

from design.maas.training.export_job_sft import export_job_sft
from design.maas.training.export_sft_seed import export_sft_seed


class Command(BaseCommand):
    help = "Export MAAS intent/review fine-tuning JSONL datasets."

    def add_arguments(self, parser):
        parser.add_argument(
            "--out-dir",
            default="docs/ai-session-memory/datasets",
            help="Output directory relative to repository root or absolute path.",
        )
        parser.add_argument("--limit", type=int, default=100)
        parser.add_argument("--job-id", default=None)
        parser.add_argument("--skip-db", action="store_true")
        parser.add_argument(
            "--include-graph",
            action="store_true",
            help="Allow evidence export to query Neo4j law provenance if configured.",
        )

    def handle(self, *args, **options):
        repo_root = Path(__file__).resolve().parents[5]
        out_dir = Path(options["out_dir"])
        if not out_dir.is_absolute():
            out_dir = repo_root / out_dir
        out_dir.mkdir(parents=True, exist_ok=True)

        seed_path = export_sft_seed(out_dir / "maas_intent_sft_seed.jsonl")
        self.stdout.write(self.style.SUCCESS(f"wrote {seed_path}"))

        if not options["skip_db"]:
            if not options["include_graph"]:
                os.environ.pop("NEO4J_URI", None)
            review_path = export_job_sft(
                out_dir / "maas_evidence_review_sft.jsonl",
                limit=options["limit"],
                job_id=options["job_id"],
            )
            self.stdout.write(self.style.SUCCESS(f"wrote {review_path}"))
