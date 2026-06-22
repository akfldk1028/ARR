# _inactive

Django apps with code but NOT registered in INSTALLED_APPS.
These were planned features that were never activated.

## To activate an app:
1. Move folder from `_inactive/` to `backend/`
2. Add app name to INSTALLED_APPS in `backend/settings.py`
3. Run `python manage.py makemigrations <app> && python manage.py migrate`

## Apps

| App | Lines | Description | Dependencies |
|-----|-------|-------------|-------------|
| authz | ~180 | RBAC: Role, Permission, UserRole, APIKey | core.Organization |
| billing | ~600 | UsageMetric, BillingPeriod, CostCalculation | core, conversations, tasks |
| conversations | ~180 | Room, RoomParticipant, Conversation, Message | core, agents |
| events | ~700 | EventLog (45+ types), AuditTrail, EventStream | core, agents, conversations, tasks |
| live_a2a_bridge | ~200 | Gemini TTS bridge, Live API optimized bridge | gemini |
| mcp | ~800 | MCPConnector, MCPService, MCPWebhook | core, agents |
| registry | ~500 | ServiceRegistration, HealthCheck, ServiceEndpoint | core |
| tasks | ~250 | Task, Job, JobTask, ExecutionRequest | core, agents, conversations |

## Cross-dependencies
- `billing` requires `tasks` and `conversations`
- `events` requires `conversations` and `tasks`
- Activate in order: core -> agents -> conversations -> tasks -> rest
