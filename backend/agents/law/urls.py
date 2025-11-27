"""
Law MAS API URLs

완전 자동화 엔드포인트:
- POST /agents/law/upload-pdf/     → PDF 업로드 및 자동 처리
- GET  /agents/law/domains/         → 도메인 목록 조회 (구버전)

REST API 엔드포인트 (AgentManager + DomainAgent):
- POST /agents/law/api/search                     → 자동 라우팅 검색
- POST /agents/law/api/search/stream              → SSE 스트리밍 검색 (실시간 진행상황)
- POST /agents/law/api/domain/{id}/search         → 도메인별 검색
- GET  /agents/law/api/domains                    → 도메인 목록 (신버전)
- GET  /agents/law/api/domain/{id}                → 도메인 상세
- GET  /agents/law/api/health                     → 헬스체크
"""

from django.urls import path
from . import pdf_upload_api
from .api import (
    LawSearchAPIView,
    DomainSearchAPIView,
    DomainsListAPIView,
    DomainDetailAPIView,
    HealthCheckAPIView,
    LawSearchStreamAPIView,
)

app_name = 'law'

urlpatterns = [
    # PDF 업로드 (완전 자동)
    path('upload-pdf/', pdf_upload_api.upload_pdf, name='upload_pdf'),

    # 도메인 목록 조회 (구버전 - 하위 호환성)
    path('domains/', pdf_upload_api.list_domains, name='list_domains'),

    # ===== REST API (신버전) =====
    # 검색
    path('api/search', LawSearchAPIView.as_view(), name='api_search'),
    path('api/search/stream', LawSearchStreamAPIView.as_view(), name='api_search_stream'),  # SSE 스트리밍
    path('api/domain/<str:domain_id>/search', DomainSearchAPIView.as_view(), name='api_domain_search'),

    # 도메인 관리
    path('api/domains', DomainsListAPIView.as_view(), name='api_domains_list'),
    path('api/domain/<str:domain_id>', DomainDetailAPIView.as_view(), name='api_domain_detail'),

    # 헬스체크
    path('api/health', HealthCheckAPIView.as_view(), name='api_health'),
]
