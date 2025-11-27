"""
FastAPI A2A server for Domain 1

Based on: agent/a2a/langraph_agent/server.py
Implements: A2A protocol (JSON-RPC 2.0)
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from graph import domain_1_graph, Domain1State
from domain_logic import Domain1SearchLogic
from config import config
from dotenv import load_dotenv
import logging
import uuid

load_dotenv()

# Configure logging
logging.basicConfig(level=config.LOG_LEVEL)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title=f"Domain 1 Agent: {config.DOMAIN_NAME}",
    description=config.DOMAIN_DESCRIPTION,
    version="0.1.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize search logic
search_logic = Domain1SearchLogic()


@app.get("/.well-known/agent-card.json")
def get_agent_card():
    """
    A2A Protocol: Agent Card endpoint

    Returns agent metadata according to A2A protocol specification.
    Spec: https://a2a.dev/protocol#agent-card

    Returns:
        Agent card JSON
    """
    logger.info("Agent card requested")
    return config.get_agent_card()


@app.post("/messages")
async def handle_message(req: Request):
    """
    A2A Protocol: Message endpoint (JSON-RPC 2.0)

    Receives messages in JSON-RPC 2.0 format and processes them
    through the LangGraph workflow.

    Spec: https://a2a.dev/protocol#message-send

    Args:
        req: FastAPI request object

    Returns:
        JSON-RPC 2.0 response
    """
    try:
        body = await req.json()
        logger.info(f"Received message: {body.get('id', 'unknown')}")

        # Extract message from JSON-RPC params
        params = body.get("params", {})
        message_data = params.get("message", {})
        parts = message_data.get("parts", [])

        if not parts:
            logger.warning("No message parts provided")
            return JSONResponse(
                status_code=400,
                content={
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32602,
                        "message": "Invalid params: No message parts provided"
                    },
                    "id": body.get("id", "")
                }
            )

        # Combine all text parts
        message_text = "\n".join([
            part.get("text", "")
            for part in parts
            if part.get("kind") == "text" or "text" in part
        ])

        logger.info(f"Processing query: {message_text[:100]}...")

        # Invoke LangGraph workflow (async)
        result = await domain_1_graph.ainvoke({
            "messages": [{"role": "user", "content": message_text}]
        })

        # Extract last AI message
        last_message = result["messages"][-1]
        response_text = last_message.content if hasattr(last_message, 'content') else str(last_message)

        logger.info(f"Generated response: {response_text[:100]}...")

        # Build JSON-RPC 2.0 response
        response = {
            "jsonrpc": "2.0",
            "result": {
                "kind": "message",
                "role": "agent",
                "parts": [
                    {
                        "kind": "text",
                        "text": response_text
                    }
                ],
                "messageId": message_data.get("messageId", str(uuid.uuid4())),
                "contextId": message_data.get("contextId", str(uuid.uuid4()))
            },
            "id": body.get("id", "")
        }

        logger.info("Response sent successfully")
        return response

    except Exception as e:
        logger.error(f"Error handling message: {e}", exc_info=True)
        # Try to get request ID, but handle case where body wasn't parsed
        request_id = ""
        try:
            request_id = body.get("id", "")
        except:
            pass

        return JSONResponse(
            status_code=500,
            content={
                "jsonrpc": "2.0",
                "error": {
                    "code": -32000,
                    "message": f"Server error: {str(e)}"
                },
                "id": request_id
            }
        )


@app.get("/health")
def health_check():
    """
    Health check endpoint

    Returns:
        Health status and domain information
    """
    try:
        stats = search_logic.get_domain_stats()
        return {
            "status": "healthy",
            "domain": config.DOMAIN_NAME,
            "domain_id": config.DOMAIN_ID,
            "port": config.DOMAIN_PORT,
            "stats": stats,
            "version": "0.1.0"
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "domain": config.DOMAIN_NAME,
                "error": str(e)
            }
        )


@app.get("/")
def root():
    """
    Root endpoint with API information

    Returns:
        API information
    """
    return {
        "name": f"Domain 1 Agent: {config.DOMAIN_NAME}",
        "description": config.DOMAIN_DESCRIPTION,
        "version": "0.1.0",
        "endpoints": {
            "agent_card": "/.well-known/agent-card.json",
            "messages": "/messages (POST)",
            "health": "/health",
            "docs": "/docs"
        },
        "a2a_protocol": "0.3.0"
    }


if __name__ == "__main__":
    import uvicorn

    logger.info(f"Starting Domain 1 Agent on port {config.DOMAIN_PORT}")
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=config.DOMAIN_PORT,
        log_level=config.LOG_LEVEL.lower()
    )
