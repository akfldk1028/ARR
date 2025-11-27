"""
전체 법규의 임베딩 상태 확인
"""
import sys
import io
import os

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
import django
django.setup()

from graph_db.services.neo4j_service import Neo4jService

neo4j = Neo4jService()
neo4j.connect()

print("=" * 70)
print("전체 법규 임베딩 상태")
print("=" * 70)

with neo4j.driver.session() as session:
    query = """
    MATCH (h:HANG)
    RETURN
        h.law_name as law_name,
        count(h) as total,
        count(CASE WHEN h.embedding IS NOT NULL THEN 1 END) as with_emb,
        avg(CASE WHEN h.embedding IS NOT NULL THEN size(h.embedding) END) as avg_dim
    ORDER BY total DESC
    """

    result = session.run(query)
    records = list(result)

    print(f"\n법규별 임베딩 상태:")
    print(f"{'법규명':<40} {'전체':>8} {'임베딩':>8} {'비율':>8} {'차원':>6}")
    print("=" * 70)

    total_all = 0
    total_with_emb = 0

    for r in records:
        law_name = r['law_name']
        if len(law_name) > 37:
            law_name = law_name[:34] + "..."

        total = r['total']
        with_emb = r['with_emb']
        ratio = (with_emb / total * 100) if total > 0 else 0
        avg_dim = int(r['avg_dim']) if r['avg_dim'] else 0

        total_all += total
        total_with_emb += with_emb

        status = "✅" if ratio == 100 else "❌"

        print(f"{status} {law_name:<38} {total:>8} {with_emb:>8} {ratio:>7.1f}% {avg_dim:>6}")

    print("=" * 70)
    print(f"{'총계':<40} {total_all:>8} {total_with_emb:>8} {(total_with_emb/total_all*100):>7.1f}%")

print("\n" + "=" * 70)
print("결론")
print("=" * 70)

if total_with_emb == total_all:
    print("✅ 모든 HANG에 임베딩이 있습니다!")
    print("✅ 바로 알고리즘 테스트 진행 가능!")
else:
    print(f"❌ {total_all - total_with_emb}개 HANG에 임베딩이 없습니다.")
    print("→ add_embeddings.py 실행 필요!")

print("=" * 70)
