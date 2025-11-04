"""
법률 관계 추출 모듈

법률 간, 조항 간 관계를 추출하는 기능 제공
"""

from typing import List, Dict, Optional
from collections import defaultdict
import re


class LawRelationExtractor:
    """법률 간 관계 추출 (LAW-LAW)"""

    @staticmethod
    def extract_enforced_by(laws: List[Dict]) -> List[Dict]:
        """
        법률 → 시행령 관계 추출

        Args:
            laws: law_info 딕셔너리 리스트
                [{law_name, law_category, base_law_name, ...}, ...]

        Returns:
            ENFORCED_BY 관계 리스트
                [{type, from_id, to_id, properties}, ...]
        """
        relationships = []

        # base_law_name으로 그룹화
        groups = defaultdict(list)
        for law in laws:
            base_name = law.get('base_law_name') or law['law_name']
            groups[base_name].append(law)

        # 각 그룹에서 법률 → 시행령 관계 찾기
        for base_name, group_laws in groups.items():
            law_node = None
            decree_node = None

            for law in group_laws:
                category = law.get('law_category', law.get('law_type', ''))
                if category == '법률':
                    law_node = law
                elif category == '시행령':
                    decree_node = law

            # 법률과 시행령이 모두 있으면 관계 생성
            if law_node and decree_node:
                relationships.append({
                    'type': 'ENFORCED_BY',
                    'from_id': law_node['law_name'],
                    'to_id': decree_node['law_name'],
                    'properties': {
                        'scope': '전체',
                        'base_law_name': base_name
                    }
                })

        return relationships

    @staticmethod
    def extract_detailed_by(laws: List[Dict]) -> List[Dict]:
        """
        시행령 → 시행규칙 관계 추출

        Args:
            laws: law_info 딕셔너리 리스트

        Returns:
            DETAILED_BY 관계 리스트
        """
        relationships = []

        # base_law_name으로 그룹화
        groups = defaultdict(list)
        for law in laws:
            base_name = law.get('base_law_name') or law['law_name']
            groups[base_name].append(law)

        # 각 그룹에서 시행령 → 시행규칙 관계 찾기
        for base_name, group_laws in groups.items():
            decree_node = None
            rule_node = None

            for law in group_laws:
                category = law.get('law_category', law.get('law_type', ''))
                if category == '시행령':
                    decree_node = law
                elif category == '시행규칙':
                    rule_node = law

            # 시행령과 시행규칙이 모두 있으면 관계 생성
            if decree_node and rule_node:
                relationships.append({
                    'type': 'DETAILED_BY',
                    'from_id': decree_node['law_name'],
                    'to_id': rule_node['law_name'],
                    'properties': {
                        'scope': '전체',
                        'base_law_name': base_name
                    }
                })

        return relationships

    @staticmethod
    def extract_all_law_relationships(laws: List[Dict]) -> List[Dict]:
        """
        모든 법률 간 관계 추출 (ENFORCED_BY + DETAILED_BY)

        Args:
            laws: law_info 딕셔너리 리스트

        Returns:
            모든 관계 리스트
        """
        relationships = []
        relationships.extend(LawRelationExtractor.extract_enforced_by(laws))
        relationships.extend(LawRelationExtractor.extract_detailed_by(laws))
        return relationships


class ArticleRelationExtractor:
    """조항 간 관계 추출 (JO-JO, HANG-HANG 등)"""

    # 위임 패턴 (대통령령, 국토교통부령 등)
    DELEGATION_PATTERNS = [
        r'대통령령으로\s+정한다',
        r'대통령령으로\s+정하는',
        r'대통령령이\s+정하는',
        r'국토교통부령으로\s+정한다',
        r'국토교통부령으로\s+정하는',
        r'총리령으로\s+정한다',
        r'부령으로\s+정한다',
        r'조례로\s+정한다',
    ]

    # 인용 패턴 ("「○○법」제○조")
    REFERENCE_PATTERN = r'「([^」]+)」\s*제(\d+)조'

    @staticmethod
    def extract_delegations(content: str, full_id: str) -> List[Dict]:
        """
        조항 내용에서 위임 패턴 추출

        Args:
            content: 조항 내용
            full_id: 조항 ID (예: "국토계획법::제5조")

        Returns:
            위임 정보 리스트
                [{delegation_type, pattern_found, context}, ...]
        """
        delegations = []

        for pattern in ArticleRelationExtractor.DELEGATION_PATTERNS:
            matches = re.finditer(pattern, content)
            for match in matches:
                # 위임 타입 추출
                delegation_type = None
                if '대통령령' in match.group():
                    delegation_type = '시행령'
                elif '부령' in match.group() or '령으로' in match.group():
                    delegation_type = '시행규칙'
                elif '조례' in match.group():
                    delegation_type = '조례'

                # 주변 문맥 추출 (매칭 전후 50자)
                start = max(0, match.start() - 50)
                end = min(len(content), match.end() + 50)
                context = content[start:end]

                delegations.append({
                    'from_id': full_id,
                    'delegation_type': delegation_type,
                    'pattern_found': match.group(),
                    'context': context.strip()
                })

        return delegations

    @staticmethod
    def extract_references(content: str, full_id: str) -> List[Dict]:
        """
        조항 내용에서 법률 인용 패턴 추출

        Args:
            content: 조항 내용
            full_id: 조항 ID

        Returns:
            인용 정보 리스트
                [{referenced_law, referenced_article, context}, ...]
        """
        references = []

        matches = re.finditer(ArticleRelationExtractor.REFERENCE_PATTERN, content)
        for match in matches:
            law_name = match.group(1)
            article_num = match.group(2)

            # 주변 문맥 추출
            start = max(0, match.start() - 30)
            end = min(len(content), match.end() + 30)
            context = content[start:end]

            references.append({
                'from_id': full_id,
                'referenced_law': law_name,
                'referenced_article': f"제{article_num}조",
                'pattern_found': match.group(),
                'context': context.strip()
            })

        return references


# 헬퍼 함수
def extract_law_relationships_from_jsons(json_files: List[str]) -> List[Dict]:
    """
    여러 JSON 파일에서 법률 간 관계 추출

    Args:
        json_files: JSON 파일 경로 리스트

    Returns:
        관계 리스트
    """
    import json

    laws = []
    for json_file in json_files:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            laws.append(data['law_info'])

    return LawRelationExtractor.extract_all_law_relationships(laws)
