"""
Law Search API

법규 검색 API 엔드포인트.
SemanticRNE (범위 기반) 및 SemanticINE (k-NN) 지원.
"""

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
import json
import logging

# 로거 설정
logger = logging.getLogger(__name__)

# Lazy loading을 위한 전역 변수
_embedding_model = None
_law_repository = None
_semantic_rne = None
_semantic_ine = None


def get_embedding_model():
    """임베딩 모델 Lazy Loading"""
    global _embedding_model
    if _embedding_model is None:
        from sentence_transformers import SentenceTransformer
        _embedding_model = SentenceTransformer('jhgan/ko-sbert-sts')
    return _embedding_model


def get_law_repository():
    """LawRepository Lazy Loading"""
    global _law_repository
    if _law_repository is None:
        from graph_db.services.neo4j_service import Neo4jService
        from graph_db.algorithms.repository.law_repository import LawRepository

        neo4j = Neo4jService()
        _law_repository = LawRepository(neo4j)
    return _law_repository


def get_semantic_rne():
    """SemanticRNE Lazy Loading"""
    global _semantic_rne
    if _semantic_rne is None:
        from graph_db.algorithms.core.semantic_rne import SemanticRNE

        _semantic_rne = SemanticRNE(
            cost_calculator=None,
            repository=get_law_repository(),
            embedding_model=get_embedding_model()
        )
    return _semantic_rne


def get_semantic_ine():
    """SemanticINE Lazy Loading"""
    global _semantic_ine
    if _semantic_ine is None:
        from graph_db.algorithms.core.semantic_ine import SemanticINE

        _semantic_ine = SemanticINE(
            cost_calculator=None,
            repository=get_law_repository(),
            embedding_model=get_embedding_model()
        )
    return _semantic_ine


def index(request):
    """
    Law app index view.
    """
    return JsonResponse({
        'status': 'ok',
        'message': 'Law Search API is running',
        'app': 'law',
        'endpoints': {
            '/law/search/rne/': 'Semantic RNE (범위 기반 검색)',
            '/law/search/ine/': 'Semantic INE (k-NN 검색)',
            '/law/stats/': '법규 데이터 통계'
        }
    })


@require_http_methods(["GET", "POST"])
def search_rne(request):
    """
    Semantic RNE 검색 API (범위 기반)

    **엔드포인트**: `GET /law/search/rne/`

    **파라미터**:
    - q: 검색 쿼리 (required)
    - threshold: 유사도 임계값 (default: 0.75)
    - max_results: 최대 결과 수 (default: None)
    - initial_candidates: 초기 후보 수 (default: 10)

    **응답**:
    ```json
    {
        "query": "도시계획 수립 절차",
        "algorithm": "SemanticRNE",
        "threshold": 0.75,
        "results": [
            {
                "hang_id": 123,
                "full_id": "국토의 계획 및 이용에 관한 법률::제13조::제1항",
                "law_name": "국토의 계획 및 이용에 관한 법률",
                "article_number": "제13조제1항",
                "content": "...",
                "similarity": 0.89,
                "expansion_type": "vector"
            },
            ...
        ],
        "count": 15,
        "execution_time_ms": 5.2
    }
    ```

    **Example**:
    ```bash
    curl "http://localhost:8000/law/search/rne/?q=도시계획+수립&threshold=0.75"
    ```
    """
    import time

    # 파라미터 파싱
    if request.method == 'POST':
        try:
            body = json.loads(request.body)
            query_text = body.get('q', '')
            threshold = float(body.get('threshold', 0.75))
            max_results = body.get('max_results')
            initial_candidates = int(body.get('initial_candidates', 10))
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
    else:  # GET
        query_text = request.GET.get('q', '')
        threshold = float(request.GET.get('threshold', 0.75))
        max_results = request.GET.get('max_results')
        initial_candidates = int(request.GET.get('initial_candidates', 10))

    # 쿼리 검증
    if not query_text:
        return JsonResponse({'error': 'Query parameter "q" is required'}, status=400)

    if threshold < 0 or threshold > 1:
        return JsonResponse({'error': 'Threshold must be between 0 and 1'}, status=400)

    # max_results 변환
    if max_results:
        try:
            max_results = int(max_results)
        except ValueError:
            max_results = None

    try:
        # SemanticRNE 실행
        start_time = time.time()
        rne = get_semantic_rne()
        results, _ = rne.execute_query(
            query_text=query_text,
            similarity_threshold=threshold,
            max_results=max_results,
            initial_candidates=initial_candidates
        )
        execution_time = (time.time() - start_time) * 1000  # ms

        logger.info(f"RNE query: '{query_text}', threshold={threshold}, results={len(results)}, time={execution_time:.2f}ms")

        return JsonResponse({
            'query': query_text,
            'algorithm': 'SemanticRNE',
            'threshold': threshold,
            'max_results': max_results,
            'initial_candidates': initial_candidates,
            'results': results,
            'count': len(results),
            'execution_time_ms': round(execution_time, 2),
            'note': 'relevance_score는 그래프 거리 기반 관련성 점수 (0~1)'
        })

    except ValueError as e:
        logger.warning(f"RNE validation error: {e}, query='{query_text}'")
        return JsonResponse({
            'error': 'Validation error',
            'detail': str(e),
            'query': query_text
        }, status=400)

    except Exception as e:
        logger.error(f"RNE execution error: {e}, query='{query_text}'", exc_info=True)
        return JsonResponse({
            'error': 'Internal server error',
            'detail': str(e),
            'query': query_text
        }, status=500)


@require_http_methods(["GET", "POST"])
def search_ine(request):
    """
    Semantic INE 검색 API (k-NN)

    **엔드포인트**: `GET /law/search/ine/`

    **파라미터**:
    - q: 검색 쿼리 (required)
    - k: 결과 개수 (default: 5)
    - initial_candidates: 초기 후보 수 (default: 20)

    **응답**:
    ```json
    {
        "query": "도시계획",
        "algorithm": "SemanticINE",
        "k": 5,
        "results": [
            {
                "hang_id": 123,
                "full_id": "...",
                "article_number": "제13조제1항",
                "content": "...",
                "similarity": 0.89,
                "rank": 1
            },
            ...
        ],
        "count": 5,
        "execution_time_ms": 3.8
    }
    ```

    **Example**:
    ```bash
    curl "http://localhost:8000/law/search/ine/?q=도시계획&k=5"
    ```
    """
    import time

    # 파라미터 파싱
    if request.method == 'POST':
        try:
            body = json.loads(request.body)
            query_text = body.get('q', '')
            k = int(body.get('k', 5))
            initial_candidates = int(body.get('initial_candidates', 20))
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
    else:  # GET
        query_text = request.GET.get('q', '')
        k = int(request.GET.get('k', 5))
        initial_candidates = int(request.GET.get('initial_candidates', 20))

    # 쿼리 검증
    if not query_text:
        return JsonResponse({'error': 'Query parameter "q" is required'}, status=400)

    if k <= 0:
        return JsonResponse({'error': 'k must be positive'}, status=400)

    try:
        # SemanticINE 실행
        start_time = time.time()
        ine = get_semantic_ine()
        results = ine.execute_query(
            query_text=query_text,
            k=k,
            initial_candidates=initial_candidates
        )
        execution_time = (time.time() - start_time) * 1000  # ms

        logger.info(f"INE query: '{query_text}', k={k}, results={len(results)}, time={execution_time:.2f}ms")

        return JsonResponse({
            'query': query_text,
            'algorithm': 'SemanticINE',
            'k': k,
            'initial_candidates': initial_candidates,
            'results': results,
            'count': len(results),
            'execution_time_ms': round(execution_time, 2),
            'note': 'relevance_score는 그래프 거리 기반 관련성 점수 (0~1)'
        })

    except ValueError as e:
        logger.warning(f"INE validation error: {e}, query='{query_text}'")
        return JsonResponse({
            'error': 'Validation error',
            'detail': str(e),
            'query': query_text
        }, status=400)

    except Exception as e:
        logger.error(f"INE execution error: {e}, query='{query_text}'", exc_info=True)
        return JsonResponse({
            'error': 'Internal server error',
            'detail': str(e),
            'query': query_text
        }, status=500)


@require_http_methods(["GET"])
def stats(request):
    """
    법규 데이터 통계 API

    **엔드포인트**: `GET /law/stats/`

    **응답**:
    ```json
    {
        "total_hangs": 1586,
        "hangs_with_embedding": 1586,
        "embedding_dimension": 3072,
        "total_jos": 422,
        "total_hos": 1025,
        "vector_index": "hang_embedding_index",
        "algorithm_info": {
            "semantic_rne": "Range-based search",
            "semantic_ine": "k-NN search"
        }
    }
    ```
    """
    try:
        repo = get_law_repository()
        stats_data = repo.get_statistics()

        stats_data['vector_index'] = 'hang_embedding_index'
        stats_data['algorithm_info'] = {
            'semantic_rne': 'Range-based search (threshold-based)',
            'semantic_ine': 'k-NN search (top-k results)'
        }

        return JsonResponse(stats_data)

    except Exception as e:
        return JsonResponse({
            'error': str(e)
        }, status=500)
