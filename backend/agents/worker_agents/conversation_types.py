"""
Agent-to-Agent Conversation Types
Type-safe definitions for real-time agent conversations
"""

from typing import TypedDict, Literal, Optional, Dict, Any, List, Union
from enum import Enum
from dataclasses import dataclass
from datetime import datetime
import uuid


class ConversationState(Enum):
    """Conversation state enumeration"""
    INITIATED = "initiated"
    ACTIVE = "active"
    DELEGATED = "delegated"
    STREAMING = "streaming"
    WAITING = "waiting"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class MessageRole(Enum):
    """Message role enumeration"""
    USER = "user"
    ASSISTANT = "assistant"
    AGENT = "agent"
    SYSTEM = "system"


class StreamEventType(Enum):
    """Stream event types following A2A standard"""
    MESSAGE = "message"
    TASK_STATUS = "task-status"
    TASK_ARTIFACT = "task-artifact"
    AGENT_SWITCH = "agent-switch"
    CONVERSATION_UPDATE = "conversation-update"
    ERROR = "error"


class AgentRole(Enum):
    """Agent roles in conversation"""
    COORDINATOR = "coordinator"
    SPECIALIST = "specialist"
    OBSERVER = "observer"
    PARTICIPANT = "participant"


# TypedDict definitions following A2A Protocol
class MessagePart(TypedDict):
    """Message part structure"""
    kind: Literal["text", "file", "image", "audio"]
    text: Optional[str]
    file: Optional[Dict[str, Any]]
    mimeType: Optional[str]
    data: Optional[str]  # base64 encoded


class A2AMessage(TypedDict):
    """A2A Protocol message structure"""
    messageId: str
    role: str
    parts: List[MessagePart]
    contextId: Optional[str]
    timestamp: str
    agentId: Optional[str]
    metadata: Optional[Dict[str, Any]]


class TaskStatus(TypedDict):
    """Task status following A2A standard"""
    state: str  # ConversationState enum value
    timestamp: str
    progress: Optional[float]  # 0.0 to 1.0
    details: Optional[str]


class TaskStatusUpdateEvent(TypedDict):
    """A2A TaskStatusUpdateEvent"""
    type: Literal["task-status"]
    taskId: str
    contextId: str
    status: TaskStatus
    final: bool
    kind: Literal["status-update"]


class TaskArtifact(TypedDict):
    """Task artifact structure"""
    artifactId: str
    parts: List[MessagePart]
    metadata: Optional[Dict[str, Any]]


class TaskArtifactUpdateEvent(TypedDict):
    """A2A TaskArtifactUpdateEvent"""
    type: Literal["task-artifact"]
    taskId: str
    contextId: str
    artifact: TaskArtifact
    append: bool
    lastChunk: bool
    final: bool
    kind: Literal["artifact-update"]


class SendStreamingMessageResponse(TypedDict):
    """A2A SendStreamingMessageResponse"""
    type: Literal["message"]
    message: A2AMessage
    contextId: str
    kind: Literal["streaming-response"]
    final: bool


# Agent conversation specific types
class AgentParticipant(TypedDict):
    """Agent participant in conversation"""
    agentId: str
    agentSlug: str
    agentName: str
    role: str  # AgentRole enum value
    capabilities: List[str]
    status: str  # online, busy, offline
    joinedAt: str


class ConversationContext(TypedDict):
    """Conversation context structure"""
    conversationId: str
    contextId: str
    sessionId: str
    initiatedBy: str  # user or agent ID
    topic: Optional[str]
    state: str  # ConversationState enum value
    participants: List[AgentParticipant]
    currentSpeaker: Optional[str]  # agent ID
    turnHistory: List[str]  # agent IDs in order
    createdAt: str
    updatedAt: str
    metadata: Dict[str, Any]


class AgentSwitchEvent(TypedDict):
    """Agent switch event structure"""
    type: Literal["agent-switch"]
    conversationId: str
    contextId: str
    previousAgent: str
    newAgent: str
    reason: str
    timestamp: str
    metadata: Optional[Dict[str, Any]]


class ConversationUpdateEvent(TypedDict):
    """Conversation update event"""
    type: Literal["conversation-update"]
    conversationId: str
    contextId: str
    updateType: str  # participant_joined, participant_left, topic_changed, etc.
    data: Dict[str, Any]
    timestamp: str


# JSON-RPC 2.0 structures for A2A
class JsonRpc2Request(TypedDict):
    """JSON-RPC 2.0 request structure"""
    jsonrpc: Literal["2.0"]
    method: str
    params: Dict[str, Any]
    id: str


class JsonRpc2Response(TypedDict):
    """JSON-RPC 2.0 response structure"""
    jsonrpc: Literal["2.0"]
    result: Optional[Dict[str, Any]]
    error: Optional[Dict[str, Any]]
    id: str


class StreamingResponse(TypedDict):
    """Streaming response union type"""
    jsonrpc: Literal["2.0"]
    result: Union[
        SendStreamingMessageResponse,
        TaskStatusUpdateEvent,
        TaskArtifactUpdateEvent,
        AgentSwitchEvent,
        ConversationUpdateEvent
    ]
    id: str


# Dataclasses for business logic
@dataclass
class ConversationTurn:
    """Represents a single turn in conversation"""
    turnId: str
    conversationId: str
    agentId: str
    agentSlug: str
    message: A2AMessage
    startedAt: datetime
    completedAt: Optional[datetime] = None
    duration: Optional[float] = None
    tokens: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "turnId": self.turnId,
            "conversationId": self.conversationId,
            "agentId": self.agentId,
            "agentSlug": self.agentSlug,
            "message": self.message,
            "startedAt": self.startedAt.isoformat(),
            "completedAt": self.completedAt.isoformat() if self.completedAt else None,
            "duration": self.duration,
            "tokens": self.tokens
        }


@dataclass
class ConversationSession:
    """Full conversation session state"""
    context: ConversationContext
    turns: List[ConversationTurn]
    currentTurn: Optional[ConversationTurn] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "context": self.context,
            "turns": [turn.to_dict() for turn in self.turns],
            "currentTurn": self.currentTurn.to_dict() if self.currentTurn else None
        }


# Helper functions for type creation
def create_conversation_id() -> str:
    """Generate unique conversation ID"""
    return f"conv_{uuid.uuid4().hex[:12]}"


def create_message_id() -> str:
    """Generate unique message ID"""
    return str(uuid.uuid4())


def create_task_id() -> str:
    """Generate unique task ID"""
    return f"task_{uuid.uuid4().hex[:12]}"


def create_artifact_id() -> str:
    """Generate unique artifact ID"""
    return f"artifact_{uuid.uuid4().hex[:12]}"


def current_timestamp() -> str:
    """Get current timestamp in ISO format"""
    return datetime.now().isoformat()


# Type guards for runtime type checking
def is_streaming_response(data: Dict[str, Any]) -> bool:
    """Check if data is a valid streaming response"""
    return (
        "jsonrpc" in data and
        data["jsonrpc"] == "2.0" and
        "result" in data and
        "id" in data
    )


def is_task_status_event(event: Dict[str, Any]) -> bool:
    """Check if event is a task status update"""
    return event.get("type") == "task-status" and "status" in event


def is_task_artifact_event(event: Dict[str, Any]) -> bool:
    """Check if event is a task artifact update"""
    return event.get("type") == "task-artifact" and "artifact" in event


def is_agent_switch_event(event: Dict[str, Any]) -> bool:
    """Check if event is an agent switch"""
    return event.get("type") == "agent-switch" and all(
        key in event for key in ["previousAgent", "newAgent"]
    )