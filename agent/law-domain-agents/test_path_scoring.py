"""
Path-based Scoring 프로토타입 검증

CaseGNN 논문 기반 - Graph 경로를 고려한 검색 개선
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "shared"))

from neo4j_client import get_neo4j_client

def get_hang_with_paths(query_keyword: str):
    """
    특정 키워드를 포함하는 HANG과 전체 경로 조회
    """
    neo4j = get_neo4j_client()
    session = neo4j.get_session()

    # 전체 경로 조회 쿼리
    cypher = """
    MATCH (h:HANG)
    WHERE h.content CONTAINS $keyword

    // 전체 경로 조회 (LAW까지)
    MATCH path = (law:LAW)-[:CONTAINS*]->(h)

    WITH h, path,
         [node in nodes(path) | {
             label: labels(node)[0],
             title: COALESCE(node.title, node.name, node.unit_number),
             full_id: node.full_id
         }] as path_nodes

    RETURN
        h.full_id as hang_id,
        h.content as content,
        h.unit_path as unit_path,
        path_nodes
    LIMIT 10
    """

    results = session.run(cypher, {'keyword': query_keyword})

    found_paths = []
    for record in results:
        found_paths.append({
            'hang_id': record['hang_id'],
            'content': record['content'][:100] + '...',
            'unit_path': record['unit_path'],
            'path_nodes': record['path_nodes']
        })

    session.close()
    return found_paths


def compute_path_score(path_nodes):
    """
    CaseGNN 방식의 간단한 path scoring

    한국 법률 구조 기반 휴리스틱:
    - "제12장" → 0.1배 penalty (부칙 - appendix)
    - "제4장" or lower numbered chapters → 1.5배 boost (본문 - main content)
    - "절" (section) → 1.1배 boost (구조화된 본문)
    """
    score = 0.5  # base score

    # Check for chapter numbers in full_id
    for node in path_nodes:
        full_id = node.get('full_id', '') or ''
        label = node.get('label', '')

        # Appendix penalty: 제12장 is typically appendix
        if '::제12장' in full_id:
            score *= 0.1
            print(f"  [PENALTY] 제12장 (부칙) 감지: {full_id} → score *= 0.1")

        # Main content boost: 제1장~제6장 are usually main content
        elif any(f'::제{i}장' in full_id for i in range(1, 7)):
            score *= 1.5
            chapter_num = next(i for i in range(1, 7) if f'::제{i}장' in full_id)
            print(f"  [BOOST] 제{chapter_num}장 (본문) 감지: {full_id} → score *= 1.5")

        # Section boost: presence of 절 indicates well-structured main content
        if label == 'JEOL' or '::제' in full_id and '절::' in full_id:
            score *= 1.1
            print(f"  [BOOST] 절 (section) 감지 → score *= 1.1")

    return min(score, 1.0)


if __name__ == "__main__":
    print("=" * 80)
    print("Path-based Scoring 프로토타입 테스트")
    print("=" * 80)

    # 1. "용도지역" 포함하는 HANG 조회
    keyword = "용도지역"
    print(f"\n[Step 1] '{keyword}' 포함 HANG 조회 (경로 포함)")
    print("-" * 80)

    paths = get_hang_with_paths(keyword)

    if not paths:
        print(f"No results found for '{keyword}'")
        sys.exit(0)

    print(f"Found {len(paths)} results\n")

    # 2. 각 경로의 path score 계산
    print("[Step 2] Path Score 계산")
    print("-" * 80)

    scored_paths = []
    for i, item in enumerate(paths, 1):
        print(f"\n{i}. {item['hang_id']}")
        path_titles = [n['title'] or f"[{n['label']}]" for n in item['path_nodes']]
        print(f"   Path: {' → '.join(path_titles)}")
        print(f"   Content: {item['content']}")

        # Path score 계산
        path_score = compute_path_score(item['path_nodes'])
        print(f"   → Final Path Score: {path_score:.3f}")

        scored_paths.append({
            **item,
            'path_score': path_score
        })

    # 3. Path score 기준 재정렬
    print("\n" + "=" * 80)
    print("[Step 3] Path Score 기준 Re-ranking")
    print("=" * 80)

    scored_paths.sort(key=lambda x: x['path_score'], reverse=True)

    print("\n재정렬된 결과:")
    for i, item in enumerate(scored_paths, 1):
        path_titles = [n['title'] or f"[{n['label']}]" for n in item['path_nodes']]
        path_str = ' → '.join(path_titles)
        print(f"\n{i}. [Score: {item['path_score']:.3f}] {item['hang_id']}")
        print(f"   Path: {path_str}")
        print(f"   Content: {item['content']}")

    # 4. 결과 분석
    print("\n" + "=" * 80)
    print("[분석]")
    print("=" * 80)

    top_result = scored_paths[0]
    top_full_id = top_result['hang_id']

    is_appendix = '::제12장' in top_full_id
    is_main_content = any(f'::제{i}장' in top_full_id for i in range(1, 7))

    if is_appendix:
        print("❌ 제12장(부칙) 경로가 1위 → Path scoring 실패")
        print(f"   부칙 결과: {top_full_id}")
    elif is_main_content:
        chapter_num = next(i for i in range(1, 7) if f'::제{i}장' in top_full_id)
        print(f"✅ 제{chapter_num}장(본문) 경로가 1위 → Path scoring 성공!")
        print(f"   본문 결과: {top_full_id}")
    else:
        print("⚠️ 확인 필요 - 예상치 못한 장 번호")
        print(f"   결과: {top_full_id}")

    print(f"\nPath Score: {top_result['path_score']:.3f}")
