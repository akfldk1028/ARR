# backend/ - Django 프로젝트 설정

## 개요
Django 프로젝트 메인 설정. ASGI, URL 라우팅, 미들웨어, 데이터베이스 설정.

## 핵심 기능
- Django 프로젝트 설정
- ASGI 서버 설정 (WebSocket 지원)
- URL 라우팅
- 미들웨어 구성

---

## 파일 구조 및 역할

| 파일 | 역할 | 설명 |
|------|------|------|
| `settings.py` | 메인 설정 | DB, 앱, 미들웨어, 채널 레이어 |
| `urls.py` | URL 라우팅 | 전체 URL 패턴 |
| `asgi.py` | ASGI 설정 | WebSocket 라우팅 |
| `wsgi.py` | WSGI 설정 | HTTP 전용 (사용 안 함) |

---

## 주요 설정

### INSTALLED_APPS
```python
INSTALLED_APPS = [
    # Django 기본
    'django.contrib.admin',
    'django.contrib.auth',
    ...
    
    # 서드파티
    'channels',
    'rest_framework',
    'corsheaders',
    
    # 프로젝트 앱
    'core',
    'agents',
    'gemini',
    'chat',
    'conversations',
    'graph_db',
    'law',
    'parser',
    'live_a2a_bridge',
    'mcp',
    'tasks',
    'authz',
]
```

### CHANNEL_LAYERS
```python
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels.layers.InMemoryChannelLayer'
        # 프로덕션: Redis 사용
    }
}
```

### DATABASES
```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}
# 프로덕션: PostgreSQL 권장
```

---

## ASGI 라우팅

```python
# asgi.py
application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(
        URLRouter([
            path("ws/gemini/", GeminiConsumer.as_asgi()),
            path("ws/chat/", ChatConsumer.as_asgi()),
        ])
    ),
})
```

---

## 서버 실행

```bash
# 개발 서버 (WebSocket 지원)
daphne -b 0.0.0.0 -p 8000 backend.asgi:application

# HTTP 전용 (WebSocket 미지원)
python manage.py runserver
```

---

## 환경 변수

```env
DEBUG=True
SECRET_KEY=your-secret-key
ALLOWED_HOSTS=localhost,127.0.0.1

# Neo4j
NEO4J_URI=neo4j://127.0.0.1:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=11111111

# API Keys
OPENAI_API_KEY=sk-xxx
GEMINI_API_KEY=xxx
```
