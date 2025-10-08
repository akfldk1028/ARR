# Deprecated Files

이 폴더에는 더 이상 사용하지 않는 파일들이 보관되어 있습니다.

## 이동된 파일들

### Root Level
- `langgraph_agent.py` - 구버전 LangGraph 에이전트 (test_langgraph.py에서만 사용)
- `services.py` - 구버전 서비스 초기화 (test_langgraph.py에서만 사용)

### voice/
- 전체 폴더 - 구버전 음성 서비스 (사용 안 됨)

### worker_agents/
- `conversation_coordinator.py` - 구버전 대화 코디네이터 (test_agent_conversations.py에서만 사용)
- `conversation_types.py` - 구버전 대화 타입 (test_agent_conversations.py에서만 사용)
- `websocket_integration.py` - 구버전 WebSocket 통합 (사용 안 됨)
- `a2a_streaming.py` - 구버전 A2A 스트리밍 (사용 안 됨)

## 현재 사용 중인 시스템

### 활성 Worker 시스템:
- `worker_agents/worker_manager.py` - Worker 관리자
- `worker_agents/worker_factory.py` - Worker 생성 팩토리
- `worker_agents/base/base_worker.py` - 기본 Worker 클래스
- `worker_agents/implementations/general_worker.py` - Host Agent
- `worker_agents/implementations/flight_specialist_worker.py` - Flight Specialist
- `worker_agents/agent_discovery.py` - 에이전트 발견 서비스

### 활성 데이터베이스:
- `database/neo4j/service.py` - Neo4j 서비스

### 활성 A2A 프로토콜:
- `a2a_client.py` - A2A 클라이언트
- `views.py` - Agent card endpoints

이동 날짜: 2025-10-02
