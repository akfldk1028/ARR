"""
데이터 형식 변환 모듈
"""
from typing import List, Dict, Any
from datetime import datetime


def generate_agent_id(base_law_name: str) -> str:
    """
    base_law_name으로부터 agent_id 생성

    Args:
        base_law_name: 모법 이름 (예: "국토계획법")

    Returns:
        agent_id (예: "agent_국토계획법")
    """
    return f"agent_{base_law_name}"


def generate_agent_scope(base_law_name: str) -> List[str]:
    """
    base_law_name으로부터 agent_scope 생성

    Agent가 담당하는 법률 체계 전체 (법률 + 시행령 + 시행규칙)

    Args:
        base_law_name: 모법 이름 (예: "국토계획법")

    Returns:
        agent_scope 리스트 (예: ["국토계획법", "국토계획법 시행령", "국토계획법 시행규칙"])
    """
    return [
        base_law_name,
        f"{base_law_name} 시행령",
        f"{base_law_name} 시행규칙"
    ]


def units_to_standard_json(law_name: str, law_type: str, source_file: str, units: List,
                           law_category: str = None, law_number: str = None,
                           promulgation_date: str = None, enforcement_date: str = None,
                           base_law_name: str = None) -> Dict[str, Any]:
    """
    파싱된 units를 표준 JSON 형식으로 변환

    Args:
        law_name: 법률명
        law_type: 법률 유형 ("법률", "시행령", "시행규칙")
        source_file: 원본 파일명
        units: 파싱된 LegalUnit 객체 리스트
        law_category: 법률 카테고리
        law_number: 법령 번호
        promulgation_date: 공포일
        enforcement_date: 시행일
        base_law_name: 모법 이름

    Returns:
        표준 JSON 딕셔너리
    """
    # base_law_name 결정
    final_base_law_name = base_law_name or law_name

    standard_json = {
        "law_info": {
            "law_name": law_name,
            "law_type": law_type,
            "law_category": law_category or law_type,
            "law_number": law_number,
            "promulgation_date": promulgation_date,
            "enforcement_date": enforcement_date,
            "base_law_name": final_base_law_name,
            "agent_id": generate_agent_id(final_base_law_name),
            "agent_scope": generate_agent_scope(final_base_law_name),
            "source_file": source_file,
            "parsed_at": datetime.now().isoformat(),
            "total_units": len(units)
        },
        "units": []
    }

    for unit in units:
        unit_dict = {
            "unit_type": unit.unit_type.value,
            "unit_number": unit.unit_number,
            "title": unit.title,
            "content": unit.content,
            "unit_path": unit.unit_path,
            "full_id": unit.full_id,
            "parent_id": unit.parent_id,
            "order": unit.order,
            "revision_dates": unit.revision_dates,
            "metadata": unit.metadata
        }

        standard_json["units"].append(unit_dict)

    return standard_json


def standard_json_to_neo4j_format(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    표준 JSON을 Neo4j 형식으로 변환

    Args:
        data: 표준 JSON 데이터

    Returns:
        Neo4j 형식 딕셔너리
    """
    law_info = data['law_info']
    units = data['units']

    nodes = []
    relationships = []

    # 법률 루트 노드
    base_law_name = law_info.get('base_law_name', law_info['law_name'])

    law_node = {
        "id": law_info['law_name'],
        "labels": ["LAW"],
        "properties": {
            "full_id": law_info['law_name'],
            "name": law_info['law_name'],
            "law_type": law_info['law_type'],
            "law_category": law_info.get('law_category', law_info['law_type']),
            "law_number": law_info.get('law_number'),
            "promulgation_date": law_info.get('promulgation_date'),
            "enforcement_date": law_info.get('enforcement_date'),
            "base_law_name": base_law_name,
            "agent_id": generate_agent_id(base_law_name),
            "agent_scope": generate_agent_scope(base_law_name),
            "source_file": law_info['source_file'],
            "parsed_at": law_info['parsed_at'],
            "total_units": law_info['total_units']
        }
    }
    nodes.append(law_node)

    # 단위 노드 생성
    agent_id = generate_agent_id(base_law_name)

    for unit in units:
        node = {
            "id": unit['full_id'],
            "labels": [_unit_type_to_node_label(unit['unit_type'])],
            "properties": {
                "full_id": unit['full_id'],
                "law_name": law_info['law_name'],  # 법률명 추가
                "law_type": law_info['law_type'],  # 법률 타입 추가
                "law_category": law_info.get('law_category', law_info['law_type']),  # 법률 카테고리
                "base_law_name": base_law_name,  # 모법 이름
                "agent_id": agent_id,  # Agent ID 추가
                "unit_number": unit['unit_number'],
                "title": unit['title'],
                "content": unit['content'],
                "unit_path": unit['unit_path'],
                "order": unit['order']
            }
        }

        # 메타데이터 추가
        if unit.get('metadata'):
            node["properties"].update(unit['metadata'])

        nodes.append(node)

        # CONTAINS 관계 (부모 → 자식)
        if unit['parent_id']:
            relationships.append({
                "type": "CONTAINS",
                "from_id": unit['parent_id'],
                "to_id": unit['full_id'],
                "properties": {}
            })

    # NEXT 관계 (같은 레벨 순서)
    _add_next_relationships(units, relationships)

    # CITES 관계 (법률 인용)
    _add_citation_relationships(units, relationships)

    return {
        "law_name": law_info['law_name'],
        "nodes": nodes,
        "relationships": relationships
    }


def _unit_type_to_node_label(unit_type: str) -> str:
    """단위 타입을 Neo4j 노드 레이블로 변환"""
    mapping = {
        "편": "PYEON",
        "장": "JANG",
        "절": "JEOL",
        "관": "GWAN",
        "조": "JO",
        "항": "HANG",
        "호": "HO",
        "목": "MOK"
    }
    return mapping.get(unit_type, "UNIT")


def _add_next_relationships(units: List[Dict], relationships: List[Dict]) -> None:
    """같은 레벨에서 순서 관계 추가"""
    # parent_id별로 그룹화
    from collections import defaultdict
    siblings = defaultdict(list)

    for unit in units:
        parent_id = unit['parent_id']
        if parent_id:
            siblings[parent_id].append(unit)

    # 각 그룹 내에서 NEXT 관계 생성
    for parent_id, children in siblings.items():
        # order로 정렬
        sorted_children = sorted(children, key=lambda x: x['order'])

        for i in range(len(sorted_children) - 1):
            relationships.append({
                "type": "NEXT",
                "from_id": sorted_children[i]['full_id'],
                "to_id": sorted_children[i + 1]['full_id'],
                "properties": {}
            })


def _add_citation_relationships(units: List[Dict], relationships: List[Dict]) -> None:
    """법률 인용 관계 추가"""
    for unit in units:
        referenced_laws = unit.get('metadata', {}).get('referenced_laws', [])

        for ref in referenced_laws:
            relationships.append({
                "type": "CITES",
                "from_id": unit['full_id'],
                "to_id": ref,  # 인용된 법률 ID
                "properties": {}
            })
