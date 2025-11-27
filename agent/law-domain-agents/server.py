"""
Dynamic FastAPI Server for Law Domain Agents

서버 하나가 모든 도메인 에이전트를 관리
Neo4j에서 도메인 목록을 동적으로 읽어서 A2A 엔드포인트 자동 생성
"""

import sys
import os
from pathlib import Path

# Add paths
sys.path.insert(0, str(Path(__file__).parent))

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Annotated, Dict, Any, Optional, List
from pydantic import BaseModel, Field
from functools import lru_cache
from datetime import datetime
from uuid import uuid4
import logging

from domain_manager import DomainManager, get_domain_manager, DomainInfo
from domain_agent_factory import DomainAgentFactory, get_agent_factory, LawDomainAgent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============== Pydantic Models (A2A Protocol) ==============

class A2AMessagePart(BaseModel):
    """A2A 메시지 파트"""
    kind: str = "text"  # 또는 "text" 필드
    text: Optional[str] = None

    class Config:
        # kind 또는 text 필드 허용
        extra = "allow"


class A2AMessage(BaseModel):
    """A2A 메시지"""
    parts: list[A2AMessagePart]
    messageId: Optional[str] = None
    contextId: Optional[str] = None
    role: str = "user"


class JSONRPCRequest(BaseModel):
    """JSON-RPC 2.0 요청"""
    jsonrpc: str = "2.0"
    method: str
    params: Optional[Dict[str, Any]] = None
    id: str = Field(default_factory=lambda: str(uuid4()))


class JSONRPCResponse(BaseModel):
    """JSON-RPC 2.0 응답"""
    jsonrpc: str = "2.0"
    result: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None
    id: str


# ============== Lifespan Management ==============

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI Lifespan - Startup & Shutdown

    Startup:
    1. DomainManager 초기화 (Neo4j에서 도메인 로드)
    2. DomainAgentFactory 초기화
    3. 각 도메인마다 A2A 엔드포인트 동적 등록

    Shutdown:
    4. 리소스 정리
    """
    logger.info("=" * 70)
    logger.info("Law Domain Agent Server - Starting...")
    logger.info("=" * 70)

    # [1] DomainManager 초기화
    domain_manager = get_domain_manager()
    domains = domain_manager.get_all_domains()

    logger.info(f"✓ Loaded {len(domains)} domains from Neo4j:")
    for domain in domains:
        logger.info(f"  - {domain.domain_name} ({domain.node_count} nodes)")

    # [2] DomainAgentFactory 초기화
    agent_factory = get_agent_factory()

    # 각 도메인마다 에이전트 생성 (lazy loading도 가능하지만 여기선 미리 생성)
    for domain in domains:
        agent_factory.create_agent(domain)

    logger.info(f"✓ Created {len(domains)} domain agents")

    # [3] App state에 저장
    app.state.domain_manager = domain_manager
    app.state.agent_factory = agent_factory

    # [4] 동적 라우트 등록
    register_a2a_routes(app, domain_manager, agent_factory)

    logger.info("=" * 70)
    logger.info("Server Ready! Listening on http://0.0.0.0:8011")
    logger.info("=" * 70)

    yield  # 서버 실행 중

    # Shutdown
    logger.info("Shutting down...")
    agent_factory.clear_cache()
    logger.info("Shutdown complete")


# ============== FastAPI App ==============

app = FastAPI(
    title="Law Domain Agent Server",
    description="Dynamic multi-agent system with A2A protocol",
    version="2.0.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============== Dependencies ==============

def get_dm() -> DomainManager:
    """DomainManager 의존성"""
    return get_domain_manager()


def get_af() -> DomainAgentFactory:
    """AgentFactory 의존성"""
    return get_agent_factory()


# ============== Dynamic Route Registration ==============

def register_a2a_routes(
    app: FastAPI,
    domain_manager: DomainManager,
    agent_factory: DomainAgentFactory
):
    """
    각 도메인마다 A2A 프로토콜 엔드포인트 동적 등록

    엔드포인트:
    - GET /.well-known/agent-card/{slug}.json
    - POST /messages/{slug}
    """
    domains = domain_manager.get_all_domains()

    for domain in domains:
        slug = domain.agent_slug()

        # ===== Agent Card 엔드포인트 =====
        def make_agent_card_handler(domain_info: DomainInfo):
            async def handler():
                return generate_agent_card(domain_info)
            handler.__name__ = f"agent_card_{slug}"  # 고유 이름
            return handler

        app.add_api_route(
            path=f"/.well-known/agent-card/{slug}.json",
            endpoint=make_agent_card_handler(domain),
            methods=["GET"],
            name=f"agent_card_{slug}",
            tags=["A2A Protocol"]
        )

        # ===== Message 엔드포인트 =====
        def make_message_handler(domain_info: DomainInfo):
            async def handler(request: Request):
                body = await request.json()
                return await handle_a2a_message(domain_info, body, agent_factory)
            handler.__name__ = f"messages_{slug}"  # 고유 이름
            return handler

        app.add_api_route(
            path=f"/messages/{slug}",
            endpoint=make_message_handler(domain),
            methods=["POST"],
            name=f"messages_{slug}",
            tags=["A2A Protocol"]
        )

        logger.info(f"  ✓ Registered A2A endpoints for '{slug}'")


# ============== Helper Functions ==============

def generate_agent_card(domain: DomainInfo) -> Dict[str, Any]:
    """
    Agent Card 생성 (Google ADK 호환 형식)

    Google ADK 형식 (agent/a2a/langraph_agent/server.py 패턴 참조)
    """
    slug = domain.agent_slug()

    # 도메인별 상세 설명 (도메인 ID 기반 매칭으로 Orchestrator 라우팅 정확도 향상)
    # 실제 Neo4j 도메인 이름은 축약형이므로 domain_id로 정확히 매칭
    domain_id = domain.domain_id

    # Domain ID별 상세 설명 매핑
    domain_descriptions_by_id = {
        "domain_09b3af0d": (  # 국토 계획 및 이용 (121 nodes)
            "Expert in land use planning and zoning regulations. "
            "Handles questions about 용도지역 (zoning districts), 용도지구 (zoning areas), "
            "용도구역 (zoning zones), 지구단위계획 (district unit plans), "
            "개발행위허가 (development permits), 도시관리계획 (urban management plans). "
            f"Specializes in {domain.domain_name} law with {domain.node_count} articles covering urban planning framework and zoning systems."
        ),
        "domain_3be25bdc": (  # 국토 이용 및 관리
            "Expert in land use management and regional planning. "
            "Specializes in 토지이용계획 (land use plans), 지역지구 관리 (district management), "
            f"토지거래허가 (land transaction permits). Covers {domain.domain_name} law ({domain.node_count} articles)."
        ),
        "domain_fad24752": (  # 건축 및 시설 계획
            "Expert in building codes and facility planning regulations. "
            "Handles questions about 건축허가 (building permits), 건축기준 (construction standards), "
            f"시설기준 (facility standards). Specializes in {domain.domain_name} ({domain.node_count} articles)."
        ),
        "domain_c283b545": (  # 도시계획 및 개발 사업
            "Expert in urban planning and development projects. "
            "Specializes in 도시개발사업 (urban development projects), 재개발 (redevelopment), "
            f"재건축 (reconstruction), development approvals. Covers {domain.domain_name} ({domain.node_count} articles)."
        ),
        "domain_676e7400": (  # 국토 이용 및 건축제한
            "Expert in land use restrictions and building limitations. "
            "Handles questions about 건축제한 (building restrictions), 용도제한 (use restrictions), "
            f"지역별 건축규제 (regional building regulations). Specializes in {domain.domain_name} ({domain.node_count} articles)."
        ),
    }

    # domain_id로 설명 가져오기 (없으면 기본 설명)
    description = domain_descriptions_by_id.get(
        domain_id,
        f"Korean Law Domain Agent - {domain.domain_name} ({domain.node_count} articles)"
    )

    return {
        "capabilities": {},  # Google ADK는 dict 요구
        "defaultInputModes": ["text/plain"],
        "defaultOutputModes": ["text/plain"],
        "description": description,
        "name": domain.domain_name,
        "preferredTransport": "JSONRPC",
        "protocolVersion": "0.3.0",
        "skills": [
            {
                "description": f"Search Korean law in {domain.domain_name} domain",
                "id": "legal_search",
                "name": "legal_search",
                "tags": ["law", "search"]
            },
            {
                "description": "RNE/INE algorithm for graph-based search",
                "id": "semantic_graph_search",
                "name": "semantic_graph_search",
                "tags": ["graph", "semantic"]
            }
        ],
        "supportsAuthenticatedExtendedCard": False,
        "url": f"http://localhost:8011/messages/{slug}",
        "version": "2.0.0"
    }


async def handle_a2a_message(
    domain: DomainInfo,
    body: Dict[str, Any],
    agent_factory: DomainAgentFactory
) -> JSONRPCResponse:
    """
    A2A 메시지 처리 (JSON-RPC 2.0)

    Args:
        domain: 도메인 정보
        body: JSON-RPC 요청 본문
        agent_factory: 에이전트 팩토리

    Returns:
        JSON-RPC 응답
    """
    request_id = body.get("id", str(uuid4()))

    try:
        # 메소드 검증
        method = body.get("method")
        if method != "message/send":
            return JSONRPCResponse(
                id=request_id,
                error={
                    "code": -32601,
                    "message": "Method not found",
                    "data": {"method": method}
                }
            ).model_dump()

        # 메시지 추출
        params = body.get("params", {})
        message_data = params.get("message", {})
        parts = message_data.get("parts", [])

        if not parts:
            return JSONRPCResponse(
                id=request_id,
                error={
                    "code": -32602,
                    "message": "Invalid params: No message parts"
                }
            ).model_dump()

        # 텍스트 결합
        message_text = " ".join(
            part.get("text", "")
            for part in parts
            if "text" in part
        )

        if not message_text.strip():
            return JSONRPCResponse(
                id=request_id,
                error={
                    "code": -32602,
                    "message": "Invalid params: Empty message"
                }
            ).model_dump()

        logger.info(f"[{domain.domain_name}] Processing: {message_text[:50]}...")

        # 에이전트 가져오기
        agent = agent_factory.get_agent(domain.domain_id)

        if not agent:
            # 에이전트가 없으면 생성
            agent = agent_factory.create_agent(domain)

        # 에이전트 실행 (async)
        response_text = await agent.ainvoke(message_text)

        logger.info(f"[{domain.domain_name}] Response generated")

        # JSON-RPC 응답 (Google ADK 형식)
        return JSONRPCResponse(
            id=request_id,
            result={
                "kind": "message",
                "message_id": str(uuid4()),
                "role": "agent",
                "parts": [{"kind": "text", "text": response_text}]
            }
        ).model_dump()

    except Exception as e:
        logger.error(f"[{domain.domain_name}] Error: {e}", exc_info=True)
        return JSONRPCResponse(
            id=request_id,
            error={
                "code": -32603,
                "message": "Internal error",
                "data": {"error": str(e)}
            }
        ).model_dump()


# ============== Static Routes ==============

@app.get("/")
async def root():
    """루트 엔드포인트"""
    return {
        "service": "Law Domain Agent Server",
        "version": "2.0.0",
        "protocol": "A2A/1.0",
        "endpoints": {
            "domains": "/domains",
            "health": "/health",
            "agent_cards": "/.well-known/agent-card/{slug}.json",
            "messages": "/messages/{slug}"
        }
    }


@app.get("/domains")
async def list_domains(dm: Annotated[DomainManager, Depends(get_dm)]):
    """도메인 목록"""
    domains = dm.get_all_domains()

    return {
        "total": len(domains),
        "domains": [
            {
                "domain_id": d.domain_id,
                "domain_name": d.domain_name,
                "agent_slug": d.agent_slug(),
                "node_count": d.node_count,
                "endpoints": {
                    "agent_card": f"/.well-known/agent-card/{d.agent_slug()}.json",
                    "messages": f"/messages/{d.agent_slug()}"
                }
            }
            for d in domains
        ]
    }


@app.get("/domains/{slug}/info")
async def get_domain_info(
    slug: str,
    dm: Annotated[DomainManager, Depends(get_dm)]
):
    """특정 도메인 정보"""
    domain = dm.get_domain_by_slug(slug)

    if not domain:
        raise HTTPException(status_code=404, detail=f"Domain '{slug}' not found")

    return {
        "domain_id": domain.domain_id,
        "domain_name": domain.domain_name,
        "agent_slug": domain.agent_slug(),
        "description": domain.description,
        "node_count": domain.node_count,
        "created_at": domain.created_at.isoformat(),
        "updated_at": domain.updated_at.isoformat()
    }


@app.post("/domains/refresh")
async def refresh_domains(dm: Annotated[DomainManager, Depends(get_dm)]):
    """도메인 목록 새로고침"""
    stats = dm.refresh()
    return {
        "status": "refreshed",
        "stats": stats
    }


@app.get("/health")
async def health_check(
    dm: Annotated[DomainManager, Depends(get_dm)],
    af: Annotated[DomainAgentFactory, Depends(get_af)]
):
    """헬스 체크"""
    domains = dm.get_all_domains()
    agent_stats = af.get_stats()

    return {
        "status": "healthy",
        "domains_loaded": len(domains),
        "agents_created": agent_stats["total_agents"],
        "timestamp": datetime.now().isoformat()
    }


# ============== REST API for Frontend Integration ==============

class LawSearchRequest(BaseModel):
    """프론트엔드 검색 요청"""
    query: str
    limit: int = 10


class LawArticle(BaseModel):
    """법률 조항"""
    hang_id: str
    content: str
    unit_path: str
    similarity: float
    stages: List[str]
    source: str = "my_domain"
    # Enriched fields from law_utils
    law_name: Optional[str] = None
    law_type: Optional[str] = None
    article: Optional[str] = None


class SearchStats(BaseModel):
    """검색 통계"""
    total: int
    vector_count: int = 0
    relationship_count: int = 0
    graph_expansion_count: int = 0
    my_domain_count: int = 0


class LawSearchResponse(BaseModel):
    """프론트엔드 검색 응답"""
    results: List[LawArticle]
    stats: SearchStats
    domain_id: Optional[str] = None
    domain_name: Optional[str] = None
    response_time: Optional[int] = None


def calculate_search_stats(results: List[Dict]) -> SearchStats:
    """검색 결과에서 통계 계산"""
    stats = {
        "total": len(results),
        "vector_count": 0,
        "relationship_count": 0,
        "graph_expansion_count": 0,
        "my_domain_count": len(results)
    }

    for result in results:
        stage = result.get("stage", "")

        if "vector" in stage:
            stats["vector_count"] += 1
        if "relationship" in stage:
            stats["relationship_count"] += 1
        if "rne" in stage or "graph" in stage:
            stats["graph_expansion_count"] += 1

    return SearchStats(**stats)


@app.post("/api/search")
async def rest_api_search(
    request: LawSearchRequest,
    dm: Annotated[DomainManager, Depends(get_dm)],
    af: Annotated[DomainAgentFactory, Depends(get_af)]
) -> LawSearchResponse:
    """
    REST API: 자동 라우팅 검색

    프론트엔드와 호환되는 REST API 엔드포인트
    """
    import time
    start_time = time.time()

    try:
        # 첫 번째 도메인 선택 (TODO: 자동 라우팅 로직 추가)
        domains = dm.get_all_domains()
        if not domains:
            raise HTTPException(status_code=500, detail="No domains available")

        domain = domains[0]

        # 에이전트 가져오기
        agent = af.get_agent(domain.domain_id)
        if not agent:
            agent = af.create_agent(domain)

        # 검색 엔진 직접 호출 (LangGraph 우회)
        search_results = agent.search_engine.search(request.query, top_k=request.limit)

        # 결과 변환
        articles = []
        for result in search_results:
            articles.append(LawArticle(
                hang_id=result.get("hang_id", ""),
                content=result.get("content", ""),
                unit_path=result.get("unit_path", ""),
                similarity=result.get("similarity", 0.0),
                stages=[result.get("stage", "unknown")],
                source="my_domain",
                # Include enriched fields
                law_name=result.get("law_name"),
                law_type=result.get("law_type"),
                article=result.get("article")
            ))

        # 통계 계산
        stats = calculate_search_stats(search_results)

        # 응답 시간 계산
        response_time = int((time.time() - start_time) * 1000)

        return LawSearchResponse(
            results=articles,
            stats=stats,
            domain_id=domain.domain_id,
            domain_name=domain.domain_name,
            response_time=response_time
        )

    except Exception as e:
        logger.error(f"REST API search error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/domain/{domain_id}/search")
async def rest_api_domain_search(
    domain_id: str,
    request: LawSearchRequest,
    dm: Annotated[DomainManager, Depends(get_dm)],
    af: Annotated[DomainAgentFactory, Depends(get_af)]
) -> LawSearchResponse:
    """
    REST API: 특정 도메인 검색
    """
    import time
    start_time = time.time()

    try:
        # 도메인 찾기
        domain = dm.get_domain(domain_id)
        if not domain:
            raise HTTPException(status_code=404, detail=f"Domain '{domain_id}' not found")

        # 에이전트 가져오기
        agent = af.get_agent(domain.domain_id)
        if not agent:
            agent = af.create_agent(domain)

        # 검색 엔진 직접 호출
        search_results = agent.search_engine.search(request.query, top_k=request.limit)

        # 결과 변환
        articles = []
        for result in search_results:
            articles.append(LawArticle(
                hang_id=result.get("hang_id", ""),
                content=result.get("content", ""),
                unit_path=result.get("unit_path", ""),
                similarity=result.get("similarity", 0.0),
                stages=[result.get("stage", "unknown")],
                source="my_domain",
                # Include enriched fields
                law_name=result.get("law_name"),
                law_type=result.get("law_type"),
                article=result.get("article")
            ))

        # 통계 계산
        stats = calculate_search_stats(search_results)

        # 응답 시간 계산
        response_time = int((time.time() - start_time) * 1000)

        return LawSearchResponse(
            results=articles,
            stats=stats,
            domain_id=domain.domain_id,
            domain_name=domain.domain_name,
            response_time=response_time
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"REST API domain search error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/domains")
async def rest_api_domains(dm: Annotated[DomainManager, Depends(get_dm)]):
    """
    REST API: 도메인 목록

    프론트엔드 호환 버전 (/domains와 동일)
    """
    domains = dm.get_all_domains()

    return {
        "total": len(domains),
        "domains": [
            {
                "domain_id": d.domain_id,
                "domain_name": d.domain_name,
                "node_count": d.node_count,
                "created_at": d.created_at.isoformat(),
                "updated_at": d.updated_at.isoformat()
            }
            for d in domains
        ]
    }


@app.get("/api/health")
async def rest_api_health(
    dm: Annotated[DomainManager, Depends(get_dm)],
    af: Annotated[DomainAgentFactory, Depends(get_af)]
):
    """
    REST API: 헬스체크

    프론트엔드 호환 버전 (/health와 동일)
    """
    domains = dm.get_all_domains()
    agent_stats = af.get_stats()

    return {
        "status": "healthy",
        "domains_loaded": len(domains),
        "agents_created": agent_stats["total_agents"],
        "timestamp": datetime.now().isoformat()
    }


# ============== Run Server ==============

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8011,
        log_level="info"
    )
