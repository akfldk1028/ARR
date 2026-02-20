"""
Step 2a: 표준 JSON → Neo4j

표준 법규 JSON을 Neo4j 그래프 데이터베이스에 적재
"""

import json
from pathlib import Path
from typing import Dict, List
import sys

from neo4j_loader import Neo4jLawLoader


def standard_json_to_neo4j_format(data: Dict) -> Dict:
    """
    표준 JSON을 Neo4j 로더가 읽을 수 있는 형식으로 변환

    Args:
        data: 표준 JSON 데이터

    Returns:
        {
            'law_name': str,
            'nodes': List[Dict],
            'relationships': List[Dict]
        }
    """
    law_info = data['law_info']
    units = data['units']

    # 한글 unit_type -> 영문 레이블 매핑
    unit_type_mapping = {
        '법률': 'LAW',
        '편': 'PYEON',
        '장': 'JANG',
        '절': 'JEOL',
        '관': 'GWAN',
        '조': 'JO',
        '항': 'HANG',
        '호': 'HO',
        '목': 'MOK',
        '세목': 'SEMOK'
    }

    # 법률명에 법률 타입을 추가하여 full_id를 고유하게 만듦
    # 예: "국토의 계획 및 이용에 관한 법률" -> "국토의 계획 및 이용에 관한 법률(법률)"
    #     "국토의 계획 및 이용에 관한 법률" -> "국토의 계획 및 이용에 관한 법률(시행령)"
    #     "국토의 계획 및 이용에 관한 법률" -> "국토의 계획 및 이용에 관한 법률(시행규칙)"
    law_name = law_info['law_name']
    law_type = law_info['law_type']
    law_with_type = f"{law_name}({law_type})"

    # 노드 생성
    nodes = []
    for unit in units:
        unit_type_korean = unit['unit_type']
        unit_type_english = unit_type_mapping.get(unit_type_korean, unit_type_korean.upper())

        # full_id에 법률 타입 추가
        # 예: "국토법::제1장::제1조" -> "국토법(법률)::제1장::제1조"
        original_full_id = unit['full_id']
        new_full_id = original_full_id.replace(law_name, law_with_type, 1)

        # unit_path에도 법률 타입 추가
        original_unit_path = unit['unit_path']
        new_unit_path = original_unit_path.replace(law_name, law_with_type, 1)

        node = {
            'labels': [unit_type_english],  # JO, HANG, HO, MOK 등
            'properties': {
                'law_name': law_info['law_name'],  # 제약조건 만족
                'number': unit['unit_number'],
                'title': unit['title'],
                'content': unit['content'],
                'full_id': new_full_id,  # 법률 타입이 포함된 full_id
                'unit_path': new_unit_path,  # 법률 타입이 포함된 unit_path
                'order': unit['order']
            }
        }

        # 개정일자가 있으면 추가
        if unit['revision_dates']:
            node['properties']['revision_dates'] = unit['revision_dates']

        # 메타데이터 추가
        if unit['metadata']:
            node['properties']['metadata'] = json.dumps(unit['metadata'], ensure_ascii=False)

        nodes.append(node)

    # 관계 생성
    relationships = []

    # LAW 노드의 full_id (법률 타입 포함)
    # LAW 노드는 "국토법(법률)" 형식이므로 law_with_type만 사용
    law_full_id = law_with_type

    # 1. CONTAINS 관계 (부모-자식)
    for unit in units:
        original_parent_id = unit['parent_id']

        # parent_id에도 법률 타입 추가
        if original_parent_id == law_name:
            # parent_id가 법률명과 같으면 LAW full_id로 변환
            new_parent_id = law_full_id
        elif original_parent_id:
            # parent_id에 법률 타입 추가
            new_parent_id = original_parent_id.replace(law_name, law_with_type, 1)
        else:
            new_parent_id = None

        # full_id에도 법률 타입 추가
        original_full_id = unit['full_id']
        new_full_id = original_full_id.replace(law_name, law_with_type, 1)

        if new_parent_id:
            # 부모가 있으면 부모와 연결
            relationships.append({
                'type': 'CONTAINS',
                'from_id': new_parent_id,
                'to_id': new_full_id,
                'properties': {
                    'order': unit['order']
                }
            })
        else:
            # 부모가 없으면 LAW 노드와 연결 (최상위 노드)
            relationships.append({
                'type': 'CONTAINS',
                'from_id': law_full_id,
                'to_id': new_full_id,
                'properties': {
                    'order': unit['order']
                }
            })

    # 2. NEXT 관계 (같은 레벨의 순서)
    # parent_id와 unit_type이 같은 것들끼리 그룹화
    units_by_parent_and_type = {}
    for unit in units:
        key = (unit['parent_id'], unit['unit_type'])
        if key not in units_by_parent_and_type:
            units_by_parent_and_type[key] = []
        units_by_parent_and_type[key].append(unit)

    # 각 그룹에서 order 순서대로 NEXT 관계 생성
    for units_group in units_by_parent_and_type.values():
        sorted_units = sorted(units_group, key=lambda x: x['order'])
        for i in range(len(sorted_units) - 1):
            # full_id에 법률 타입 추가
            from_full_id = sorted_units[i]['full_id'].replace(law_name, law_with_type, 1)
            to_full_id = sorted_units[i+1]['full_id'].replace(law_name, law_with_type, 1)

            relationships.append({
                'type': 'NEXT',
                'from_id': from_full_id,
                'to_id': to_full_id,
                'properties': {}
            })

    # 3. CITES 관계 (타법 인용)
    for unit in units:
        referenced_laws = unit['metadata'].get('referenced_laws', [])
        for ref_law in referenced_laws:
            # full_id에 법률 타입 추가
            from_full_id = unit['full_id'].replace(law_name, law_with_type, 1)

            relationships.append({
                'type': 'CITES',
                'from_id': from_full_id,
                'to_id': ref_law,
                'properties': {
                    'citation_text': ref_law
                }
            })

    return {
        'law_name': law_info['law_name'],
        'law_type': law_info['law_type'],
        'nodes': nodes,
        'relationships': relationships
    }


def json_to_neo4j(json_path: str, neo4j_uri: str, neo4j_user: str, neo4j_password: str,
                  output_dir: str = "neo4j") -> str:
    """
    표준 JSON을 Neo4j에 적재

    Args:
        json_path: 표준 JSON 파일 경로
        neo4j_uri: Neo4j 연결 URI
        neo4j_user: Neo4j 사용자명
        neo4j_password: Neo4j 비밀번호
        output_dir: 백업 JSON 저장 디렉토리

    Returns:
        생성된 백업 JSON 파일 경로
    """
    json_path = Path(json_path)
    output_dir = Path(output_dir)

    # 출력 디렉토리 생성
    output_dir.mkdir(exist_ok=True)

    print(f"\n{'='*80}")
    print(f"Step 2a: 표준 JSON → Neo4j")
    print(f"{'='*80}")

    # 1. JSON 읽기
    print(f"\n[1/4] JSON 읽기 중...")
    with open(json_path, 'r', encoding='utf-8') as f:
        standard_json = json.load(f)

    law_info = standard_json['law_info']
    print(f"✅ {law_info['law_name']} ({law_info['law_type']})")
    print(f"   법령 단위: {law_info['total_units']}개")

    # 2. Neo4j 형식으로 변환
    print(f"\n[2/4] Neo4j 형식으로 변환 중...")
    neo4j_data = standard_json_to_neo4j_format(standard_json)

    print(f"✅ 변환 완료")
    print(f"   노드: {len(neo4j_data['nodes'])}개")
    print(f"   관계: {len(neo4j_data['relationships'])}개")

    # 3. Neo4j에 적재
    print(f"\n[3/4] Neo4j에 적재 중...")
    print(f"   URI: {neo4j_uri}")

    try:
        with Neo4jLawLoader(neo4j_uri, neo4j_user, neo4j_password) as loader:
            # 제약조건 및 인덱스 생성
            loader.create_constraints_and_indexes()

            # 법률 노드 생성
            loader.create_law_node(
                law_name=neo4j_data['law_name'],
                law_type=neo4j_data['law_type']
            )

            # 노드 및 관계 생성
            loader.create_nodes_batch(neo4j_data['nodes'])
            loader.create_relationships_batch(neo4j_data['relationships'])

            print(f"✅ Neo4j 적재 완료")

            # 데이터 검증
            print(f"\n데이터 검증 중...")
            loader.verify_data(neo4j_data['law_name'])

    except Exception as e:
        print(f"❌ Neo4j 적재 실패: {e}")
        print(f"\n⚠️  Neo4j가 실행 중인지 확인하세요:")
        print(f"   docker ps | grep neo4j")
        raise

    # 4. 백업 JSON 저장
    print(f"\n[4/4] 백업 JSON 저장 중...")

    safe_law_name = law_info['law_name'].replace(" ", "_")
    backup_filename = f"{safe_law_name}_neo4j.json"
    backup_path = output_dir / backup_filename

    with open(backup_path, 'w', encoding='utf-8') as f:
        json.dump(neo4j_data, f, ensure_ascii=False, indent=2)

    file_size = backup_path.stat().st_size / 1024  # KB

    print(f"✅ 백업 저장: {backup_path}")
    print(f"   파일 크기: {file_size:.1f} KB")

    print(f"\n{'='*80}")
    print(f"✅ Step 2a 완료!")
    print(f"{'='*80}")

    return str(backup_path)


def process_multiple_jsons(json_dir: str = "parsed", neo4j_uri: str = "bolt://localhost:7687",
                           neo4j_user: str = "neo4j", neo4j_password: str = "password",
                           output_dir: str = "neo4j", pattern: str = "*.json"):
    """
    여러 JSON을 일괄 처리

    Args:
        json_dir: JSON 디렉토리
        neo4j_uri: Neo4j URI
        neo4j_user: Neo4j 사용자명
        neo4j_password: Neo4j 비밀번호
        output_dir: 백업 저장 디렉토리
        pattern: 파일 패턴
    """
    json_dir = Path(json_dir)

    if not json_dir.exists():
        print(f"❌ 디렉토리를 찾을 수 없습니다: {json_dir}")
        return

    json_files = list(json_dir.glob(pattern))

    if not json_files:
        print(f"⚠️  {json_dir}에서 '{pattern}' 패턴의 JSON을 찾을 수 없습니다")
        return

    print(f"\n{'='*80}")
    print(f"일괄 처리: {len(json_files)}개 JSON 파일")
    print(f"{'='*80}")

    results = []
    errors = []

    for i, json_file in enumerate(sorted(json_files), 1):
        print(f"\n[{i}/{len(json_files)}] {json_file.name}")

        try:
            output_path = json_to_neo4j(
                str(json_file),
                neo4j_uri,
                neo4j_user,
                neo4j_password,
                output_dir
            )
            results.append(output_path)
        except Exception as e:
            print(f"❌ 실패: {e}")
            errors.append((json_file.name, str(e)))

    # 최종 요약
    print(f"\n{'='*80}")
    print(f"일괄 처리 완료")
    print(f"{'='*80}")
    print(f"성공: {len(results)}개")
    print(f"실패: {len(errors)}개")

    if errors:
        print(f"\n실패한 파일:")
        for filename, error in errors:
            print(f"  - {filename}: {error}")


# 사용 예시
if __name__ == "__main__":
    import argparse
    import os
    from dotenv import load_dotenv

    # UTF-8 출력 설정
    sys.stdout.reconfigure(encoding='utf-8')

    # 환경 변수 로드
    load_dotenv()

    parser = argparse.ArgumentParser(description="표준 JSON을 Neo4j에 적재")
    parser.add_argument("--json", type=str, help="변환할 JSON 파일 경로")
    parser.add_argument("--dir", type=str, default="parsed", help="JSON 디렉토리 (기본: parsed)")
    parser.add_argument("--output", type=str, default="neo4j", help="백업 디렉토리 (기본: neo4j)")
    parser.add_argument("--uri", type=str, default=os.getenv("NEO4J_URI", "bolt://localhost:7687"), help="Neo4j URI")
    parser.add_argument("--user", type=str, default=os.getenv("NEO4J_USER", "neo4j"), help="Neo4j 사용자명")
    parser.add_argument("--password", type=str, default=os.getenv("NEO4J_PASSWORD", "password"), help="Neo4j 비밀번호")
    parser.add_argument("--all", action="store_true", help="디렉토리 내 모든 JSON 처리")

    args = parser.parse_args()

    try:
        if args.json:
            # 단일 파일 처리
            json_to_neo4j(args.json, args.uri, args.user, args.password, args.output)
        elif args.all:
            # 전체 디렉토리 처리
            process_multiple_jsons(args.dir, args.uri, args.user, args.password, args.output)
        else:
            print(f"사용법:")
            print(f"  단일 파일: python json_to_neo4j.py --json <파일경로>")
            print(f"  전체 처리: python json_to_neo4j.py --all")
            print(f"\n환경 변수 (.env):")
            print(f"  NEO4J_URI={args.uri}")
            print(f"  NEO4J_USER={args.user}")
            print(f"  NEO4J_PASSWORD=***")

    except KeyboardInterrupt:
        print("\n\n중단되었습니다.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        sys.exit(1)
