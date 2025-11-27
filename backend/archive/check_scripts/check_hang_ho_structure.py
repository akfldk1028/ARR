"""
HANG와 HO의 full_id 구조 확인
"""

import os
import sys
import django

# Windows console encoding fix
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Django 설정
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from graph_db.services.neo4j_service import Neo4jService


def check_structure():
    neo4j = Neo4jService()
    neo4j.connect()

    with neo4j.driver.session() as session:
        print("\n" + "="*70)
        print("HANG 샘플 (5개)")
        print("="*70)

        result = session.run("""
            MATCH (h:HANG)
            RETURN h.full_id as full_id, h.number as number
            LIMIT 5
        """)

        for record in result:
            print(f"  full_id: {record['full_id']}")
            print(f"  number:  {record['number']}")
            print()

        print("\n" + "="*70)
        print("HO 샘플 (5개)")
        print("="*70)

        result = session.run("""
            MATCH (ho:HO)
            RETURN ho.full_id as full_id, ho.number as number
            LIMIT 5
        """)

        for record in result:
            print(f"  full_id: {record['full_id']}")
            print(f"  number:  {record['number']}")
            print()

        print("\n" + "="*70)
        print("매칭 시도")
        print("="*70)

        # HO의 부모 HANG 찾기 시도
        result = session.run("""
            MATCH (ho:HO)
            WITH ho, split(ho.full_id, '::') as parts
            WITH ho, parts[0..3] as hang_parts
            WITH ho, reduce(s = '', x IN hang_parts | s + '::' + x) as reconstructed
            WITH ho, substring(reconstructed, 2) as hang_full_id
            RETURN ho.full_id as ho_id,
                   hang_full_id as expected_hang_id
            LIMIT 5
        """)

        for record in result:
            print(f"  HO:           {record['ho_id']}")
            print(f"  Expected HANG: {record['expected_hang_id']}")

            # 실제로 HANG이 존재하는지 확인
            check = session.run("""
                MATCH (h:HANG {full_id: $hang_id})
                RETURN count(h) as exists
            """, hang_id=record['expected_hang_id'])

            exists = check.single()['exists']
            print(f"  Exists: {'Yes ✅' if exists else 'No ❌'}")
            print()


if __name__ == "__main__":
    check_structure()
