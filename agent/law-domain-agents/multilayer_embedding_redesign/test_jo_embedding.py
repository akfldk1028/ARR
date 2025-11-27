"""
JO 임베딩 검증 테스트

1. JO 임베딩 저장 확인
2. "용도지역" 벡터 검색
3. 제4장 vs 제12장 순위 비교
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "shared"))

from neo4j_client import get_neo4j_client
import os

# OpenAI embedding 로드
from langchain_openai import OpenAIEmbeddings

def test_jo_embeddings():
    neo4j = get_neo4j_client()
    session = neo4j.get_session()

    output_path = Path(__file__).parent / "jo_test_results.txt"

    with open(output_path, 'w', encoding='utf-8') as f:
        def log(msg):
            f.write(msg + '\n')
            f.flush()
            print(msg)

        log("=" * 80)
        log("JO 임베딩 검증 테스트")
        log("=" * 80)

        # 1. JO 임베딩 저장 확인
        log("\n[Test 1] JO 임베딩 저장 확인")
        log("-" * 80)

        query = """
        MATCH (jo:JO)
        RETURN count(jo) as total,
               count(jo.embedding) as with_embedding,
               count(jo) - count(jo.embedding) as without_embedding
        """

        result = session.run(query).single()
        total = result['total']
        with_emb = result['with_embedding']
        without_emb = result['without_embedding']

        log(f"총 JO 노드: {total}")
        log(f"임베딩 있음: {with_emb}")
        log(f"임베딩 없음: {without_emb}")

        if with_emb == 770:
            log("[OK] 모든 JO 노드에 임베딩 저장 완료!")
        else:
            log(f"[WARN] {without_emb}개 JO 노드 임베딩 누락")

        # 2. "용도지역" 벡터 검색
        log("\n[Test 2] '용도지역' JO 노드 벡터 검색")
        log("-" * 80)

        # 쿼리 임베딩 생성
        embeddings = OpenAIEmbeddings(
            model="text-embedding-3-large",
            dimensions=3072
        )
        query_text = "용도지역의 지정"
        query_embedding = embeddings.embed_query(query_text)

        log(f"검색 쿼리: '{query_text}'")
        log(f"임베딩 차원: {len(query_embedding)}")

        # 벡터 유사도 검색
        search_query = """
        MATCH (jo:JO)
        WHERE jo.embedding IS NOT NULL

        WITH jo,
             vector.similarity.cosine(jo.embedding, $query_embedding) AS score

        ORDER BY score DESC
        LIMIT 10

        RETURN jo.full_id as full_id,
               jo.title as title,
               score,
               EXISTS((jo)-[:CONTAINS]->(:HANG)) as has_hang
        """

        results = session.run(search_query, {'query_embedding': query_embedding})

        log("\n검색 결과 (Top 10):")
        log("")

        results_list = list(results)

        for i, record in enumerate(results_list, 1):
            full_id = record['full_id']
            title = record['title']
            score = record['score']
            has_hang = record['has_hang']

            # 장 구분
            if '::제4장::' in full_id:
                chapter_info = "[제4장 - 본문]"
            elif '::제12장::' in full_id:
                chapter_info = "[제12장 - 부칙]"
            else:
                chapter_info = "[기타]"

            hang_info = "HANG O" if has_hang else "HANG X"

            log(f"{i}. {chapter_info} {hang_info} | Score: {score:.4f}")
            log(f"   ID: {full_id}")
            log(f"   Title: {title}")
            log("")

        # 3. 분석
        log("\n[Test 3] 결과 분석")
        log("-" * 80)

        # 1위 확인
        if results_list:
            top_result = results_list[0]
            top_id = top_result['full_id']

            if '::제4장::' in top_id and '36조' in top_id:
                log("[SUCCESS] 제4장 제36조가 1위로 검색됨!")
                log(f"  → {top_id}")
            elif '::제12장::' in top_id:
                log("[FAIL] 제12장(부칙)이 1위로 검색됨")
                log(f"  → {top_id}")
                log("  → Path scoring 필요")
            else:
                log("[UNEXPECTED] 예상치 못한 결과")
                log(f"  → {top_id}")

            # 제4장 vs 제12장 순위 비교
            log("\n제4장 vs 제12장 비교:")

            jang4_results = [r for r in results_list if '::제4장::' in r['full_id']]
            jang12_results = [r for r in results_list if '::제12장::' in r['full_id']]

            if jang4_results:
                log(f"  제4장 결과: {len(jang4_results)}개")
                for r in jang4_results[:3]:
                    idx = results_list.index(r) + 1
                    log(f"    #{idx}: {r['full_id']} (Score: {r['score']:.4f})")

            if jang12_results:
                log(f"  제12장 결과: {len(jang12_results)}개")
                for r in jang12_results[:3]:
                    idx = results_list.index(r) + 1
                    log(f"    #{idx}: {r['full_id']} (Score: {r['score']:.4f})")

        session.close()

        log("\n" + "=" * 80)
        log("테스트 완료")
        log(f"결과 저장: {output_path}")
        log("=" * 80)

if __name__ == "__main__":
    test_jo_embeddings()
