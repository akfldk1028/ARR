"""
A2A Streaming Communication Protocol
Real-time agent-to-agent communication following Context7 A2A standard
"""

import asyncio
import json
import logging
import time
from typing import Dict, Any, Optional, Callable, AsyncGenerator, List
from uuid import uuid4
from datetime import datetime
from contextlib import asynccontextmanager

import httpx
from django.conf import settings

from .conversation_types import (
    A2AMessage, StreamingResponse, TaskStatusUpdateEvent, TaskArtifactUpdateEvent,
    AgentSwitchEvent, ConversationUpdateEvent, JsonRpc2Request, JsonRpc2Response,
    ConversationState, StreamEventType, MessageRole, MessagePart,
    create_message_id, create_task_id, current_timestamp
)
from ..a2a_client import A2AAgentCard, A2ACardResolver

logger = logging.getLogger(__name__)
stream_logger = logging.getLogger('agents.a2a_streaming')


class A2AStreamingError(Exception):
    """Base exception for A2A streaming errors"""
    pass


class A2AStreamingClient:
    """
    A2A Streaming Client supporting message/stream endpoint
    Implements Context7 A2A Protocol with Server-Sent Events (SSE)
    """

    def __init__(self, target_agent_card: A2AAgentCard, timeout: float = 60.0):
        self.agent_card = target_agent_card
        self.timeout = timeout
        self._active_streams: Dict[str, asyncio.Task] = {}

    async def send_streaming_message(
        self,
        message: str,
        context_id: str,
        session_id: str,
        callback: Optional[Callable[[StreamingResponse], None]] = None
    ) -> AsyncGenerator[StreamingResponse, None]:
        """
        Send streaming message using A2A message/stream endpoint
        Returns async generator yielding StreamingResponse events
        """
        task_id = create_task_id()
        message_id = create_message_id()

        stream_logger.info(f"Starting A2A stream: task_id={task_id}, target={self.agent_card.name}")

        # Get streaming endpoint (message/stream)
        base_url = self.agent_card.endpoints.get('jsonrpc') or self.agent_card.endpoints.get('a2a')
        if not base_url:
            raise A2AStreamingError(f"No streaming endpoint found for {self.agent_card.name}")

        # Support both direct endpoint and message/stream path
        if not base_url.endswith('/message/stream'):
            stream_url = f"{base_url.rstrip('/')}/message/stream"
        else:
            stream_url = base_url

        # Prepare A2A message/stream request
        request_payload = JsonRpc2Request(
            jsonrpc="2.0",
            method="message/stream",
            params={
                "message": A2AMessage(
                    messageId=message_id,
                    role=MessageRole.USER.value,
                    parts=[MessagePart(
                        kind="text",
                        text=message,
                        file=None,
                        mimeType=None,
                        data=None
                    )],
                    contextId=context_id,
                    timestamp=current_timestamp(),
                    agentId="user",
                    metadata={"sessionId": session_id, "taskId": task_id}
                ),
                "configuration": {
                    "streaming": True,
                    "capabilities": ["streaming", "pushNotifications"]
                },
                "metadata": {
                    "taskId": task_id,
                    "sessionId": session_id,
                    "clientId": "a2a_streaming_client"
                }
            },
            id=message_id
        )

        # Headers for SSE
        headers = {
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive"
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                # Send streaming request
                stream_logger.info(f"Sending A2A streaming request to: {stream_url}")

                async with client.stream(
                    "POST",
                    stream_url,
                    json=request_payload,
                    headers=headers
                ) as response:
                    response.raise_for_status()

                    if response.headers.get("content-type") != "text/event-stream":
                        raise A2AStreamingError(
                            f"Expected text/event-stream, got {response.headers.get('content-type')}"
                        )

                    stream_logger.info(f"SSE stream established with {self.agent_card.name}")

                    # Process Server-Sent Events
                    async for chunk in self._parse_sse_stream(response.aiter_lines()):
                        if callback:
                            await callback(chunk)
                        yield chunk

            except httpx.HTTPStatusError as e:
                stream_logger.error(f"HTTP error in A2A streaming: {e.response.status_code}")
                raise A2AStreamingError(f"HTTP {e.response.status_code}: {e.response.text}")
            except Exception as e:
                stream_logger.error(f"Error in A2A streaming: {e}")
                raise A2AStreamingError(f"Streaming failed: {str(e)}")

    async def _parse_sse_stream(self, lines: AsyncGenerator[str, None]) -> AsyncGenerator[StreamingResponse, None]:
        """Parse Server-Sent Events stream into A2A streaming responses"""
        current_event = {}
        event_type = None

        async for line in lines:
            line = line.strip()

            if not line:
                # Empty line indicates end of event
                if current_event.get("data"):
                    try:
                        # Parse JSON-RPC 2.0 response from SSE data
                        sse_data = json.loads(current_event["data"])

                        if self._is_valid_jsonrpc_response(sse_data):
                            streaming_response = StreamingResponse(
                                jsonrpc="2.0",
                                result=sse_data.get("result", {}),
                                id=sse_data.get("id", "")
                            )
                            yield streaming_response

                        current_event = {}
                        event_type = None

                    except json.JSONDecodeError as e:
                        stream_logger.warning(f"Invalid JSON in SSE data: {e}")
                        continue

            elif line.startswith("event:"):
                event_type = line[6:].strip()
                current_event["event"] = event_type

            elif line.startswith("data:"):
                data = line[5:].strip()
                if "data" not in current_event:
                    current_event["data"] = data
                else:
                    current_event["data"] += "\n" + data

            elif line.startswith("id:"):
                current_event["id"] = line[3:].strip()

            elif line.startswith("retry:"):
                current_event["retry"] = int(line[6:].strip())

    def _is_valid_jsonrpc_response(self, data: Dict[str, Any]) -> bool:
        """Validate JSON-RPC 2.0 response structure"""
        return (
            isinstance(data, dict) and
            data.get("jsonrpc") == "2.0" and
            ("result" in data or "error" in data) and
            "id" in data
        )

    async def close_stream(self, task_id: str):
        """Close active streaming connection"""
        if task_id in self._active_streams:
            task = self._active_streams[task_id]
            task.cancel()
            del self._active_streams[task_id]
            stream_logger.info(f"Closed A2A stream: {task_id}")


class A2AConversationStreamer:
    """
    High-level agent conversation streamer
    Manages multi-agent conversations with real-time updates
    """

    def __init__(self):
        self._active_conversations: Dict[str, Dict[str, Any]] = {}
        self._stream_clients: Dict[str, A2AStreamingClient] = {}

    async def start_agent_conversation(
        self,
        conversation_id: str,
        agent_slugs: List[str],
        initial_message: str,
        context_id: str,
        session_id: str,
        websocket_callback: Optional[Callable] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Start multi-agent conversation with streaming updates
        """
        stream_logger.info(f"Starting agent conversation: {conversation_id} with agents: {agent_slugs}")

        # Initialize conversation state
        conversation_state = {
            "conversationId": conversation_id,
            "contextId": context_id,
            "sessionId": session_id,
            "agents": agent_slugs,
            "currentAgent": 0,
            "state": ConversationState.INITIATED.value,
            "startedAt": current_timestamp(),
            "turns": []
        }
        self._active_conversations[conversation_id] = conversation_state

        try:
            # Send initial status update
            if websocket_callback:
                await websocket_callback({
                    "type": "conversation_started",
                    "conversationId": conversation_id,
                    "agents": agent_slugs,
                    "initialMessage": initial_message
                })

            # Start conversation with first agent
            current_agent_slug = agent_slugs[0]
            conversation_state["state"] = ConversationState.ACTIVE.value

            # Get agent card and create streaming client
            resolver = A2ACardResolver("http://localhost:8002")
            agent_card = await resolver.get_agent_card(current_agent_slug)

            if not agent_card:
                raise A2AStreamingError(f"Could not get agent card for {current_agent_slug}")

            streaming_client = A2AStreamingClient(agent_card)
            self._stream_clients[conversation_id] = streaming_client

            # Create callback for streaming updates
            async def stream_callback(response: StreamingResponse):
                if websocket_callback:
                    await websocket_callback({
                        "type": "agent_stream_update",
                        "conversationId": conversation_id,
                        "agentSlug": current_agent_slug,
                        "data": response
                    })

            # Start streaming conversation
            async for response in streaming_client.send_streaming_message(
                message=initial_message,
                context_id=context_id,
                session_id=session_id,
                callback=stream_callback
            ):
                # Process different types of streaming responses
                result = response.get("result", {})

                if result.get("kind") == "streaming-response":
                    # Regular message response
                    yield {
                        "type": "agent_message",
                        "conversationId": conversation_id,
                        "agentSlug": current_agent_slug,
                        "message": result.get("message"),
                        "final": result.get("final", False)
                    }

                elif result.get("kind") == "status-update":
                    # Task status update
                    status = result.get("status", {})
                    yield {
                        "type": "conversation_status",
                        "conversationId": conversation_id,
                        "status": status,
                        "final": result.get("final", False)
                    }

                elif result.get("kind") == "artifact-update":
                    # Artifact update (e.g., file, image, etc.)
                    artifact = result.get("artifact", {})
                    yield {
                        "type": "conversation_artifact",
                        "conversationId": conversation_id,
                        "artifact": artifact,
                        "append": result.get("append", False),
                        "lastChunk": result.get("lastChunk", False)
                    }

                # Check if conversation should continue with next agent
                if result.get("final") and len(agent_slugs) > 1:
                    # Switch to next agent
                    next_agent_index = (conversation_state["currentAgent"] + 1) % len(agent_slugs)
                    if next_agent_index != conversation_state["currentAgent"]:
                        await self._switch_to_next_agent(
                            conversation_id, agent_slugs[next_agent_index],
                            response, websocket_callback
                        )

        except Exception as e:
            stream_logger.error(f"Error in agent conversation {conversation_id}: {e}")
            conversation_state["state"] = ConversationState.FAILED.value
            if websocket_callback:
                await websocket_callback({
                    "type": "conversation_error",
                    "conversationId": conversation_id,
                    "error": str(e)
                })
            raise

        finally:
            # Cleanup
            conversation_state["state"] = ConversationState.COMPLETED.value
            conversation_state["completedAt"] = current_timestamp()

    async def _switch_to_next_agent(
        self,
        conversation_id: str,
        next_agent_slug: str,
        previous_response: StreamingResponse,
        websocket_callback: Optional[Callable]
    ):
        """Switch conversation to next agent"""
        stream_logger.info(f"Switching conversation {conversation_id} to agent: {next_agent_slug}")

        # Send agent switch event
        switch_event = AgentSwitchEvent(
            type="agent-switch",
            conversationId=conversation_id,
            contextId=self._active_conversations[conversation_id]["contextId"],
            previousAgent=self._active_conversations[conversation_id]["agents"][
                self._active_conversations[conversation_id]["currentAgent"]
            ],
            newAgent=next_agent_slug,
            reason="conversation_continuation",
            timestamp=current_timestamp(),
            metadata={"previousResponse": previous_response}
        )

        if websocket_callback:
            await websocket_callback({
                "type": "agent_switch",
                "conversationId": conversation_id,
                "switchEvent": switch_event
            })

    async def stop_conversation(self, conversation_id: str):
        """Stop active conversation"""
        if conversation_id in self._active_conversations:
            conversation_state = self._active_conversations[conversation_id]
            conversation_state["state"] = ConversationState.CANCELLED.value
            conversation_state["stoppedAt"] = current_timestamp()

            # Close streaming client
            if conversation_id in self._stream_clients:
                # Cancel streaming task
                streaming_client = self._stream_clients[conversation_id]
                await streaming_client.close_stream(conversation_id)
                del self._stream_clients[conversation_id]

            stream_logger.info(f"Stopped conversation: {conversation_id}")

    def get_conversation_status(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """Get current conversation status"""
        return self._active_conversations.get(conversation_id)

    def list_active_conversations(self) -> List[str]:
        """List all active conversation IDs"""
        return [
            conv_id for conv_id, state in self._active_conversations.items()
            if state["state"] in [ConversationState.ACTIVE.value, ConversationState.STREAMING.value]
        ]


# Global instance
conversation_streamer = A2AConversationStreamer()


# Utility functions
async def create_streaming_client_for_agent(agent_slug: str) -> Optional[A2AStreamingClient]:
    """Create streaming client for specific agent"""
    try:
        resolver = A2ACardResolver("http://localhost:8002")
        agent_card = await resolver.get_agent_card(agent_slug)

        if agent_card:
            return A2AStreamingClient(agent_card)
        return None
    except Exception as e:
        logger.error(f"Failed to create streaming client for {agent_slug}: {e}")
        return None


async def test_agent_streaming_connection(agent_slug: str) -> bool:
    """Test if agent supports streaming"""
    try:
        client = await create_streaming_client_for_agent(agent_slug)
        if client and "streaming" in client.agent_card.capabilities:
            return True
        return False
    except Exception:
        return False