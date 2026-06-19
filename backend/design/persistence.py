"""
Persistence helpers for design optimization.

All saves are non-fatal (wrapped in try/except).
"""

import logging

from design.models import OptimizationJob, DesignResult

logger = logging.getLogger(__name__)


def save_job(job_data: dict) -> OptimizationJob | None:
    """Create OptimizationJob record (non-fatal on failure)."""
    try:
        return OptimizationJob.objects.create(**job_data)
    except Exception as e:
        logger.warning(f"OptimizationJob save failed (non-fatal): {e}")
        return None


def save_results(job: OptimizationJob, designs: list[dict]) -> int:
    """Bulk-create DesignResult records. Returns count saved."""
    try:
        objs = [DesignResult(job=job, **d) for d in designs]
        created = DesignResult.objects.bulk_create(objs)
        return len(created)
    except Exception as e:
        logger.warning(f"DesignResult bulk save failed (non-fatal): {e}")
        return 0


def update_job_status(job_id, status: str, **kwargs) -> bool:
    """Update job status (non-fatal on failure)."""
    try:
        OptimizationJob.objects.filter(id=job_id).update(status=status, **kwargs)
        return True
    except Exception as e:
        logger.warning(f"Job status update failed (non-fatal): {e}")
        return False
