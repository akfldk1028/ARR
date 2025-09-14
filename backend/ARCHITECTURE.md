# Django Multi-Agent System Architecture Plan

## Current State (Phase 1): Simplified Foundation

```
backend/
├── backend/                    # Django project settings
│   ├── settings.py            # Main settings + environment loading
│   ├── asgi.py               # ASGI config with Channels
│   └── urls.py               # Root URL configuration
├── gemini/                    # Current unified app (temporary)
│   ├── models.py             # Simple ChatSession & ChatMessage
│   ├── consumers/            # WebSocket handlers
│   │   ├── base.py          # Base consumer with optimization
│   │   └── simple_consumer.py # Main chat consumer
│   ├── services/             # Business logic layer
│   │   ├── gemini_client.py  # Optimized Gemini API client
│   │   └── service_manager.py # Singleton service manager
│   ├── config/               # Configuration management
│   └── utils/                # Utilities & logging
└── templates/gemini/          # Frontend interface
```

**Current Features:**
- ✅ Single-user chat sessions
- ✅ Text & image processing
- ✅ WebSocket real-time communication
- ✅ Optimized Gemini Live API integration
- ✅ Connection pooling & error handling
- ✅ Message persistence
- ✅ Admin interface

## Future Architecture (Phase 2): Modular App Structure

Based on your suggested structure, here's the expansion plan:

```
apps/
├── django-api/                # Main Django + DRF + Channels
│   ├── config/               # Centralized configuration
│   │   ├── settings/         # Environment-specific settings
│   │   ├── asgi.py           # ASGI with routing
│   │   ├── urls.py           # API routing
│   │   └── logging.py        # Structured logging
│   └── manage.py
├── core/                     # 🔧 Shared components
│   ├── models.py            # Base models (org/tenant, tags)
│   ├── permissions.py       # RBAC, API key auth
│   ├── pagination.py        # Standardized pagination
│   └── middleware.py        # Idempotency, rate limiting
├── authz/                    # 🔐 Authentication & Authorization
│   ├── models.py            # User, Role, Permission models
│   ├── oauth.py             # OAuth2 integration
│   ├── api_keys.py          # API key management
│   └── rbac.py              # Role-based access control
├── agents/                   # 🤖 Agent Management
│   ├── models.py            # Agent definitions & configurations
│   ├── serializers.py       # DRF serializers for API
│   ├── views.py             # Agent CRUD operations
│   ├── registry.py          # Agent discovery & health checks
│   └── orchestrator.py      # Multi-agent coordination
├── conversations/            # 💬 Chat & Session Management
│   ├── models.py            # Sessions, Messages, Rooms
│   ├── consumers.py         # WebSocket chat consumers
│   ├── serializers.py       # Message & session serializers
│   └── views.py             # REST API for chat history
├── tasks/                    # ⚡ Job & Task Management
│   ├── models.py            # Task, Job, ExecutionRequest
│   ├── workers.py           # Celery/RQ task workers
│   ├── retry.py             # Retry policies & strategies
│   └── monitoring.py        # Task status & monitoring
├── rules/                    # 📋 Rules & Policies Engine
│   ├── models.py            # Rule definitions, guardrails
│   ├── engine.py            # Rule evaluation engine
│   ├── routing.py           # Message routing rules
│   └── validators.py        # Policy validation
├── registry/                 # 📊 Service Discovery
│   ├── models.py            # Service registration
│   ├── health.py            # Health check aggregation
│   ├── discovery.py         # Service discovery logic
│   └── metrics.py           # Service metrics collection
├── events/                   # 📡 Event Streaming & Audit
│   ├── models.py            # Event log, audit trail
│   ├── streams.py           # Event streaming logic
│   ├── audit.py             # Audit log management
│   └── telemetry.py         # OpenTelemetry integration
├── mcp/                      # 🔌 MCP (Model Context Protocol) Integration
│   ├── models.py            # MCP connector metadata
│   ├── connectors.py        # MCP protocol handlers
│   ├── permissions.py       # MCP-specific permissions
│   └── registry.py          # MCP service registry
├── billing/                  # 💳 Usage & Cost Tracking
│   ├── models.py            # Usage metrics, cost calculation
│   ├── collectors.py        # Token/request usage collection
│   ├── aggregators.py       # Cost aggregation logic
│   └── reports.py           # Billing reports & analytics
└── adminui/                  # 🎛️ Admin Interface Extensions
    ├── admin.py             # Custom Django admin
    ├── forms.py             # Admin forms for configuration
    ├── templates/           # Admin UI templates
    └── static/              # Admin UI assets
```

## Migration Strategy

### Phase 1 ➜ Phase 2 Transition:

1. **Extract Core Components** (Week 1-2)
   - Move shared models to `core/`
   - Extract auth logic to `authz/`
   - Create base serializers & permissions

2. **Modularize Current Features** (Week 3-4)
   - Split `gemini/` into `agents/` and `conversations/`
   - Move WebSocket consumers to `conversations/`
   - Extract agent management to `agents/`

3. **Add Advanced Features** (Week 5+)
   - Implement `rules/` engine for routing
   - Add `tasks/` for async job processing
   - Build `registry/` for multi-service coordination
   - Integrate `events/` for audit trails

### Benefits of Modular Structure:

- **🔄 Scalability**: Each app can be scaled independently
- **🧪 Testing**: Isolated testing per domain
- **👥 Team Development**: Clear ownership boundaries
- **📦 Deployment**: Microservice-ready architecture
- **🔧 Maintenance**: Clear separation of concerns
- **🚀 Feature Addition**: Easy to add new capabilities

## Current vs Future Comparison:

| Feature | Current (Phase 1) | Future (Phase 2) |
|---------|-------------------|-------------------|
| Architecture | Monolithic app | Modular microservice-ready |
| User Management | Simple auth | Full RBAC + OAuth |
| Agent Management | Single Gemini agent | Multi-agent orchestration |
| Chat System | Simple sessions | Rooms, multi-user, persistence |
| API | Basic endpoints | Full DRF API with docs |
| Admin | Basic Django admin | Custom admin UI |
| Monitoring | Basic logging | Full telemetry + audit |
| Deployment | Single Django app | Docker + orchestration ready |

## Key Technologies:

- **Framework**: Django 5.2 + Django REST Framework
- **Real-time**: Django Channels + WebSockets
- **Database**: PostgreSQL (production) / SQLite (development)
- **Caching**: Redis (sessions, rate limiting)
- **Task Queue**: Celery + Redis/RabbitMQ
- **API Documentation**: OpenAPI/Swagger
- **Monitoring**: OpenTelemetry + structured logging
- **Authentication**: Django Auth + OAuth2 + API Keys

This architecture provides a clean migration path from the current simplified structure to a full-featured, production-ready multi-agent system while maintaining working functionality throughout the transition.