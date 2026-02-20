"""
한국 법령 Neo4j 전처리 모듈

법령 텍스트를 파싱하여 Neo4j 그래프 DB에 적합한 형태로 변환
계층 구조: 법률 > 편 > 장 > 절 > 관 > 조 > 항 > 호 > 목
"""

import re
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import json
from datetime import datetime


class UnitType(Enum):
    """법률 단위 타입 (계층 구조 순서)"""
    LAW = "법률"
    PYEON = "편"
    JANG = "장"
    JEOL = "절"
    GWAN = "관"
    JO = "조"
    HANG = "항"
    HO = "호"
    MOK = "목"
    SEMOK = "세목"  # 1), 가), (1), (가) 등


@dataclass
class LegalUnit:
    """법률 단위 데이터 클래스"""
    unit_type: UnitType
    unit_number: str
    title: Optional[str]
    content: str
    unit_path: str
    full_id: str
    parent_id: Optional[str]
    revision_dates: List[str] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)
    order: int = 0  # 같은 레벨 내 순서


class EnhancedKoreanLawParser:
    """한국 법규 파싱 클래스 (편/장/절/관 지원)"""

    def __init__(self, law_name: str = "", law_type: str = "법률"):
        self.law_name = law_name
        self.law_type = law_type
        self.units: List[LegalUnit] = []

        # 현재 컨텍스트 추적
        self.current_pyeon = None
        self.current_jang = None
        self.current_jeol = None
        self.current_gwan = None
        self.current_jo = None
        self.current_hang = None
        self.current_ho = None

        # 순서 카운터
        self.order_counters = {
            UnitType.PYEON: 0,
            UnitType.JANG: 0,
            UnitType.JEOL: 0,
            UnitType.GWAN: 0,
            UnitType.JO: 0,
            UnitType.HANG: 0,
            UnitType.HO: 0,
            UnitType.MOK: 0,
        }

        # 중복 방지용 ID 세트
        self.seen_ids = set()

        # 정규식 패턴
        self.patterns = {
            # 편: 제1편, 제2편 등
            'pyeon': re.compile(r'^제(\d+)편\s*(.*)'),

            # 장: 제1장, 제2장 등 (제목 포함 가능)
            'jang': re.compile(r'^제(\d+)장\s*(.*)'),

            # 절: 제1절, 제2절 등
            'jeol': re.compile(r'^제(\d+)절\s*(.*)'),

            # 관: 제1관, 제2관 등
            'gwan': re.compile(r'^제(\d+)관\s*(.*)'),

            # 조: 제3조(적용 제외), 제44조의2(특례) 등
            'jo': re.compile(r'제(\d+조(?:의\d+)?)\s*(?:\(([^)]+)\))?'),

            # 항: ①, ②, ③... (원문자) 또는 제1항, 제2항
            'hang': re.compile(r'([①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳])|^제(\d+)항'),

            # 호: 1., 2., 3... (숫자 + 온점)
            'ho': re.compile(r'^(\d+)\.\s*(.*)'),

            # 목: 가., 나., 다... (한글 + 온점)
            'mok': re.compile(r'^([가나다라마바사아자차카타파하])\.\s*(.*)'),

            # 세목: 1), 가), (1), (가) 등
            'semok_1': re.compile(r'^(\d+)\)\s*(.*)'),      # 1) 형식
            'semok_2': re.compile(r'^([가나다라])\)\s*(.*)'),  # 가) 형식
            'semok_3': re.compile(r'^\((\d+)\)\s*(.*)'),    # (1) 형식
            'semok_4': re.compile(r'^\(([가나다라])\)\s*(.*)'),  # (가) 형식

            # 개정 이력: <개정 2016. 1. 19.>, <신설 2019. 11. 26.>
            'revision': re.compile(r'<([^>]+)>'),

            # 법률 인용: 「문화유산의 보존 및 활용에 관한 법률」
            'law_reference': re.compile(r'「([^」]+)」'),

            # 조항 참조: 제○조, 제○항, 제○호 등
            'jo_reference': re.compile(r'제(\d+조(?:의\d+)?)'),
            'hang_reference': re.compile(r'제(\d+)항'),
            'ho_reference': re.compile(r'제(\d+)호'),
        }

    def parse(self, text: str) -> List[LegalUnit]:
        """법률 텍스트 파싱 (편/장/절/관 지원)"""
        self.units = []
        lines = text.split('\n')

        i = 0
        while i < len(lines):
            line = lines[i].strip()

            # 빈 줄 건너뛰기
            if not line:
                i += 1
                continue

            # 편 처리
            if self._try_parse_pyeon(line, i):
                i += 1
                continue

            # 장 처리
            if self._try_parse_jang(line, i):
                i += 1
                continue

            # 절 처리
            if self._try_parse_jeol(line, i):
                i += 1
                continue

            # 관 처리
            if self._try_parse_gwan(line, i):
                i += 1
                continue

            # 조 처리
            jo_match = self.patterns['jo'].search(line)
            if jo_match:
                self._parse_jo(line, jo_match, i)

                # 같은 줄에 항이 있는지 확인
                remaining_text = line[jo_match.end():].strip()
                if remaining_text:
                    hang_match = self.patterns['hang'].search(remaining_text)
                    if hang_match:
                        self._parse_hang_inline(remaining_text, hang_match, i)

                i += 1
                continue

            # 항 처리 (독립된 줄)
            hang_match = self.patterns['hang'].match(line)
            if hang_match and self.current_jo:
                hang_content = line[hang_match.end():].strip()
                self._parse_hang(line, hang_match, hang_content, i)
                i += 1
                continue

            # 호 처리
            ho_match = self.patterns['ho'].match(line)
            if ho_match and self.current_hang:
                self._parse_ho(line, ho_match, i)
                i += 1
                continue

            # 목 처리
            mok_match = self.patterns['mok'].match(line)
            if mok_match and self.current_ho:
                self._parse_mok(line, mok_match, i)
                i += 1
                continue

            # 어떤 패턴도 매치되지 않으면 이전 단위의 내용에 추가
            if self.units and not self._is_new_structure(line):
                self.units[-1].content += " " + line

            i += 1

        return self.units

    def _try_parse_pyeon(self, line: str, line_num: int) -> bool:
        """편 파싱 시도"""
        match = self.patterns['pyeon'].match(line)
        if not match:
            return False

        number = match.group(1)
        title = match.group(2).strip() if match.group(2) else None

        unit_path = f"제{number}편"
        full_id = f"{self.law_name}::제{number}편" if self.law_name else f"제{number}편"

        # 중복 체크
        if full_id in self.seen_ids:
            return True

        self.order_counters[UnitType.PYEON] += 1

        pyeon_unit = LegalUnit(
            unit_type=UnitType.PYEON,
            unit_number=number,
            title=title,
            content=line,
            unit_path=unit_path,
            full_id=full_id,
            parent_id=self.law_name if self.law_name else None,
            order=self.order_counters[UnitType.PYEON],
            metadata={'line_number': line_num}
        )

        self.units.append(pyeon_unit)
        self.seen_ids.add(full_id)
        self.current_pyeon = pyeon_unit
        self.current_jang = None
        self.current_jeol = None
        self.current_gwan = None
        self.current_jo = None

        # 하위 레벨 카운터 초기화
        self.order_counters[UnitType.JANG] = 0

        return True

    def _try_parse_jang(self, line: str, line_num: int) -> bool:
        """장 파싱 시도"""
        match = self.patterns['jang'].match(line)
        if not match:
            return False

        number = match.group(1)
        title = match.group(2).strip() if match.group(2) else None

        # 부모 결정: 현재 편이 있으면 편, 없으면 법률
        parent = self.current_pyeon if self.current_pyeon else None
        parent_id = parent.full_id if parent else self.law_name
        parent_path = parent.unit_path if parent else ""

        unit_path = f"{parent_path}_제{number}장" if parent_path else f"제{number}장"
        full_id = f"{parent_id}::제{number}장" if parent_id else f"제{number}장"

        # 중복 체크
        if full_id in self.seen_ids:
            return True

        self.order_counters[UnitType.JANG] += 1

        jang_unit = LegalUnit(
            unit_type=UnitType.JANG,
            unit_number=number,
            title=title,
            content=line,
            unit_path=unit_path,
            full_id=full_id,
            parent_id=parent_id,
            order=self.order_counters[UnitType.JANG],
            metadata={'line_number': line_num}
        )

        self.units.append(jang_unit)
        self.seen_ids.add(full_id)
        self.current_jang = jang_unit
        self.current_jeol = None
        self.current_gwan = None
        self.current_jo = None

        # 하위 레벨 카운터 초기화
        self.order_counters[UnitType.JEOL] = 0
        self.order_counters[UnitType.JO] = 0

        return True

    def _try_parse_jeol(self, line: str, line_num: int) -> bool:
        """절 파싱 시도"""
        match = self.patterns['jeol'].match(line)
        if not match:
            return False

        number = match.group(1)
        title = match.group(2).strip() if match.group(2) else None

        parent = self.current_jang
        if not parent:
            return False

        parent_id = parent.full_id
        parent_path = parent.unit_path

        unit_path = f"{parent_path}_제{number}절"
        full_id = f"{parent_id}::제{number}절"

        # 중복 체크
        if full_id in self.seen_ids:
            return True

        self.order_counters[UnitType.JEOL] += 1

        jeol_unit = LegalUnit(
            unit_type=UnitType.JEOL,
            unit_number=number,
            title=title,
            content=line,
            unit_path=unit_path,
            full_id=full_id,
            parent_id=parent_id,
            order=self.order_counters[UnitType.JEOL],
            metadata={'line_number': line_num}
        )

        self.units.append(jeol_unit)
        self.seen_ids.add(full_id)
        self.current_jeol = jeol_unit
        self.current_gwan = None
        self.current_jo = None

        self.order_counters[UnitType.GWAN] = 0

        return True

    def _try_parse_gwan(self, line: str, line_num: int) -> bool:
        """관 파싱 시도"""
        match = self.patterns['gwan'].match(line)
        if not match:
            return False

        number = match.group(1)
        title = match.group(2).strip() if match.group(2) else None

        parent = self.current_jeol
        if not parent:
            return False

        parent_id = parent.full_id
        parent_path = parent.unit_path

        unit_path = f"{parent_path}_제{number}관"
        full_id = f"{parent_id}::제{number}관"

        # 중복 체크
        if full_id in self.seen_ids:
            return True

        self.order_counters[UnitType.GWAN] += 1

        gwan_unit = LegalUnit(
            unit_type=UnitType.GWAN,
            unit_number=number,
            title=title,
            content=line,
            unit_path=unit_path,
            full_id=full_id,
            parent_id=parent_id,
            order=self.order_counters[UnitType.GWAN],
            metadata={'line_number': line_num}
        )

        self.units.append(gwan_unit)
        self.seen_ids.add(full_id)
        self.current_gwan = gwan_unit
        self.current_jo = None

        return True

    def _parse_jo(self, line: str, match, line_num: int):
        """조 파싱"""
        jo_number = match.group(1)
        jo_title = match.group(2) if match.lastindex >= 2 else None

        # 부모 결정: 관 > 절 > 장 > 편 > 법률 순서
        parent = (self.current_gwan or self.current_jeol or
                 self.current_jang or self.current_pyeon)
        parent_id = parent.full_id if parent else self.law_name
        parent_path = parent.unit_path if parent else ""

        jo_content = f"제{jo_number}"
        if jo_title:
            jo_content += f"({jo_title})"

        unit_path = f"{parent_path}_제{jo_number}" if parent_path else f"제{jo_number}"
        full_id = f"{parent_id}::제{jo_number}" if parent_id else f"제{jo_number}"

        # 중복 체크: 이미 파싱한 조는 건너뛰기
        if full_id in self.seen_ids:
            return

        self.order_counters[UnitType.JO] += 1

        # 개정 이력 추출
        revisions = self._extract_revisions(line)

        jo_unit = LegalUnit(
            unit_type=UnitType.JO,
            unit_number=jo_number,
            title=jo_title,
            content=jo_content,
            unit_path=unit_path,
            full_id=full_id,
            parent_id=parent_id,
            revision_dates=revisions,
            order=self.order_counters[UnitType.JO],
            metadata={'line_number': line_num}
        )

        self.units.append(jo_unit)
        self.seen_ids.add(full_id)
        self.current_jo = jo_unit
        self.current_hang = None
        self.current_ho = None

        # 하위 카운터 초기화
        self.order_counters[UnitType.HANG] = 0

    def _parse_hang(self, line: str, match, content: str, line_num: int):
        """항 파싱"""
        hang_number = match.group(1) or match.group(2)

        # 개정 이력 추출 및 제거
        revisions = self._extract_revisions(content)
        content = self.patterns['revision'].sub('', content).strip()

        unit_path = f"{self.current_jo.unit_path}_{hang_number}"
        full_id = f"{self.current_jo.full_id}::{hang_number}"

        # 중복 체크
        if full_id in self.seen_ids:
            return

        self.order_counters[UnitType.HANG] += 1

        hang_unit = LegalUnit(
            unit_type=UnitType.HANG,
            unit_number=hang_number,
            title=None,
            content=content,
            unit_path=unit_path,
            full_id=full_id,
            parent_id=self.current_jo.full_id,
            revision_dates=revisions,
            order=self.order_counters[UnitType.HANG],
            metadata={'line_number': line_num}
        )

        self.units.append(hang_unit)
        self.seen_ids.add(full_id)
        self.current_hang = hang_unit
        self.current_ho = None

        self.order_counters[UnitType.HO] = 0

    def _parse_hang_inline(self, text: str, match, line_num: int):
        """같은 줄에 있는 항 파싱"""
        hang_number = match.group(1) or match.group(2)
        hang_content = text[match.end():].strip()

        self._parse_hang(text, match, hang_content, line_num)

    def _parse_ho(self, line: str, match, line_num: int):
        """호 파싱"""
        ho_number = match.group(1)
        ho_content = match.group(2)

        unit_path = f"{self.current_hang.unit_path}_제{ho_number}호"
        full_id = f"{self.current_hang.full_id}::제{ho_number}호"

        # 중복 체크
        if full_id in self.seen_ids:
            return

        self.order_counters[UnitType.HO] += 1

        # 인용 법률 추출
        referenced_laws = self._extract_law_references(ho_content)

        ho_unit = LegalUnit(
            unit_type=UnitType.HO,
            unit_number=ho_number,
            title=None,
            content=ho_content,
            unit_path=unit_path,
            full_id=full_id,
            parent_id=self.current_hang.full_id,
            order=self.order_counters[UnitType.HO],
            metadata={
                'line_number': line_num,
                'referenced_laws': referenced_laws
            }
        )

        self.units.append(ho_unit)
        self.seen_ids.add(full_id)
        self.current_ho = ho_unit

        self.order_counters[UnitType.MOK] = 0

    def _parse_mok(self, line: str, match, line_num: int):
        """목 파싱"""
        mok_char = match.group(1)
        mok_content = match.group(2)

        unit_path = f"{self.current_ho.unit_path}_{mok_char}목"
        full_id = f"{self.current_ho.full_id}::{mok_char}목"

        # 중복 체크
        if full_id in self.seen_ids:
            return

        self.order_counters[UnitType.MOK] += 1

        mok_unit = LegalUnit(
            unit_type=UnitType.MOK,
            unit_number=mok_char,
            title=None,
            content=mok_content,
            unit_path=unit_path,
            full_id=full_id,
            parent_id=self.current_ho.full_id,
            order=self.order_counters[UnitType.MOK],
            metadata={'line_number': line_num}
        )

        self.units.append(mok_unit)
        self.seen_ids.add(full_id)

    def _is_new_structure(self, line: str) -> bool:
        """새로운 구조 요소인지 확인"""
        return (self.patterns['pyeon'].match(line) is not None or
                self.patterns['jang'].match(line) is not None or
                self.patterns['jeol'].match(line) is not None or
                self.patterns['gwan'].match(line) is not None or
                self.patterns['jo'].search(line) is not None or
                self.patterns['hang'].match(line) is not None or
                self.patterns['ho'].match(line) is not None or
                self.patterns['mok'].match(line) is not None)

    def _extract_revisions(self, text: str) -> List[str]:
        """개정 이력 추출"""
        matches = self.patterns['revision'].findall(text)
        revisions = []
        for match in matches:
            if any(keyword in match for keyword in ['개정', '신설', '삭제']):
                dates = re.findall(r'\d{4}\.\s*\d{1,2}\.\s*\d{1,2}\.?', match)
                revisions.extend(dates)
        return revisions

    def _extract_law_references(self, text: str) -> List[str]:
        """인용 법률 추출"""
        return self.patterns['law_reference'].findall(text)

    def to_neo4j_nodes(self) -> List[Dict]:
        """Neo4j 노드 형식으로 변환"""
        nodes = []

        for unit in self.units:
            node = {
                'labels': [unit.unit_type.name],  # 노드 레이블
                'properties': {
                    'number': unit.unit_number,
                    'title': unit.title,
                    'content': unit.content,
                    'full_id': unit.full_id,
                    'path': unit.unit_path,
                    'order': unit.order,
                }
            }

            # 개정일자가 있으면 추가
            if unit.revision_dates:
                node['properties']['revision_dates'] = unit.revision_dates

            # 메타데이터 추가
            if unit.metadata:
                node['properties']['metadata'] = json.dumps(unit.metadata, ensure_ascii=False)

            nodes.append(node)

        return nodes

    def to_neo4j_relationships(self) -> List[Dict]:
        """Neo4j 관계 형식으로 변환"""
        relationships = []

        for unit in self.units:
            if unit.parent_id:
                # CONTAINS 관계
                relationships.append({
                    'type': 'CONTAINS',
                    'from_id': unit.parent_id,
                    'to_id': unit.full_id,
                    'properties': {
                        'order': unit.order
                    }
                })

            # 법률 인용 관계 (CITES)
            referenced_laws = unit.metadata.get('referenced_laws', [])
            for ref_law in referenced_laws:
                relationships.append({
                    'type': 'CITES',
                    'from_id': unit.full_id,
                    'to_id': ref_law,
                    'properties': {
                        'citation_text': ref_law
                    }
                })

            # 조항 참조 관계 (REFERENCES)
            jo_refs = self.patterns['jo_reference'].findall(unit.content)
            for ref in jo_refs:
                if ref != unit.unit_number:  # 자기 참조 제외
                    law_prefix = unit.full_id.split('::')[0]
                    relationships.append({
                        'type': 'REFERENCES',
                        'from_id': unit.full_id,
                        'to_id': f"{law_prefix}::제{ref}",
                        'properties': {
                            'reference_type': 'article'
                        }
                    })

        # NEXT 관계 생성 (같은 레벨의 순서)
        units_by_type = {}
        for unit in self.units:
            key = (unit.unit_type, unit.parent_id)
            if key not in units_by_type:
                units_by_type[key] = []
            units_by_type[key].append(unit)

        for units_list in units_by_type.values():
            sorted_units = sorted(units_list, key=lambda x: x.order)
            for i in range(len(sorted_units) - 1):
                relationships.append({
                    'type': 'NEXT',
                    'from_id': sorted_units[i].full_id,
                    'to_id': sorted_units[i+1].full_id,
                    'properties': {}
                })

        return relationships

    def print_tree(self):
        """파싱 결과를 트리 형태로 출력"""
        print("\n" + "=" * 80)
        print(f"{self.law_name} 파싱 결과 트리")
        print("=" * 80)

        indent_map = {
            UnitType.LAW: "",
            UnitType.PYEON: "  ",
            UnitType.JANG: "    ",
            UnitType.JEOL: "      ",
            UnitType.GWAN: "        ",
            UnitType.JO: "          ",
            UnitType.HANG: "            ",
            UnitType.HO: "              ",
            UnitType.MOK: "                ",
        }

        for unit in self.units:
            indent = indent_map.get(unit.unit_type, "")
            title = f" ({unit.title})" if unit.title else ""
            content_preview = unit.content[:40] + "..." if len(unit.content) > 40 else unit.content

            print(f"{indent}[{unit.unit_type.value}] {unit.unit_number}{title}")
            if unit.revision_dates:
                print(f"{indent}  개정: {', '.join(unit.revision_dates)}")


# 사용 예시
if __name__ == "__main__":
    sample_text = """
제1편 총칙

제1장 목적 및 정의

제1조(목적) 이 법은 건축물의 대지·구조·설비 기준 및 용도를 정하여 건축물의 안전·기능·환경 및 미관을 향상시킴으로써 공공복리의 증진에 이바지하는 것을 목적으로 한다.

제2장 적용 범위

제3조(적용 제외) ① 다음 각 호의 어느 하나에 해당하는 건축물에는 이 법을 적용하지 아니한다. <개정 2016. 1. 19., 2019. 11. 26.>
1. 「문화유산의 보존 및 활용에 관한 법률」에 따른 지정문화유산이나 임시지정문화유산
2. 철도나 궤도의 선로 부지에 있는 다음 각 목의 시설
가. 운전보안시설
나. 철도 선로의 위나 아래를 가로지르는 보행시설
다. 플랫폼
3. 고속도로 통행료 징수시설
② 「국토의 계획 및 이용에 관한 법률」에 따른 도시지역 외의 지역은 제44조부터 제47조까지를 적용하지 아니한다.
"""

    parser = EnhancedKoreanLawParser(law_name="건축법")
    units = parser.parse(sample_text)

    parser.print_tree()

    print("\n=== Neo4j 노드 ===")
    nodes = parser.to_neo4j_nodes()
    for node in nodes[:5]:
        print(f"{node['labels'][0]}: {node['properties'].get('full_id')}")

    print(f"\n총 {len(nodes)}개 노드, {len(parser.to_neo4j_relationships())}개 관계")

    # JSON 저장
    with open('neo4j_data.json', 'w', encoding='utf-8') as f:
        json.dump({
            'law_name': parser.law_name,
            'nodes': nodes,
            'relationships': parser.to_neo4j_relationships()
        }, f, ensure_ascii=False, indent=2)

    print("neo4j_data.json 저장 완료")
