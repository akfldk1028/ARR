# Agent Registry & Auto-Discovery Refactoring

**Date**: 2025-10-09
**Objective**: Eliminate hardcoded agent lists and implement metadata-driven, auto-discovery architecture for scalable multi-agent system

---

## 🎯 Problem Statement

### Critical Issues Before Refactoring

1. **Hardcoded Specialist Lists** (3 locations)
   - `gemini/consumers/handlers/a2a_handler.py:576-579` - specialist type check
   - `gemini/consumers/handlers/a2a_handler.py:587-590` - current agent check
   - Manual updates required for every new specialist

2. **Manual Worker Registration**
   - `agents/worker_agents/worker_factory.py:11` - manual imports
   - `agents/worker_agents/worker_factory.py:19-22` - manual dictionary entries
   - Forgot to register `HotelSpecialistWorkerAgent` → caused routing bugs

3. **Hardcoded Routing Thresholds**
   - `specialist_threshold = 0.70` buried in code
   - `confidence_gap_threshold = 0.01` not configurable
   - No per-agent customization

4. **Specialist-to-Specialist Switching Bug**
   - User: "호텔예약해줘" → Hotel Specialist ✓
   - User: "아니다 비행기예약해줘" → Stuck on Hotel Specialist ✗
   - Fallback logic didn't consider current agent context

---

## ✅ Solution: Metadata-Driven Auto-Discovery

### Architecture Overview

```
JSON Agent Cards (Source of Truth)
    ↓
AgentRegistry (Metadata Manager)
    ↓
├── Agent Type Detection (specialist, coordinator, custom)
├── Routing Threshold Configuration
└── Auto-Discovery of Available Agents
    ↓
WorkerFactory (Auto-Registration)
    ↓
Worker Class Auto-Discovery from implementations/
```

---

## 📦 New Components Created

### 1. `agents/worker_agents/agent_registry.py` (230 lines)

**Purpose**: Centralized metadata management for all agents

**Key Classes**:

```python
@dataclass
class AgentMetadata:
    slug: str
    name: str
    agent_type: str  # "coordinator", "specialist", "orchestrator"
    worker_class: str
    capabilities: Dict[str, bool]

    # Routing configuration (from JSON card)
    specialist_threshold: float = 0.70
    general_threshold: float = 0.50
    confidence_gap_threshold: float = 0.01

    @property
    def is_specialist(self) -> bool:
        return self.agent_type == "specialist"
```

**Core API**:

```python
class AgentRegistry:
    @classmethod
    def load_registry(cls, force_reload: bool = False):
        """Auto-load from JSON cards in cards/ directory"""

    @classmethod
    def is_specialist(cls, agent_slug: str) -> bool:
        """Check if agent is specialist (metadata-driven)"""

    @classmethod
    def get_specialist_slugs(cls) -> List[str]:
        """Get all specialist agent slugs automatically"""

    @classmethod
    def get_routing_thresholds(cls, agent_slug: str) -> Dict[str, float]:
        """Get routing config from JSON card"""
```

**Usage Example**:

```python
from agents.worker_agents.agent_registry import AgentRegistry

# Instead of hardcoded list:
# is_specialist = agent in ['flight-specialist', 'hotel-specialist']

# Use metadata-driven approach:
is_specialist = AgentRegistry.is_specialist(agent)
```

---

## 🔧 Modified Components

### 2. `gemini/consumers/handlers/a2a_handler.py` (Lines 561-591)

**Before** (Hardcoded):
```python
# Lines 576-579: Hardcoded specialist list
is_specialist = best_agent in [
    'flight-specialist', 'hotel-specialist',
    'flight_specialist', 'hotel_specialist'
]

# Lines 567-569: Hardcoded thresholds
specialist_threshold = 0.70
general_threshold = 0.5
confidence_gap_threshold = 0.01
```

**After** (Metadata-Driven):
```python
# ============== AGENT REGISTRY-BASED ROUTING ==============
from agents.worker_agents.agent_registry import AgentRegistry

AgentRegistry.load_registry()

# Get routing thresholds from JSON card
thresholds = AgentRegistry.get_routing_thresholds(best_agent)
specialist_threshold = thresholds['specialist_threshold']
general_threshold = thresholds['general_threshold']
confidence_gap_threshold = thresholds['confidence_gap_threshold']

# Check if agent is specialist (metadata-driven)
is_specialist = AgentRegistry.is_specialist(best_agent)
current_is_specialist = AgentRegistry.is_specialist(current_agent)
```

**Key Changes**:
- No more hardcoded agent lists (lines 576-579, 587-590 removed)
- Thresholds loaded from JSON cards
- Automatic specialist detection

---

### 3. `agents/worker_agents/worker_factory.py`

**Before** (Manual Registration):
```python
from .implementations import HostAgent, FlightSpecialistWorkerAgent, HotelSpecialistWorkerAgent

_WORKER_CLASSES: Dict[str, Type[BaseWorkerAgent]] = {
    'HostAgent': HostAgent,
    'FlightSpecialistWorkerAgent': FlightSpecialistWorkerAgent,
    'HotelSpecialistWorkerAgent': HotelSpecialistWorkerAgent,  # Forgot this → BUG!
}
```

**After** (Auto-Discovery):
```python
from . import implementations

_WORKER_CLASSES: Dict[str, Type[BaseWorkerAgent]] = {}  # Auto-populated

@classmethod
def _auto_discover_workers(cls):
    """Auto-discover worker classes from implementations module"""
    logger.info("Auto-discovering worker agent classes...")

    for class_name in implementations.__all__:
        worker_class = getattr(implementations, class_name, None)

        if (inspect.isclass(worker_class) and
            issubclass(worker_class, BaseWorkerAgent) and
            worker_class is not BaseWorkerAgent):

            cls._WORKER_CLASSES[class_name] = worker_class
            logger.info(f"  ✓ Registered: {class_name}")

    logger.info(f"Auto-discovery complete: {len(cls._WORKER_CLASSES)} worker classes available")
```

**Key Changes**:
- Uses Python reflection to scan `implementations.__all__`
- Automatically registers all `BaseWorkerAgent` subclasses
- No manual import statements needed
- Logs all registered classes at startup

---

### 4. JSON Agent Cards - Added `routing_config`

**`agents/worker_agents/cards/flight_specialist_card.json`**:
```json
{
  "name": "Flight Specialist Agent",
  "django": {
    "agent_type": "specialist",
    "worker_class": "FlightSpecialistWorkerAgent",
    "model_config": {
      "provider": "openai",
      "model_name": "gpt-4o-mini"
    },
    "routing_config": {
      "specialist_threshold": 0.70,
      "general_threshold": 0.50,
      "confidence_gap_threshold": 0.01
    }
  }
}
```

**Same for `hotel_specialist_card.json`**

**Key Addition**:
- `routing_config` section with tunable thresholds
- Per-agent threshold customization possible
- Configuration-driven instead of code-driven

---

## 🚀 How to Add New Specialist Agent

### Before (6 steps, 5 files to modify)

1. Write worker class implementation
2. Add import to `implementations/__init__.py`
3. Add import to `worker_factory.py` line 11
4. Add to `_WORKER_CLASSES` dict in `worker_factory.py` line 19-22
5. Add to hardcoded list in `a2a_handler.py` line 576-579
6. Add to hardcoded list in `a2a_handler.py` line 587-590
7. Create JSON card

### After (3 steps, 2 files to modify)

1. **Write Worker Class**:
   ```python
   # agents/worker_agents/implementations/restaurant_specialist_worker.py
   from ..base import BaseWorkerAgent

   class RestaurantSpecialistWorkerAgent(BaseWorkerAgent):
       async def process(self, message):
           # Implementation
   ```

2. **Register in `implementations/__init__.py`**:
   ```python
   from .restaurant_specialist_worker import RestaurantSpecialistWorkerAgent

   __all__ = [
       'HostAgent',
       'FlightSpecialistWorkerAgent',
       'HotelSpecialistWorkerAgent',
       'RestaurantSpecialistWorkerAgent',  # Add this line
   ]
   ```

3. **Create JSON Card**:
   ```json
   {
     "name": "Restaurant Specialist Agent",
     "django": {
       "agent_type": "specialist",  // CRITICAL: Mark as specialist
       "worker_class": "RestaurantSpecialistWorkerAgent",
       "routing_config": {
         "specialist_threshold": 0.70,
         "confidence_gap_threshold": 0.01
       }
     },
     "skills": [
       {
         "id": "restaurant_booking",
         "tags": ["restaurant", "식당", "예약"],
         "examples": ["식당 예약해줘", "레스토랑 찾아줘"]
       }
     ]
   }
   ```

**Done!** Auto-discovery handles the rest.

---

## 🔄 Startup Logs (Auto-Discovery in Action)

```
[INFO] Auto-discovering worker agent classes...
[INFO]   ✓ Registered: HostAgent
[INFO]   ✓ Registered: FlightSpecialistWorkerAgent
[INFO]   ✓ Registered: HotelSpecialistWorkerAgent
[INFO] Auto-discovery complete: 3 worker classes available

[INFO] Building agent registry from 3 cards...
[INFO]   🔄 COORDINATOR: hostagent -> HostAgent
[INFO]   🎯 SPECIALIST: flight-specialist -> FlightSpecialistWorkerAgent
[INFO]   🎯 SPECIALIST: hotel-specialist -> HotelSpecialistWorkerAgent
[INFO] Agent registry ready: 3 agents registered
[INFO]   Specialists: flight-specialist, hotel-specialist
[INFO]   Coordinators: hostagent
```

---

## 🐛 Bug Fixes Included

### Issue 1: Hotel Specialist Not Registered
**Before**: `HotelSpecialistWorkerAgent` imported but not added to `_WORKER_CLASSES`
**After**: Auto-discovery ensures all classes in `__all__` are registered

### Issue 2: Specialist-to-Specialist Switching Failed
**Before**:
```
User: "호텔예약해줘" → Hotel Specialist ✓
User: "아니다 비행기예약해줘" → Hotel Specialist ✗ (stuck!)
```

**After** (Priority-Based Routing):
```python
# PRIORITY 1: Specialist-to-specialist switching (relaxed criteria)
if current_is_specialist and is_specialist and best_agent != current_agent:
    if best_score >= specialist_threshold:  # Only threshold, no gap required
        should_delegate = True
        logger.info(f"Specialist-to-specialist switch: {current_agent} -> {best_agent}")
```

**Result**:
```
User: "호텔예약해줘" → Hotel Specialist ✓
User: "아니다 비행기예약해줘" → Flight Specialist ✓ (switches!)
```

---

## 📊 Files Changed Summary

| File | Lines Changed | Type |
|------|---------------|------|
| `agents/worker_agents/agent_registry.py` | +230 | NEW |
| `gemini/consumers/handlers/a2a_handler.py` | 561-591 (30 lines) | MODIFIED |
| `agents/worker_agents/worker_factory.py` | 1-102 (major refactor) | MODIFIED |
| `agents/worker_agents/cards/flight_specialist_card.json` | +5 (routing_config) | MODIFIED |
| `agents/worker_agents/cards/hotel_specialist_card.json` | +5 (routing_config) | MODIFIED |

---

## 🎯 Benefits

1. **Scalability**: Add new specialists with 3 file changes (down from 6)
2. **Maintainability**: No hardcoded lists scattered across codebase
3. **Configuration-Driven**: Thresholds in JSON, not buried in code
4. **Bug Prevention**: Auto-discovery prevents registration oversights
5. **Clear Separation**: Metadata (AgentRegistry) vs Logic (A2AHandler)

---

## 🧪 Testing

### Manual Test Sequence
1. Connect to `ws://localhost:8002/ws/chat/`
2. Send: `{"type": "chat_message", "message": "호텔예약해줘"}`
3. Verify: Hotel Specialist responds
4. Send: `{"type": "chat_message", "message": "아니다 비행기예약해줘"}`
5. Verify: Flight Specialist responds (specialist-to-specialist switch)

### Expected Server Logs
```
[INFO] Semantic routing: hotel-specialist (score: 0.969, gap: 0.012)
[INFO] Delegating to: hotel-specialist (confidence: 0.969)
...
[INFO] Semantic routing: flight-specialist (score: 0.979, gap: 0.008)
[INFO] Specialist-to-specialist switch: hotel-specialist -> flight-specialist (score: 0.979 >= 0.70)
[INFO] Delegating to: flight-specialist (confidence: 0.979)
```

---

## 📚 References

- **AgentRegistry API**: `agents/worker_agents/agent_registry.py`
- **Auto-Discovery Logic**: `agents/worker_agents/worker_factory.py:30-58`
- **Routing Implementation**: `gemini/consumers/handlers/a2a_handler.py:561-627`
- **JSON Card Spec**: `agents/worker_agents/cards/*.json`

---

## 💡 Design Principles Applied

1. **DRY (Don't Repeat Yourself)**: Eliminated 3 hardcoded specialist lists
2. **Convention over Configuration**: JSON cards as single source of truth
3. **Reflection over Registration**: Auto-discovery using Python introspection
4. **Separation of Concerns**: Metadata (Registry) vs Logic (Handler)
5. **Open/Closed Principle**: Open for extension (new agents), closed for modification (no code changes in handler)

---

## 🔮 Future Enhancements

1. **Dynamic Threshold Tuning**: A/B testing different thresholds per agent
2. **Multi-Tier Specialists**: Junior/Senior specialist hierarchy
3. **Agent Capability Matching**: Route based on capabilities, not just similarity
4. **Hot Reload**: Detect new JSON cards without server restart
5. **Agent Performance Metrics**: Track routing accuracy per specialist

---

**Author**: Claude Code (Anthropic)
**Last Updated**: 2025-10-09
**Status**: ✅ Production Ready
