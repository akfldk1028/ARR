"""
Centralized configuration for the design app.

All env vars, timeouts, and shared clients live here.
"""

import atexit
import os

import httpx

# ── Env vars ─────────────────────────────────────────
VWORLD_API_KEY: str = os.getenv("VWORLD_API_KEY", "")

# ── Timeouts ─────────────────────────────────────────
VWORLD_TIMEOUT = httpx.Timeout(10.0, connect=5.0)

# ── Shared httpx clients ─────────────────────────────
# Note: land/ services are imported directly (same Django process).
# Only external APIs need httpx clients.
vworld_client = httpx.Client(timeout=VWORLD_TIMEOUT)


def _cleanup_clients():
    try:
        vworld_client.close()
    except Exception:
        pass


atexit.register(_cleanup_clients)
