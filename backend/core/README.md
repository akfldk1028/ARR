# core/ - 공유 기본 모델

## 개요
전체 프로젝트에서 공유하는 기본 모델 및 유틸리티. Multi-tenancy 지원을 위한 Organization 모델 포함.

## 핵심 기능
- BaseModel (UUID, 타임스탬프)
- Organization (멀티테넌시)
- Tag (태깅 시스템)

---

## 파일 구조 및 역할

| 파일 | 역할 | 핵심 클래스 |
|------|------|------------|
| `models.py` | 기본 모델 정의 | `BaseModel`, `Organization`, `OrganizationMember`, `Tag` |
| `admin.py` | Django Admin 설정 | |
| `views.py` | 뷰 (현재 비어있음) | |
| `apps.py` | 앱 설정 | `CoreConfig` |

---

## 모델 상세

### BaseModel (추상)
```python
class BaseModel(models.Model):
    id = models.UUIDField(primary_key=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```
- 모든 모델의 베이스
- UUID 기본 키
- 생성/수정 타임스탬프

### Organization
```python
class Organization(BaseModel):
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    settings = models.JSONField(default=dict)
```
- 멀티테넌시 지원
- 조직별 설정 관리

### OrganizationMember
```python
class OrganizationMember(BaseModel):
    organization = models.ForeignKey(Organization)
    user = models.ForeignKey(User)
    role = models.CharField(choices=ROLES)  # owner, admin, member, viewer
    is_active = models.BooleanField(default=True)
```
- 조직 멤버십 관리
- 역할 기반 권한

### Tag
```python
class Tag(BaseModel):
    name = models.CharField(max_length=100)
    color = models.CharField(max_length=7)  # Hex color
    organization = models.ForeignKey(Organization, null=True)
```
- 범용 태깅 시스템
- 조직별 태그 관리

---

## 사용 예시
```python
from core.models import BaseModel, Organization, Tag

class MyModel(BaseModel):
    name = models.CharField(max_length=100)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    tags = models.ManyToManyField(Tag)
```

## 의존성
- `django.contrib.auth.models.User`: 사용자 모델
