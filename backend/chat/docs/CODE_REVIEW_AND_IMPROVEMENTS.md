# Code Review & Improvement Plan

## 현재 문제점

### 1. Agent Card 관리 문제 ❌

**문제:**
```
agents/worker_agents/cards/
├── general_worker_card.json     # 중복 (Legacy)
├── hostagent_card.json          # 실제 사용
├── flight_specialist_card.json
└── hotel_specialist_card.json
```

- JSON 파일들이 있지만 **실제로는 Django DB에서 동적 생성** (`agents/views.py`)
- JSON 파일은 무시됨 → 혼란 야기
- Agent 추가/제거할 때 Django DB + JSON 두 곳 다 수정해야 함

**개선:**
1. **Option A (권장)**: Django DB만 사용, JSON 파일 완전 제거
2. **Option B**: JSON 파일을 Single Source of Truth로 만들고 Django DB는 캐시로만 사용

---

### 2. Semantic Routing 카테고리 하드코딩 ❌

**현재 코드** (`agents/worker_agents/agent_discovery.py:159-173`):
```python
self._categories = {
    'greetings': ["안녕하세요", "hello", ...],
    'flight_booking': ["비행기 예약", ...],
    'hotel_booking': ["호텔 예약", ...],
}
```

**문제:**
- 새 specialist agent 추가할 때마다 코드 수정 필요
- Agent와 카테고리가 분리되어 있음 (유지보수 어려움)

**개선:**
Django Agent 모델에 `routing_keywords` 필드 추가
```python
class Agent(models.Model):
    slug = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=200)
    routing_keywords = models.JSONField(default=list)  # NEW!
    # 예: ["비행기 예약", "항공편", "flight booking"]
```

---

### 3. Agent Discovery 성능 문제 ❌

**현재:**
- 매 요청마다 3개 agent card를 HTTP로 읽음 (~1.5초)
- 불필요한 네트워크 오버헤드

**개선:**
- Agent card 캐싱 (5분)
- 또는 Django DB에서 직접 읽기 (HTTP 제거)

---

### 4. Worker Factory 하드코딩 ❌

**현재 코드** (`agents/worker_agents/worker_factory.py:18-23`):
```python
WORKER_TYPES: Dict[str, Type[BaseWorkerAgent]] = {
    'hostagent': GeneralWorkerAgent,
    'general-worker': GeneralWorkerAgent,  # Legacy
    'flight-specialist': FlightSpecialistWorkerAgent,
}
```

**문제:**
- 새 specialist 추가할 때마다 코드 수정
- Legacy alias 관리 복잡

**개선:**
Django Agent 모델에 `worker_class` 필드 추가
```python
class Agent(models.Model):
    slug = models.CharField(max_length=100, unique=True)
    worker_class = models.CharField(max_length=200)
    # 예: "agents.worker_agents.implementations.flight_specialist_worker.FlightSpecialistWorkerAgent"
```

동적 import로 worker 생성:
```python
def create_worker(cls, agent_slug, agent_config):
    worker_class_path = agent_config['worker_class']
    module_path, class_name = worker_class_path.rsplit('.', 1)
    module = importlib.import_module(module_path)
    worker_class = getattr(module, class_name)
    return worker_class(agent_slug, agent_config)
```

---

### 5. Coordination LLM 제거 후 속도 개선 ✅

**Before:**
```
총 ~12초:
  - Semantic routing: 8.5초
  - Specialist: 2초
  - Coordination LLM: 1.5초  ← 제거됨
```

**After:**
```
총 ~9초:
  - Semantic routing: 8.5초
  - Specialist: 2초
```

**추가 개선 가능:**
- Agent card 캐싱으로 1.5초 절약 → **~7초**

---

## 개선 계획

### Phase 1: Agent Card 정리 (즉시)

**목표**: Django DB를 Single Source of Truth로 만들기

**작업:**
1. JSON 파일 제거 또는 deprecated 폴더로 이동
2. `agents/views.py`가 Django DB에서 agent card 생성하는 것 확인 (이미 구현됨 ✅)
3. Agent 추가/제거는 Django Admin 또는 Management Command로만

**파일 수정:**
- `agents/worker_agents/cards/*.json` → 삭제 or deprecated/로 이동

---

### Phase 2: Semantic Routing 동적화 (중요도: 높음)

**목표**: Agent 추가할 때 코드 수정 없이 routing keywords만 설정

**작업:**

#### 2.1 Django 모델 확장
```python
# agents/models.py
class Agent(models.Model):
    # ... 기존 필드 ...
    routing_keywords = models.JSONField(
        default=list,
        help_text="Semantic routing에 사용될 키워드 리스트 (예: ['비행기 예약', 'flight booking'])"
    )
    routing_category = models.CharField(
        max_length=100,
        blank=True,
        help_text="Semantic routing 카테고리 (예: 'flight_booking')"
    )
```

#### 2.2 Migration 생성
```bash
python manage.py makemigrations agents
python manage.py migrate agents
```

#### 2.3 Agent Discovery 동적화
```python
# agents/worker_agents/agent_discovery.py
async def _load_routing_categories(self):
    """Django DB에서 routing categories 동적 로드"""
    from agents.models import Agent

    categories = {}
    agents = await sync_to_async(list)(
        Agent.objects.filter(status='active', routing_category__isnull=False)
    )

    for agent in agents:
        if agent.routing_category and agent.routing_keywords:
            categories[agent.routing_category] = agent.routing_keywords

    return categories

async def should_delegate_request(self, user_request, current_agent_slug):
    # Dynamic category loading
    if not hasattr(self, '_categories'):
        self._categories = await self._load_routing_categories()

    # ... 나머지 로직 동일
```

#### 2.4 Agent 데이터 업데이트
```python
# Management command: update_agent_routing.py
from agents.models import Agent

Agent.objects.filter(slug='flight-specialist').update(
    routing_category='flight_booking',
    routing_keywords=['비행기 예약', '항공편', 'flight booking', '비행기표', '항공권']
)

Agent.objects.filter(slug='hotel-specialist').update(
    routing_category='hotel_booking',
    routing_keywords=['호텔 예약', '숙박', 'hotel reservation', '숙소']
)
```

---

### Phase 3: Worker Factory 동적화 (중요도: 중간)

**목표**: 새 specialist 추가 시 코드 수정 없이 DB 설정만으로 가능

**작업:**

#### 3.1 Django 모델 확장
```python
# agents/models.py
class Agent(models.Model):
    # ... 기존 필드 ...
    worker_class_path = models.CharField(
        max_length=500,
        default='agents.worker_agents.implementations.general_worker.GeneralWorkerAgent',
        help_text="Worker class 전체 경로 (예: 'agents.worker_agents.implementations.flight_specialist_worker.FlightSpecialistWorkerAgent')"
    )
```

#### 3.2 Worker Factory 리팩토링
```python
# agents/worker_agents/worker_factory.py
import importlib

class WorkerAgentFactory:
    @classmethod
    def create_worker(cls, agent_slug: str, agent_config: Dict[str, Any]) -> Optional[BaseWorkerAgent]:
        try:
            # Dynamic import
            worker_class_path = agent_config.get('worker_class_path')
            if not worker_class_path:
                logger.error(f"No worker_class_path for agent {agent_slug}")
                return None

            module_path, class_name = worker_class_path.rsplit('.', 1)
            module = importlib.import_module(module_path)
            worker_class = getattr(module, class_name)

            # Create worker instance
            worker = worker_class(agent_slug, agent_config)
            logger.info(f"Created worker agent: {agent_slug} ({worker_class.__name__})")

            return worker

        except Exception as e:
            logger.error(f"Error creating worker agent {agent_slug}: {e}")
            return None
```

---

### Phase 4: Agent Card 캐싱 (성능 개선)

**목표**: Agent discovery 속도를 1.5초 → 0.01초로 개선

**작업:**

#### 4.1 Agent Discovery 캐싱
```python
# agents/worker_agents/agent_discovery.py
import time

class AgentDiscoveryService:
    def __init__(self, llm: ChatOpenAI):
        self.llm = llm
        self._agent_cards_cache: Dict[str, Dict] = {}
        self._cache_timeout = 300  # 5분
        self._cache_timestamp = 0

    async def discover_available_agents(self) -> Dict[str, Dict]:
        # Check cache validity
        current_time = time.time()
        if current_time - self._cache_timestamp < self._cache_timeout:
            logger.info(f"Using cached agent cards ({len(self._agent_cards_cache)} agents)")
            return self._agent_cards_cache

        # Cache expired, reload
        logger.info("Agent card cache expired, reloading...")

        # Django DB에서 직접 읽기 (HTTP 제거!)
        from agents.models import Agent
        from asgiref.sync import sync_to_async

        agents = await sync_to_async(list)(
            Agent.objects.filter(status='active')
        )

        discovered_agents = {}
        for agent in agents:
            discovered_agents[agent.slug] = {
                'name': agent.name,
                'description': agent.description,
                'capabilities': agent.capabilities,
                'routing_category': agent.routing_category,
                'routing_keywords': agent.routing_keywords,
            }

        self._agent_cards_cache = discovered_agents
        self._cache_timestamp = current_time

        logger.info(f"Discovered {len(discovered_agents)} agents from DB")
        return discovered_agents
```

**성능 개선:**
- Before: HTTP 3회 (~1.5초)
- After: Django DB 조회 1회 + 캐시 (~0.01초)
- **총 요청 시간: 9초 → 7.5초**

---

### Phase 5: Management Commands (유지보수성)

**목표**: Agent 관리를 코드 수정 없이 CLI로 가능하게

**작업:**

#### 5.1 Create Agent Command
```python
# agents/management/commands/create_agent.py
from django.core.management.base import BaseCommand
from agents.models import Agent

class Command(BaseCommand):
    help = 'Create a new specialist agent'

    def add_arguments(self, parser):
        parser.add_argument('slug', type=str)
        parser.add_argument('--name', type=str, required=True)
        parser.add_argument('--description', type=str, required=True)
        parser.add_argument('--worker-class', type=str, required=True)
        parser.add_argument('--category', type=str, required=True)
        parser.add_argument('--keywords', type=str, nargs='+', required=True)

    def handle(self, *args, **options):
        agent = Agent.objects.create(
            slug=options['slug'],
            name=options['name'],
            description=options['description'],
            worker_class_path=options['worker_class'],
            routing_category=options['category'],
            routing_keywords=options['keywords'],
            agent_type='worker',
            status='active'
        )
        self.stdout.write(self.style.SUCCESS(f'Created agent: {agent.slug}'))
```

**사용 예시:**
```bash
python manage.py create_agent hotel-specialist \
    --name "Hotel Specialist" \
    --description "Hotel booking expert" \
    --worker-class "agents.worker_agents.implementations.hotel_specialist_worker.HotelSpecialistWorkerAgent" \
    --category "hotel_booking" \
    --keywords "호텔 예약" "숙박" "hotel reservation"
```

#### 5.2 List Agents Command
```python
# agents/management/commands/list_agents.py
from django.core.management.base import BaseCommand
from agents.models import Agent

class Command(BaseCommand):
    help = 'List all agents'

    def handle(self, *args, **options):
        agents = Agent.objects.filter(status='active')
        for agent in agents:
            self.stdout.write(f"{agent.slug}: {agent.name} ({agent.routing_category})")
            self.stdout.write(f"  Keywords: {', '.join(agent.routing_keywords)}")
```

#### 5.3 Delete Agent Command
```python
# agents/management/commands/delete_agent.py
from django.core.management.base import BaseCommand
from agents.models import Agent

class Command(BaseCommand):
    help = 'Delete an agent'

    def add_arguments(self, parser):
        parser.add_argument('slug', type=str)

    def handle(self, *args, **options):
        agent = Agent.objects.get(slug=options['slug'])
        agent.status = 'inactive'  # Soft delete
        agent.save()
        self.stdout.write(self.style.SUCCESS(f'Deactivated agent: {agent.slug}'))
```

---

## 최종 개선 결과

### Before (현재)
```
새 Agent 추가 절차:
1. Worker class 작성 (flight_specialist_worker.py)
2. worker_factory.py WORKER_TYPES 수정  ← 코드 수정!
3. agent_discovery.py _categories 수정   ← 코드 수정!
4. Django DB에 Agent 생성
5. JSON card 파일 작성 (실제로는 무시됨)
6. 서버 재시작

성능:
- 첫 요청: ~9초 (모델 로딩 포함)
- 이후 요청: ~7초 (agent discovery 1.5초 포함)
```

### After (개선 후)
```
새 Agent 추가 절차:
1. Worker class 작성 (hotel_specialist_worker.py)
2. Management command 실행:
   python manage.py create_agent hotel-specialist \
       --name "Hotel Specialist" \
       --worker-class "agents.worker_agents.implementations.hotel_specialist_worker.HotelSpecialistWorkerAgent" \
       --category "hotel_booking" \
       --keywords "호텔 예약" "숙박"
3. 끝! (서버 재시작 불필요)

성능:
- 첫 요청: ~7초 (모델 로딩 포함)
- 이후 요청: ~5.5초 (agent discovery 캐시됨, 0.01초)
```

---

## 구현 우선순위

### 🔥 High Priority (즉시)
1. **Phase 1**: Agent Card JSON 파일 제거 - 혼란 제거
2. **Phase 4**: Agent Card 캐싱 - 성능 2초 개선

### 🟡 Medium Priority (1주일 내)
3. **Phase 2**: Semantic Routing 동적화 - 유지보수성 대폭 개선
4. **Phase 5**: Management Commands - Agent 관리 편의성

### 🟢 Low Priority (나중에)
5. **Phase 3**: Worker Factory 동적화 - 완전 자동화

---

## 코드 변경 체크리스트

### Phase 1 실행 시
- [ ] `agents/worker_agents/cards/*.json` 삭제
- [ ] `agents/views.py` 확인 (Django DB 사용 확인)
- [ ] 문서 업데이트 (JSON 언급 제거)

### Phase 2 실행 시
- [ ] `agents/models.py` - `routing_keywords`, `routing_category` 필드 추가
- [ ] Migration 생성 및 실행
- [ ] `agents/worker_agents/agent_discovery.py` - 동적 카테고리 로딩
- [ ] 기존 Agent 데이터 업데이트 (management command)
- [ ] 테스트: "비행기 예약" → flight-specialist 선택 확인

### Phase 4 실행 시
- [ ] `agents/worker_agents/agent_discovery.py` - 캐싱 로직 추가
- [ ] Django DB 직접 조회로 변경 (HTTP 제거)
- [ ] 로그로 캐시 hit/miss 확인
- [ ] 성능 측정: before/after 비교

### Phase 5 실행 시
- [ ] `agents/management/commands/create_agent.py` 작성
- [ ] `agents/management/commands/list_agents.py` 작성
- [ ] `agents/management/commands/delete_agent.py` 작성
- [ ] README에 사용법 추가

---

## 테스트 계획

### Agent 추가 테스트 (Phase 2 완료 후)
```python
# 1. Hotel Specialist Agent 생성
python manage.py create_agent hotel-specialist \
    --name "Hotel Specialist" \
    --description "Hotel booking expert" \
    --worker-class "agents.worker_agents.implementations.hotel_specialist_worker.HotelSpecialistWorkerAgent" \
    --category "hotel_booking" \
    --keywords "호텔 예약" "숙박" "hotel reservation"

# 2. 서버 재시작 없이 테스트
브라우저: "호텔 예약해줘"
기대 결과: 🏨 Hotel Specialist 응답

# 3. Agent 리스트 확인
python manage.py list_agents
기대 결과:
  hostagent: Host Agent (None)
  flight-specialist: Flight Specialist (flight_booking)
  hotel-specialist: Hotel Specialist (hotel_booking)

# 4. Agent 제거
python manage.py delete_agent hotel-specialist

# 5. 다시 테스트
브라우저: "호텔 예약해줘"
기대 결과: 🤖 Host Agent 응답 (specialist 없음)
```

---

## 마이그레이션 가이드

### 기존 시스템 → 개선 시스템

**Step 1**: Phase 1 (JSON 제거)
```bash
# Backup
mv agents/worker_agents/cards agents/worker_agents/cards_deprecated

# Test
python -X utf8 -m daphne -p 8004 backend.asgi:application
# "비행기 예약" 테스트 → 정상 작동 확인
```

**Step 2**: Phase 2 (Semantic Routing 동적화)
```bash
# Add model fields
python manage.py makemigrations agents
python manage.py migrate agents

# Update existing agents
python manage.py shell
>>> from agents.models import Agent
>>> Agent.objects.filter(slug='flight-specialist').update(
...     routing_category='flight_booking',
...     routing_keywords=['비행기 예약', '항공편', 'flight booking']
... )

# Update agent_discovery.py code
# Test
```

**Step 3**: Phase 4 (캐싱)
```bash
# Update agent_discovery.py code
# Restart server
python -X utf8 -m daphne -p 8004 backend.asgi:application

# Test performance
# 첫 요청: ~7초
# 두 번째 요청: ~5.5초 (캐시됨)
```

---

## 결론

### 현재 문제점
1. ❌ Agent Card JSON 파일 무시됨 (혼란)
2. ❌ Semantic routing 하드코딩 (유지보수 어려움)
3. ❌ Worker factory 하드코딩
4. ❌ Agent discovery 성능 (1.5초)

### 개선 후
1. ✅ Django DB가 Single Source of Truth
2. ✅ Agent 추가/제거가 Management command로 가능
3. ✅ 코드 수정 없이 agent 관리 가능
4. ✅ Agent discovery 성능 1.5초 → 0.01초
5. ✅ 전체 응답 시간 9초 → 5.5초

### 개발자 경험 개선
**Before:**
```
새 agent 추가 = 5개 파일 수정 + 서버 재시작
```

**After:**
```
새 agent 추가 = 1개 파일 (worker class) + 1줄 command
python manage.py create_agent ... (서버 재시작 불필요!)
```
