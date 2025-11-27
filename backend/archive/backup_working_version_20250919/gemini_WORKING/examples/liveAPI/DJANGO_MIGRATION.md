# 🚀 Django 프로젝트 이전 가이드

Gemini Live API 멀티모달 서버를 Django 프로젝트로 이전하는 가이드입니다.

## 📋 이전 준비사항

### 1. 종속성 설치
```bash
# Django 프로젝트에서
pip install -r requirements-minimal.txt
```

### 2. 파일 구조
```
django_project/
├── gemini_app/
│   ├── consumers.py          # WebSocket consumer
│   ├── views.py             # HTTP views
│   ├── urls.py              # URL routing
│   ├── models.py            # 데이터베이스 모델
│   └── templates/
│       └── gemini/
│           └── chat.html    # UI 템플릿
├── settings.py              # Django 설정
└── routing.py               # WebSocket routing
```

## 🔧 Django 설정

### 1. settings.py
```python
# Django Channels 설정
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'channels',
    'gemini_app',  # 앱 이름
]

# Channels 설정
ASGI_APPLICATION = 'your_project.asgi.application'

CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            "hosts": [('127.0.0.1', 6379)],
        },
    },
}

# 환경변수
import os
from dotenv import load_dotenv
load_dotenv()

GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
```

### 2. asgi.py
```python
import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from gemini_app import routing

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'your_project.settings')

application = ProtocolTypeRouter({
    'http': get_asgi_application(),
    'websocket': AuthMiddlewareStack(
        URLRouter(
            routing.websocket_urlpatterns
        )
    ),
})
```

## 📝 코드 변환

### 1. WebSocket Consumer (consumers.py)
```python
import json
import asyncio
from channels.generic.websocket import AsyncWebsocketConsumer
from django.conf import settings

# 기존 GeminiMultimodalLiveServer 클래스를 여기에 복사
class GeminiMultimodalLiveServer:
    # ... (기존 코드 그대로 복사)
    pass

class GeminiLiveConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.accept()
        self.gemini_server = GeminiMultimodalLiveServer(
            api_key=settings.GOOGLE_API_KEY,
            model="gemini-2.0-flash-live-001"
        )
        await self.gemini_server.initialize()

    async def disconnect(self, close_code):
        if hasattr(self, 'gemini_server'):
            await self.gemini_server.cleanup()

    async def receive(self, text_data):
        data = json.loads(text_data)

        if data.get('type') == 'text':
            result = await self.gemini_server.process_text_stream(
                data.get('message', '')
            )
        elif data.get('type') == 'image':
            result = await self.gemini_server.process_image_stream(
                data.get('image', ''),
                data.get('prompt', 'What do you see?')
            )
        elif data.get('type') == 'audio':
            result = await self.gemini_server.process_audio_stream(
                data.get('audio', '')
            )
        else:
            result = {'text': 'Unknown message type', 'success': False}

        await self.send(text_data=json.dumps({
            'type': 'response',
            'message': result.get('text', ''),
            'response_time': result.get('response_time', 0),
            'analysis_type': result.get('type', ''),
            'success': result.get('success', False)
        }))
```

### 2. URL 라우팅 (routing.py)
```python
from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/gemini/$', consumers.GeminiLiveConsumer.as_asgi()),
]
```

### 3. HTTP Views (views.py)
```python
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json

def chat_view(request):
    """메인 채팅 페이지"""
    return render(request, 'gemini/chat.html')

@csrf_exempt
async def multimodal_test(request):
    """HTTP 기반 멀티모달 테스트 (대안)"""
    if request.method == 'POST':
        # 기존 FastAPI 엔드포인트 로직을 Django view로 변환
        pass
```

### 4. URL 설정 (urls.py)
```python
from django.urls import path
from . import views

urlpatterns = [
    path('', views.chat_view, name='chat'),
    path('api/multimodal/', views.multimodal_test, name='multimodal_test'),
]
```

## 🎨 템플릿 변환

### 1. chat.html
```html
<!-- 기존 HTML 코드를 Django 템플릿으로 변환 -->
{% load static %}
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <title>Gemini Live Chat</title>
    <!-- CSS는 static 파일로 분리 -->
    <link rel="stylesheet" href="{% static 'gemini/chat.css' %}">
</head>
<body>
    <!-- 기존 HTML 구조 유지 -->

    <script>
        // WebSocket URL을 Django에 맞게 수정
        const ws = new WebSocket('ws://{{ request.get_host }}/ws/gemini/');

        // 기존 JavaScript 코드 유지
    </script>
</body>
</html>
```

## 🔒 보안 고려사항

### 1. CSRF 보호
```python
from django.middleware.csrf import get_token
from django.views.decorators.csrf import csrf_exempt

# WebSocket은 CSRF 면제
# HTTP 엔드포인트는 CSRF 토큰 필요
```

### 2. 인증 및 권한
```python
from channels.auth import AuthMiddlewareStack
from django.contrib.auth.decorators import login_required

# WebSocket 인증
class GeminiLiveConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        if self.scope["user"].is_authenticated:
            await self.accept()
        else:
            await self.close()
```

## 📊 데이터베이스 모델 (선택사항)

### models.py
```python
from django.db import models
from django.contrib.auth.models import User

class ChatSession(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    session_id = models.CharField(max_length=100, unique=True)

class ChatMessage(models.Model):
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE)
    message_type = models.CharField(max_length=20)  # text, image, audio
    content = models.TextField()
    response = models.TextField()
    response_time = models.FloatField()
    created_at = models.DateTimeField(auto_now_add=True)
```

## 🚀 배포

### 1. 개발 서버
```bash
# Redis 서버 시작 (Windows)
redis-server

# Django 개발 서버
python manage.py runserver 8899
```

### 2. 프로덕션 (Daphne)
```bash
# ASGI 서버로 실행
daphne -p 8899 your_project.asgi:application
```

## 📚 추가 고려사항

### 1. 정적 파일 관리
- CSS/JS를 Django static files로 분리
- `python manage.py collectstatic`

### 2. 환경 설정
- 개발/프로덕션 설정 분리
- 환경변수로 민감한 정보 관리

### 3. 로깅
```python
import logging
logger = logging.getLogger(__name__)

# 로그 설정을 Django settings에 추가
```

### 4. 에러 처리
- Django의 에러 핸들링 활용
- 적절한 HTTP 상태 코드 반환

---

**🎉 이제 Django 프로젝트에서 Gemini Live API 멀티모달 채팅 서비스를 구축할 수 있습니다!**