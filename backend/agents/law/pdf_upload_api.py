"""
PDF 업로드 API - 완전 자동화

사용자가 PDF 업로드하면:
1. 자동 파싱
2. Neo4j 저장
3. 임베딩 생성
4. 도메인 자동 할당
5. DomainAgent 생성/업데이트

사용 방법:
POST /agents/law/upload-pdf/
Body: multipart/form-data
  - file: PDF 파일
"""

import logging
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from .agent_manager import AgentManager

logger = logging.getLogger(__name__)

# AgentManager 싱글톤
_agent_manager = None


def get_agent_manager():
    """AgentManager 싱글톤 인스턴스"""
    global _agent_manager
    if _agent_manager is None:
        _agent_manager = AgentManager()
    return _agent_manager


@csrf_exempt
@require_http_methods(["POST"])
def upload_pdf(request):
    """
    PDF 업로드 및 자동 처리

    Request:
        POST /agents/law/upload-pdf/
        Content-Type: multipart/form-data
        Body: file=<PDF 파일>

    Response:
        {
            "success": true,
            "law_name": "건축법",
            "hang_count": 245,
            "domains_touched": 3,
            "new_domains": ["건축규제", "안전기준"],
            "duration_seconds": 12.5
        }
    """
    try:
        # PDF 파일 가져오기
        if 'file' not in request.FILES:
            return JsonResponse({
                'success': False,
                'error': 'PDF 파일이 없습니다. (file parameter required)'
            }, status=400)

        pdf_file = request.FILES['file']

        # 임시 저장
        import os
        import tempfile

        temp_dir = tempfile.gettempdir()
        temp_path = os.path.join(temp_dir, pdf_file.name)

        with open(temp_path, 'wb') as f:
            for chunk in pdf_file.chunks():
                f.write(chunk)

        logger.info(f"PDF uploaded: {pdf_file.name}")

        # AgentManager로 자동 처리
        manager = get_agent_manager()

        # 처리 전 도메인 개수
        domains_before = set(manager.domains.keys())

        # ✅ 완전 자동 처리!
        result = manager.process_new_pdf(temp_path)

        # 처리 후 도메인 개수
        domains_after = set(manager.domains.keys())
        new_domains = domains_after - domains_before

        # 새 도메인 이름 가져오기
        new_domain_names = [
            manager.domains[domain_id].domain_name
            for domain_id in new_domains
        ]

        # 임시 파일 삭제
        os.remove(temp_path)

        # 성공 응답
        return JsonResponse({
            'success': True,
            'law_name': result['law_name'],
            'hang_count': result['hang_count'],
            'domains_touched': result['domains_touched'],
            'new_domains': new_domain_names,
            'total_domains': len(manager.domains),
            'duration_seconds': result['duration_seconds'],
            'timestamp': result['timestamp']
        })

    except Exception as e:
        logger.error(f"PDF upload failed: {e}")
        import traceback
        traceback.print_exc()

        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@require_http_methods(["GET"])
def list_domains(request):
    """
    현재 도메인 목록 조회

    Response:
        {
            "domains": [
                {
                    "domain_id": "...",
                    "domain_name": "도시계획",
                    "node_count": 245,
                    "neighbor_count": 2
                },
                ...
            ],
            "total_domains": 5,
            "total_nodes": 2987
        }
    """
    try:
        manager = get_agent_manager()

        domains_info = [
            domain.to_dict()
            for domain in manager.domains.values()
        ]

        total_nodes = sum(d['node_count'] for d in domains_info)

        return JsonResponse({
            'domains': domains_info,
            'total_domains': len(domains_info),
            'total_nodes': total_nodes
        })

    except Exception as e:
        logger.error(f"List domains failed: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)
