"""
Django settings.py에 추가할 내용

이 파일을 참고하여 Django 프로젝트의 settings.py에 추가하세요.
"""

# 1. INSTALLED_APPS에 추가
INSTALLED_APPS = [
    ...
    'law_rag',  # 생성한 Django app
]

# 2. Neo4j 연결 설정
NEO4J_CONFIG = {
    'uri': 'bolt://localhost:7687',
    'user': 'neo4j',
    'password': 'your_password_here',  # ⚠️ 변경 필수!
    'database': 'neo4j'
}

# 3. 임베딩 모델 설정
EMBEDDING_MODEL = 'jhgan/ko-sbert-sts'
EMBEDDING_DIM = 768

# 4. 데이터 경로 설정
BASE_DATA_DIR = BASE_DIR / 'data'
LAW_DATA_DIR = BASE_DATA_DIR / 'laws'
RAG_DATA_DIR = BASE_DATA_DIR / 'rag'
PARSED_DATA_DIR = BASE_DATA_DIR / 'parsed'

# 5. 로깅 설정 (선택)
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'law_rag.log',
            'maxBytes': 10485760,  # 10MB
            'backupCount': 5,
        },
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': 'INFO',
    },
}
