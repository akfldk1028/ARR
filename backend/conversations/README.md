# conversations/ - 대화 및 채팅방 관리

## 개요
다중 사용자 채팅방, 대화 세션, 메시지 관리 모델. Agent 할당 및 멀티에이전트 룸 지원.

## 핵심 기능
- 채팅방 (Room) 관리
- 대화 세션 (Conversation) 관리
- 메시지 (Message) 저장
- 에이전트 룸 할당

---

## 파일 구조 및 역할

| 파일 | 역할 | 핵심 클래스 |
|------|------|------------|
| `models.py` | 대화 모델 정의 | `Room`, `RoomParticipant`, `RoomAgent`, `Conversation`, `Message` |
| `admin.py` | Django Admin 설정 | |
| `views.py` | 뷰 (현재 비어있음) | |
| `apps.py` | 앱 설정 | `ConversationsConfig` |

---

## 모델 상세

### Room (채팅방)
```python
class Room(BaseModel):
    ROOM_TYPES = ['private', 'group', 'agent', 'multi_agent']
    
    name = models.CharField(max_length=255)
    room_type = models.CharField(choices=ROOM_TYPES)
    organization = models.ForeignKey(Organization)
    participants = models.ManyToManyField(User, through='RoomParticipant')
    agents = models.ManyToManyField(Agent, through='RoomAgent')
    max_participants = models.IntegerField(default=10)
```
- 다양한 룸 타입 지원
- 사용자 및 에이전트 참여

### RoomParticipant (참여자)
```python
class RoomParticipant(BaseModel):
    ROLES = ['owner', 'admin', 'member', 'observer']
    
    room = models.ForeignKey(Room)
    user = models.ForeignKey(User)
    role = models.CharField(choices=ROLES)
    can_invite = models.BooleanField(default=False)
    can_manage_agents = models.BooleanField(default=False)
```
- 역할 기반 권한
- 권한 설정

### RoomAgent (에이전트 할당)
```python
class RoomAgent(BaseModel):
    room = models.ForeignKey(Room)
    agent = models.ForeignKey(Agent)
    is_active = models.BooleanField(default=True)
    auto_respond = models.BooleanField(default=True)
    trigger_keywords = models.JSONField(default=list)
```
- 에이전트 자동 응답 설정
- 트리거 키워드 지원

### Conversation (대화 세션)
```python
class Conversation(BaseModel):
    room = models.ForeignKey(Room)
    user = models.ForeignKey(User, null=True)
    title = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    last_activity = models.DateTimeField(auto_now=True)
```
- 대화 세션 추적
- 활동 시간 관리

### Message (메시지)
```python
class Message(BaseModel):
    MESSAGE_TYPES = ['text', 'image', 'audio', 'video', 'file', 'system']
    SENDER_TYPES = ['user', 'agent', 'system']
    
    conversation = models.ForeignKey(Conversation)
    content = models.TextField()
    message_type = models.CharField(choices=MESSAGE_TYPES)
    sender_type = models.CharField(choices=SENDER_TYPES)
    user = models.ForeignKey(User, null=True)
    agent = models.ForeignKey(Agent, null=True)
    reply_to = models.ForeignKey('self', null=True)  # Threading
```
- 다양한 메시지 타입
- 스레딩 지원

---

## 관계도
```
Organization
    └─ Room (채팅방)
        ├─ RoomParticipant (참여자)
        │   └─ User
        ├─ RoomAgent (에이전트)
        │   └─ Agent
        └─ Conversation (대화)
            └─ Message (메시지)
                ├─ User (발신자)
                └─ Agent (발신자)
```

## 의존성
- `core.models`: BaseModel, Organization
- `agents.models`: Agent
