#!/usr/bin/env python3
"""
A2A Voice Server Runner - Start the voice-enabled A2A agent system
Integrates Gemini Live API with A2A agents for real-time voice conversations
"""

import os
import sys
import logging
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Configure Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

# Setup Django
import django
django.setup()

from agents.voice.websocket_server import run_voice_server

def main():
    """Main entry point for A2A Voice Server"""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    logger = logging.getLogger(__name__)

    # Check required environment variables
    required_env_vars = ['GOOGLE_API_KEY']
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]

    if missing_vars:
        logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
        logger.error("Please set these variables in your .env file or environment")
        sys.exit(1)

    # Start the voice server
    try:
        logger.info("Starting A2A Voice Server with Gemini Live API...")
        run_voice_server(host="localhost", port=8004)
    except KeyboardInterrupt:
        logger.info("Voice server stopped by user")
    except Exception as e:
        logger.error(f"Error running voice server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()