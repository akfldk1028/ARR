# authz/ - 인증 및 권한 관리

## 개요
사용자 인증(Authentication) 및 권한 부여(Authorization) 시스템. RBAC, OAuth, API 키 관리 예정.

## 핵심 기능 (계획)
- RBAC (Role-Based Access Control)
- OAuth2 통합
- API 키 관리
- 권한 미들웨어

---

## 파일 구조 및 역할

| 파일 | 역할 | 상태 |
|------|------|------|
| `models.py` | 인증 모델 | 비어있음 (개발 예정) |
| `admin.py` | Django Admin | 기본 설정 |
| `views.py` | 인증 뷰 | 비어있음 |
| `apps.py` | 앱 설정 | `AuthzConfig` |

---

## 계획된 모델

### User (Django 기본 사용)
- `django.contrib.auth.models.User`

### Role (계획)
```python
class Role(BaseModel):
    name = models.CharField(max_length=100)
    permissions = models.JSONField(default=list)
    organization = models.ForeignKey(Organization)
```

### APIKey (계획)
```python
class APIKey(BaseModel):
    key = models.CharField(max_length=64)
    user = models.ForeignKey(User)
    scopes = models.JSONField(default=list)
    expires_at = models.DateTimeField(null=True)
```

---

## 의존성 (계획)
- `django.contrib.auth`: 기본 인증
- `oauth2_provider`: OAuth2
- `rest_framework.authtoken`: API 토큰

## 현재 상태
- 기본 구조만 존재
- 실제 인증 로직은 Django 기본 사용
- 추후 확장 예정
