"""
RNE (Range Network Expansion) 엔진

Integration.md 명세 기반 규정 준수 경로 탐색
"""

from heapq import heappush, heappop
from typing import Dict, List, Tuple, Set, Optional
from dataclasses import dataclass, field
from datetime import datetime, time as time_type
import sys


@dataclass
class Context:
    """라우팅 컨텍스트 (θ)"""
    vehicle_type: str  # "truck", "car", "bus"
    current_time: datetime
    axle_weight: float = 0.0  # 톤
    permits: List[str] = field(default_factory=list)

    def __repr__(self):
        return f"Context(vehicle={self.vehicle_type}, time={self.current_time.strftime('%H:%M')}, weight={self.axle_weight}t)"


class RNEEngine:
    """
    Range Network Expansion 엔진

    비용 반경 e 내 도달 가능한 노드 집합 Q_S(e;θ)를 계산하고,
    규정(Regulation) 기반 엣지 차단/가중치 조정을 수행합니다.

    알고리즘:
        Integration.md 5.1절 의사코드
        - 다익스트라 변형 (우선순위 큐 기반)
        - 비용 > e인 경우 조기 중단
        - 컨텍스트 θ에 따라 w'(e;θ) 동적 계산

    사용 예시:
        >>> from graph_db.services.neo4j_service import Neo4jService
        >>> neo4j = Neo4jService()
        >>> engine = RNEEngine(neo4j)
        >>> ctx = Context(vehicle_type="truck", current_time=datetime.now(), axle_weight=12.0)
        >>> reached, dist = engine.rne_expand(start_node_id, radius_e=900, context=ctx)
    """

    INF = 10**18  # 차단된 엣지 비용

    def __init__(self, neo4j_service=None):
        """
        Args:
            neo4j_service: Neo4jService 인스턴스 (없으면 자동 생성)
        """
        if neo4j_service is None:
            from graph_db.services.neo4j_service import Neo4jService
            self.neo4j = Neo4jService()
            self.neo4j.connect()
        else:
            self.neo4j = neo4j_service

    def calculate_edge_cost(self, segment: Dict, regulations: List[Dict], context: Context) -> float:
        """
        엣지 비용 계산 (규정 적용)

        비용 함수 (Integration.md 4절):
            w'(e;θ) = w(e) + Σ penalty(r;θ)  if 통과 가능
                    = +∞                      if 차단

        Args:
            segment: SEGMENT 관계 속성 {'baseTime', 'dir', 'axleWeight', ...}
            regulations: 적용 대상 Regulation 노드 목록
            context: 라우팅 컨텍스트

        Returns:
            float: 비용 (초), INF면 차단
        """
        base_cost = segment.get('baseTime', 0)

        for reg in regulations:
            reg_type = reg.get('type')

            # === 차단 규칙 ===
            if reg_type == "oneway":
                # 일방통행: 방향 불일치 시 차단
                if segment.get('dir') != reg.get('dir'):
                    return self.INF

            elif reg_type == "timeBan":
                # 시간대 금지
                if self._is_time_in_range(context.current_time, reg.get('start'), reg.get('end')):
                    return self.INF

            elif reg_type == "weightLimit":
                # 중량 제한
                if context.vehicle_type == "truck" and context.axle_weight > reg.get('limit', 0):
                    return self.INF

            # === 페널티 규칙 ===
            elif reg_type == "busOnly":
                # 버스 전용: 다른 차량은 5분 페널티
                if context.vehicle_type != "bus":
                    base_cost += 300

            elif reg_type == "toll":
                # 통행료: 시간 페널티 가산
                base_cost += reg.get('timePenalty', 0)

            elif reg_type == "schoolZone":
                # 스쿨존: 시간대 내 추가 시간
                if self._is_time_in_range(context.current_time, reg.get('start'), reg.get('end')):
                    base_cost += reg.get('extraTime', 60)

            # 기타 규정 타입은 무시

        return base_cost

    def rne_expand(self, src_id: int, radius_e: float, context: Context) -> Tuple[Set[int], Dict[int, float]]:
        """
        RNE 확장 (Range Network Expansion)

        의사코드 (Integration.md 5.1):
            PQ ← [(q,0)]; dist[q]=0; REACHED=∅
            while PQ not empty:
              (u, du) ← pop_min(PQ)
              if du > e: break
              REACHED ← REACHED ∪ {u}
              for each (u->v) with cost w'(u,v;θ):
                alt = du + w'(u,v;θ)
                if alt < dist[v] and alt ≤ e:
                  dist[v]=alt; push (v,alt)
            return REACHED, dist

        Args:
            src_id: 출발 노드 ID (Neo4j internal ID)
            radius_e: 비용 반경 (초)
            context: 라우팅 컨텍스트

        Returns:
            (reached, dist):
                reached: 도달 가능 노드 집합 (Set[int])
                dist: 각 노드까지의 최소 비용 (Dict[int, float])
        """
        dist = {src_id: 0.0}
        pq = [(0.0, src_id)]
        reached = set()

        while pq:
            d, u = heappop(pq)

            # 비용 초과 시 조기 중단
            if d > radius_e:
                break

            # 이미 방문한 노드 스킵
            if u in reached:
                continue

            reached.add(u)

            # 인접 노드 + 규정 가져오기
            neighbors = self._get_neighbors_with_regulations(u)

            for v, segment, regulations in neighbors:
                # 규정 기반 비용 계산
                cost = self.calculate_edge_cost(segment, regulations, context)

                # 차단된 엣지 스킵
                if cost >= self.INF:
                    continue

                alt = d + cost

                # 반경 내이고, 기존 거리보다 짧으면 업데이트
                if alt <= radius_e and alt < dist.get(v, self.INF):
                    dist[v] = alt
                    heappush(pq, (alt, v))

        return reached, dist

    def find_pois_in_range(self, src_id: int, radius_e: float, context: Context,
                           poi_label: str = "POI") -> List[Dict]:
        """
        반경 내 POI 검색 (Integration.md 5.2 후처리)

        Q_S(e;θ)의 노드 위에서만 POI를 탐색하여 false positive 제거

        Args:
            src_id: 출발 노드
            radius_e: 비용 반경 (초)
            context: 컨텍스트
            poi_label: POI 노드 레이블

        Returns:
            [{poi_id, name, distance, node_id}, ...]
        """
        # RNE 실행
        reached, dist = self.rne_expand(src_id, radius_e, context)

        if not reached:
            return []

        # 도달 가능 노드 위의 POI만 검색
        query = """
        UNWIND $reached_ids as node_id
        MATCH (n:RoadNode)-[:NEAR_POI]->(poi:POI)
        WHERE id(n) = node_id
        RETURN id(poi) as poi_id,
               poi.name as name,
               node_id,
               $distances[toString(node_id)] as distance
        ORDER BY distance ASC
        """

        distances_str = {str(k): v for k, v in dist.items()}

        with self.neo4j.driver.session() as session:
            result = session.run(query, reached_ids=list(reached), distances=distances_str)
            pois = [dict(rec) for rec in result]

        return pois

    def get_regulation_citations(self, regulation_ids: List[int]) -> List[Dict]:
        """
        규정 → SNDB 법률 조항 추적

        Args:
            regulation_ids: Regulation 노드 ID 목록

        Returns:
            [{'reg_id', 'reg_type', 'sndb_id', 'article_title', 'law_name'}, ...]
        """
        query = """
        UNWIND $reg_ids as reg_id
        MATCH (r:Regulation)-[:CITES]->(sndb:SNDB)
        WHERE id(r) = reg_id
        RETURN id(r) as reg_id,
               r.type as reg_type,
               sndb.id as sndb_id,
               sndb.article_title as article_title,
               sndb.law_name as law_name
        """

        with self.neo4j.driver.session() as session:
            result = session.run(query, reg_ids=regulation_ids)
            return [dict(rec) for rec in result]

    def _get_neighbors_with_regulations(self, node_id: int) -> List[Tuple[int, Dict, List[Dict]]]:
        """
        인접 노드 + 세그먼트 + 규정 가져오기

        쿼리 구조 (수정됨):
            (a:RoadNode)-[seg:SEGMENT]->(b:RoadNode)
            seg.zone_id로 Zone 매칭
            (Zone)-[:ENFORCES]->(r:Regulation)

        Returns:
            [(neighbor_id, segment_props, regulations)]
        """
        query = """
        MATCH (a:RoadNode)-[seg:SEGMENT]->(b:RoadNode)
        WHERE id(a) = $node_id
        OPTIONAL MATCH (z:Zone)-[:ENFORCES]->(r:Regulation)
        WHERE seg.zone_id = z.name
        RETURN id(b) as neighbor_id,
               properties(seg) as segment,
               collect(properties(r)) as regulations
        """

        with self.neo4j.driver.session() as session:
            result = session.run(query, node_id=node_id)
            return [
                (rec['neighbor_id'], rec['segment'], [r for r in rec['regulations'] if r])
                for rec in result
            ]

    def _is_time_in_range(self, current: datetime, start_str: Optional[str], end_str: Optional[str]) -> bool:
        """
        시간대 검사

        Args:
            current: 현재 시각
            start_str: 시작 시각 "HH:MM:SS"
            end_str: 종료 시각 "HH:MM:SS"

        Returns:
            bool: 범위 내 여부
        """
        if not start_str or not end_str:
            return False

        current_time = current.time()

        try:
            start = datetime.strptime(start_str, "%H:%M:%S").time()
            end = datetime.strptime(end_str, "%H:%M:%S").time()
        except ValueError:
            return False

        if start <= end:
            # 일반 구간 (예: 09:00 ~ 18:00)
            return start <= current_time <= end
        else:
            # 자정 넘어가는 구간 (예: 22:00 ~ 06:00)
            return current_time >= start or current_time <= end


# ==================== CLI 테스트 ====================

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding='utf-8')

    print("=" * 80)
    print("RNE Engine 테스트")
    print("=" * 80)

    try:
        from graph_db.services.neo4j_service import Neo4jService

        # Neo4j 연결
        neo4j = Neo4jService()
        engine = RNEEngine(neo4j)

        print("\n✅ RNE Engine 초기화 완료")
        print(f"   Neo4j URI: {neo4j.uri}")

        # 컨텍스트 설정
        ctx = Context(
            vehicle_type="truck",
            current_time=datetime(2025, 10, 30, 9, 0, 0),
            axle_weight=12.0,
            permits=[]
        )

        print(f"\n컨텍스트: {ctx}")

        # === 예시 1: 비용 계산 테스트 ===
        print("\n" + "=" * 80)
        print("[예시 1] 비용 계산 테스트")
        print("=" * 80)

        test_segment = {
            'baseTime': 120,  # 2분
            'dir': 'both',
            'axleWeight': 15.0
        }

        test_regulations = [
            {'type': 'busOnly'},  # 300초 페널티
            {'type': 'toll', 'timePenalty': 60},  # 1분 페널티
        ]

        cost = engine.calculate_edge_cost(test_segment, test_regulations, ctx)
        print(f"\n기본 비용: {test_segment['baseTime']}초")
        print(f"규정: {[r['type'] for r in test_regulations]}")
        print(f"최종 비용: {cost}초 (기대: 120 + 300 + 60 = 480)")

        # === 예시 2: 차단 테스트 ===
        print("\n" + "=" * 80)
        print("[예시 2] 차단 규칙 테스트")
        print("=" * 80)

        blocking_regs = [
            {'type': 'weightLimit', 'limit': 10.0}  # 12톤 트럭은 차단
        ]

        cost = engine.calculate_edge_cost(test_segment, blocking_regs, ctx)
        print(f"\n중량 제한: {blocking_regs[0]['limit']}톤")
        print(f"트럭 중량: {ctx.axle_weight}톤")
        print(f"결과: {'차단됨 (INF)' if cost >= engine.INF else f'{cost}초'}")

        # === 예시 3: RNE 확장 (실제 데이터 필요) ===
        print("\n" + "=" * 80)
        print("[예시 3] RNE 확장 (스켈레톤)")
        print("=" * 80)
        print("\n⚠️  실제 RoadNode가 없어 스킵")
        print("   도로 네트워크 생성 후 테스트 가능")

        # 실제 RoadNode가 있으면:
        # reached, dist = engine.rne_expand(start_node_id, 900, ctx)
        # print(f"도달 가능 노드: {len(reached)}개")

        print("\n" + "=" * 80)
        print("✅ 모든 테스트 완료")
        print("=" * 80)

    except Exception as e:
        print(f"\n❌ 오류: {e}")
        import traceback
        traceback.print_exc()
