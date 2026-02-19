# mcp/ - Model Context Protocol 통합

## 개요
MCP (Model Context Protocol) 서버 및 커넥터 통합. 외부 도구 및 서비스 연결.

## 핵심 기능 (계획)
- MCP 서버 호스팅
- MCP 커넥터 관리
- 도구 레지스트리
- 권한 관리

---

## 파일 구조 및 역할

| 파일 | 역할 | 상태 |
|------|------|------|
| `models.py` | MCP 모델 | 비어있음 (개발 예정) |
| `admin.py` | Django Admin | 기본 설정 |
| `views.py` | MCP API | 비어있음 |
| `apps.py` | 앱 설정 | `McpConfig` |

---

## MCP 개요

MCP (Model Context Protocol)는 AI 모델이 외부 도구 및 데이터 소스에 접근할 수 있게 하는 프로토콜.

### 계획된 기능

1. **MCP 서버**
   - 로컬 도구 노출
   - 리소스 제공
   - 프롬프트 템플릿

2. **MCP 클라이언트**
   - 외부 MCP 서버 연결
   - 도구 호출
   - 리소스 가져오기

---

## 계획된 모델

### MCPConnector (계획)
```python
class MCPConnector(BaseModel):
    name = models.CharField(max_length=255)
    server_url = models.URLField()
    auth_type = models.CharField(choices=['none', 'bearer', 'oauth'])
    credentials = models.JSONField(default=dict)
    tools = models.JSONField(default=list)
    is_active = models.BooleanField(default=True)
```

---

## 현재 상태
- 기본 구조만 존재
- MCP 통합 개발 예정
- Agent 시스템과 연동 계획
