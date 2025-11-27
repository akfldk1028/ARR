#!/usr/bin/env python3
"""
Run Domain 1 Agent

Quick launcher for Domain 1 agent server.
"""

import sys
import os
from pathlib import Path

# Add domain-1-agent to path
domain_path = Path(__file__).parent / "domain-1-agent"
sys.path.insert(0, str(domain_path))

# Add parent directory for shared imports
sys.path.insert(0, str(Path(__file__).parent))

if __name__ == "__main__":
    import uvicorn
    from domain_logic import Domain1SearchLogic  # Import to verify setup
    from config import config

    print(f"""
╔══════════════════════════════════════════════════════════════╗
║ Law Domain Agent - Domain 1                                  ║
║ {config.DOMAIN_NAME:<58} ║
╚══════════════════════════════════════════════════════════════╝

Domain ID:    {config.DOMAIN_ID}
Port:         {config.DOMAIN_PORT}
Description:  {config.DOMAIN_DESCRIPTION}

Endpoints:
  - Agent Card:  http://localhost:{config.DOMAIN_PORT}/.well-known/agent-card.json
  - Messages:    http://localhost:{config.DOMAIN_PORT}/messages
  - Health:      http://localhost:{config.DOMAIN_PORT}/health
  - API Docs:    http://localhost:{config.DOMAIN_PORT}/docs

Starting server...
""")

    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=config.DOMAIN_PORT,
        reload=True,
        log_level=config.LOG_LEVEL.lower()
    )
