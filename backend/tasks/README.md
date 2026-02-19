# tasks/ - 작업 및 잡 관리

## 개요
비동기 작업(Task), 잡(Job) 관리 시스템. Celery/RQ 통합 예정.

## 핵심 기능 (계획)
- 작업 큐 관리
- 재시도 정책
- 작업 모니터링
- 스케줄링

---

## 파일 구조 및 역할

| 파일 | 역할 | 상태 |
|------|------|------|
| `models.py` | 작업 모델 | 비어있음 (개발 예정) |
| `admin.py` | Django Admin | 기본 설정 |
| `views.py` | 작업 API | 비어있음 |
| `apps.py` | 앱 설정 | `TasksConfig` |

---

## 계획된 모델

### Task (계획)
```python
class Task(BaseModel):
    STATUS_CHOICES = ['pending', 'running', 'completed', 'failed', 'cancelled']
    
    name = models.CharField(max_length=255)
    status = models.CharField(choices=STATUS_CHOICES)
    task_type = models.CharField(max_length=100)
    parameters = models.JSONField(default=dict)
    result = models.JSONField(null=True)
    error = models.TextField(null=True)
    started_at = models.DateTimeField(null=True)
    completed_at = models.DateTimeField(null=True)
```

### Job (계획)
```python
class Job(BaseModel):
    tasks = models.ManyToManyField(Task)
    status = models.CharField(choices=STATUS_CHOICES)
    total_tasks = models.IntegerField()
    completed_tasks = models.IntegerField(default=0)
```

---

## 의존성 (계획)
- `celery`: 비동기 작업 큐
- `redis`/`rabbitmq`: 메시지 브로커

## 현재 상태
- 기본 구조만 존재
- 추후 Celery 통합 예정
