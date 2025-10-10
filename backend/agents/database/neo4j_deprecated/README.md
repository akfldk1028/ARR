# Deprecated Neo4j Code (구버전)

**⚠️ This directory contains deprecated code. DO NOT USE!**

## Migration Status
모든 Neo4j 관련 코드가 `graph_db` Django 앱으로 마이그레이션되었습니다.

### Migration Date
- 2025-10-09

### Old Location
- `agents/database/neo4j/`

### New Location
- `graph_db/` (Django app)

## File Mapping

| Old File | New Location | Status |
|----------|-------------|--------|
| `service.py` | `graph_db/services/neo4j_service.py` | ✅ Migrated |
| `conversation_tracker.py` | `graph_db/tracking/conversation.py` | ✅ Migrated + Turn sequence fix |
| `task_manager.py` | `graph_db/tracking/task.py` | ✅ Migrated |
| `provenance_tracker.py` | `graph_db/tracking/provenance.py` | ✅ Migrated |
| `indexes.py` | `graph_db/schema/indexes.py` | ✅ Migrated |
| `queries.py` | `graph_db/schema/queries.py` | ✅ Migrated |
| `stats.py` | Not migrated yet | ⚠️ Future |
| `governance_manager.py` | Not migrated yet | ⚠️ Future |

## Import Changes

### Before (Old - Deprecated)
```python
from agents.database.neo4j import get_neo4j_service
from agents.database.neo4j.conversation_tracker import ConversationTracker
```

### After (New - Current)
```python
from graph_db.services import get_neo4j_service
from graph_db.tracking import ConversationTracker
```

## Why Deprecated?

1. **중앙집중화**: 모든 Neo4j 코드를 하나의 Django 앱으로 통합
2. **유지보수성 향상**: 명확한 구조 (services, tracking, schema)
3. **버그 수정**: Turn sequence 중복 문제 해결
4. **테스트 용이성**: 독립적인 Django 앱으로 테스트 가능

## Deletion Plan

이 폴더는 다음 조건이 충족되면 삭제될 예정입니다:
1. `stats.py` 기능이 `graph_db`로 마이그레이션
2. `governance_manager.py` 기능이 `graph_db`로 마이그레이션
3. 모든 테스트 스크립트가 새 경로 사용 확인
4. 최소 1주일 이상 프로덕션 환경에서 문제 없이 작동 확인

## Contact
문제 발생 시: 원본 코드가 여기 보관되어 있으므로 필요시 참고 가능
