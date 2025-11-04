"""
Law MAS API URLs

완전 자동화 엔드포인트:
- POST /agents/law/upload-pdf/     → PDF 업로드 및 자동 처리
- GET  /agents/law/domains/         → 도메인 목록 조회
"""

from django.urls import path
from . import pdf_upload_api

app_name = 'law'

urlpatterns = [
    # PDF 업로드 (완전 자동)
    path('upload-pdf/', pdf_upload_api.upload_pdf, name='upload_pdf'),

    # 도메인 목록 조회
    path('domains/', pdf_upload_api.list_domains, name='list_domains'),
]
