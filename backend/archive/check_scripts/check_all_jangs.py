"""
모든 장 확인
"""
import sys
from neo4j import GraphDatabase

sys.stdout.reconfigure(encoding='utf-8')

# Neo4j 연결
uri = "neo4j://127.0.0.1:7687"
user = "neo4j"
password = "11111111"

driver = GraphDatabase.driver(uri, auth=(user, password))

def check_all_jangs():
    """모든 장 확인"""

    print("=" * 80)
    print("전체 장 구조 확인")
    print("=" * 80)

    with driver.session() as session:
        # 모든 장 조회
        query = """
        MATCH (j:JANG)
        WHERE j.full_id CONTAINS '국토의 계획 및 이용에 관한 법률'
        OPTIONAL MATCH (j)-[:CONTAINS]->(jeol:JEOL)
        WITH j, count(DISTINCT jeol) as jeol_count
        ORDER BY j.number
        RETURN j.number as 장번호,
               j.title as 장제목,
               j.full_id as full_id,
               jeol_count as 절개수
        """

        result = session.run(query)

        all_jangs = []
        for record in result:
            all_jangs.append({
                'number': record['장번호'],
                'title': record['장제목'],
                'full_id': record['full_id'],
                'jeol_count': record['절개수']
            })

        print(f"\n총 {len(all_jangs)}개 장 발견\n")

        for jang in all_jangs:
            print(f"제{jang['number']}장: {jang['title']}")
            print(f"  절: {jang['jeol_count']}개")
            print(f"  full_id: {jang['full_id']}")
            print()

        # JSON 파일 확인
        print("=" * 80)
        print("JSON 파일 확인")
        print("=" * 80)

        import json
        with open('law/data/parsed/국토의_계획_및_이용에_관한_법률_법률_corrected_dedup.json', encoding='utf-8') as f:
            data = json.load(f)

        json_jangs = [u for u in data['units'] if u['unit_type'] == '장']

        print(f"\nJSON에 {len(json_jangs)}개 장 있음\n")

        for jang in json_jangs:
            print(f"제{jang['unit_number']}장: {jang['title']}")

        # 비교
        print("\n" + "=" * 80)
        print("비교 결과")
        print("=" * 80)

        if len(all_jangs) != len(json_jangs):
            print(f"❌ 개수 불일치!")
            print(f"   Neo4j: {len(all_jangs)}개")
            print(f"   JSON: {len(json_jangs)}개")
        else:
            print(f"✅ 개수 일치: {len(all_jangs)}개")

if __name__ == "__main__":
    try:
        check_all_jangs()
        driver.close()
    except Exception as e:
        print(f"\n❌ 오류: {e}")
        import traceback
        traceback.print_exc()
        driver.close()
        sys.exit(1)
