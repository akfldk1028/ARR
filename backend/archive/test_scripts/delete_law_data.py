"""
Neo4j에서 국토계획법 데이터 삭제
"""
import sys
from neo4j import GraphDatabase

sys.stdout.reconfigure(encoding='utf-8')

# Neo4j 연결
uri = "neo4j://127.0.0.1:7687"
user = "neo4j"
password = "11111111"

driver = GraphDatabase.driver(uri, auth=(user, password))

def delete_law_data():
    """국토계획법 데이터 삭제"""

    print("=" * 80)
    print("Neo4j 데이터 삭제")
    print("=" * 80)

    with driver.session() as session:
        # 1. 삭제 전 확인
        count_query = """
        MATCH (n)
        WHERE n.full_id CONTAINS '국토의 계획 및 이용에 관한 법률'
        RETURN count(n) as count
        """
        result = session.run(count_query)
        count = result.single()['count']

        print(f"\n삭제할 노드: {count}개")

        if count == 0:
            print("삭제할 데이터가 없습니다.")
            return

        # 2. 삭제 실행
        delete_query = """
        MATCH (n)
        WHERE n.full_id CONTAINS '국토의 계획 및 이용에 관한 법률'
        DETACH DELETE n
        RETURN count(n) as deleted
        """

        print("\n삭제 중...")
        result = session.run(delete_query)
        deleted = result.single()['deleted']

        print(f"✅ 삭제 완료: {deleted}개")

        # 3. 검증
        verify_query = """
        MATCH (n)
        WHERE n.full_id CONTAINS '국토의 계획 및 이용에 관한 법률'
        RETURN count(n) as remaining
        """
        result = session.run(verify_query)
        remaining = result.single()['remaining']

        if remaining == 0:
            print("✅ 모든 데이터가 삭제되었습니다.")
        else:
            print(f"⚠️ 남은 노드: {remaining}개")

if __name__ == "__main__":
    try:
        delete_law_data()
        driver.close()
        print("\n다음 단계:")
        print("python law/scripts/json_to_neo4j.py --input law/data/parsed/국토의_계획_및_이용에_관한_법률_법률_corrected_dedup.json")
    except Exception as e:
        print(f"\n❌ 오류: {e}")
        import traceback
        traceback.print_exc()
        driver.close()
        sys.exit(1)
