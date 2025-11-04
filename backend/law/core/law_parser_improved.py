"""
개선된 한국 법령 파서 - 목차/본문 구분 지원

핵심 개선사항:
1. 목차와 본문을 자동으로 구분
2. 중복 발견 시 컨텍스트 복원 (목차 → 본문 전환)
3. 장/절이 두 번 나타나는 경우 처리
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
    SEMOK = "세목"


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
    order: int = 0
    is_toc: bool = False  # 목차 여부 플래그


class ImprovedKoreanLawParser:
    """개선된 한국 법규 파싱 클래스 - 목차/본문 구분"""

    def __init__(self, law_name: str = "", law_type: str = "법률"):
        self.law_name = law_name
        self.law_type = law_type
        self.units: List[LegalUnit] = []

        # 현재 컨텍스트
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

        # 중복 방지 및 컨텍스트 복원용
        self.seen_ids = set()
        self.id_to_unit = {}  # full_id -> LegalUnit 매핑

        # 정규식 패턴
        self.patterns = {
            'pyeon': re.compile(r'^제(\d+)편\s*(.*)'),
            'jang': re.compile(r'^제(\d+)장\s*(.*)'),
            'jeol': re.compile(r'^제(\d+)절\s*(.*)'),
            'gwan': re.compile(r'^제(\d+)관\s*(.*)'),
            'jo': re.compile(r'제(\d+조(?:의\d+)?)\s*(?:\(([^)]+)\))?'),
            'hang': re.compile(r'([①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳])|^제(\d+)항'),
            'ho': re.compile(r'^(\d+)\.\s*(.*)'),
            'mok': re.compile(r'^([가나다라마바사아자차카타파하])\.\s*(.*)'),
            'revision': re.compile(r'<([^>]+)>'),
            'law_reference': re.compile(r'「([^」]+)」'),
            'jo_reference': re.compile(r'제(\d+조(?:의\d+)?)'),
        }

    def parse(self, text: str) -> List[LegalUnit]:
        """법률 텍스트 파싱 (목차/본문 구분)"""
        self.units = []
        lines = text.split('\n')

        i = 0
        while i < len(lines):
            line = lines[i].strip()

            if not line:
                i += 1
                continue

            # 편 처리
            if self._try_parse_pyeon(line, i):
                i += 1
                continue

            # 장 처리 (개선: 중복 감지)
            if self._try_parse_jang_improved(line, i):
                i += 1
                continue

            # 절 처리 (개선: 중복 감지)
            if self._try_parse_jeol_improved(line, i):
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

            # 항 처리
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

            # 어떤 패턴도 매치되지 않으면 이전 단위에 추가
            if self.units and not self._is_new_structure(line):
                self.units[-1].content += " " + line

            i += 1

        # 후처리: 목차 노드 제거
        self._remove_toc_units()

        return self.units

    def _try_parse_jang_improved(self, line: str, line_num: int) -> bool:
        """장 파싱 (개선: 중복 감지 및 컨텍스트 복원)"""
        match = self.patterns['jang'].match(line)
        if not match:
            return False

        number = match.group(1)
        title = match.group(2).strip() if match.group(2) else None

        # 부모 결정
        parent = self.current_pyeon if self.current_pyeon else None
        parent_id = parent.full_id if parent else self.law_name
        parent_path = parent.unit_path if parent else ""

        unit_path = f"{parent_path}_제{number}장" if parent_path else f"제{number}장"
        full_id = f"{parent_id}::제{number}장" if parent_id else f"제{number}장"

        # 중복 체크: 이미 있으면 이것은 본문 시작
        if full_id in self.seen_ids:
            print(f"[DEBUG] 제{number}장 중복 발견 (본문 시작) at line {line_num}")
            # 이전에 파싱된 장을 찾아서 컨텍스트 복원
            prev_jang = self.id_to_unit.get(full_id)
            if prev_jang:
                self.current_jang = prev_jang
                self.current_jeol = None
                self.current_jo = None
                print(f"[DEBUG] 컨텍스트 복원: current_jang = 제{number}장")
            return True

        # 새로운 장 생성
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
            metadata={'line_number': line_num},
            is_toc=True  # 일단 목차로 표시, 나중에 확인
        )

        self.units.append(jang_unit)
        self.seen_ids.add(full_id)
        self.id_to_unit[full_id] = jang_unit
        self.current_jang = jang_unit
        self.current_jeol = None
        self.current_gwan = None
        self.current_jo = None

        # 하위 레벨 카운터 초기화
        self.order_counters[UnitType.JEOL] = 0
        self.order_counters[UnitType.JO] = 0

        return True

    def _try_parse_jeol_improved(self, line: str, line_num: int) -> bool:
        """절 파싱 (개선: 중복 감지 및 컨텍스트 복원)"""
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

        # 중복 체크: 제목과 번호로 매칭 (full_id가 아닌 제목으로)
        # 이미 같은 번호와 제목의 절이 있으면 본문 시작
        prev_jeol = None
        for unit in self.units:
            if (unit.unit_type == UnitType.JEOL and
                unit.unit_number == number and
                unit.title == title):
                prev_jeol = unit
                break

        if prev_jeol:
            print(f"[DEBUG] 제{number}절 '{title}' 중복 발견 (본문 시작) at line {line_num}")
            # **중요**: 절이 본문으로 나타났다는 것은 부모 장도 본문임
            prev_jeol.is_toc = False

            # 부모 장도 복원하고 is_toc=False로 변경
            if prev_jeol.parent_id in self.id_to_unit:
                self.current_jang = self.id_to_unit[prev_jeol.parent_id]
                self.current_jang.is_toc = False  # 부모 장도 본문
                print(f"[DEBUG] 부모 장 복원: {self.current_jang.full_id} (is_toc=False)")

            self.current_jeol = prev_jeol
            self.current_jo = None
            print(f"[DEBUG] 컨텍스트 복원: current_jeol = 제{number}절")
            return True

        # 새로운 절 생성
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
            metadata={'line_number': line_num},
            is_toc=True  # 일단 목차로 표시
        )

        self.units.append(jeol_unit)
        self.seen_ids.add(full_id)
        self.id_to_unit[full_id] = jeol_unit
        self.current_jeol = jeol_unit
        self.current_gwan = None
        self.current_jo = None

        self.order_counters[UnitType.GWAN] = 0

        return True

    def _parse_jo(self, line: str, match, line_num: int):
        """조 파싱 (조가 나타나면 상위 장/절은 본문임)"""
        jo_number = match.group(1)
        jo_title = match.group(2) if match.lastindex >= 2 else None

        # 조가 나타났으므로 현재 장/절은 목차가 아님
        if self.current_jang:
            self.current_jang.is_toc = False
        if self.current_jeol:
            self.current_jeol.is_toc = False

        # 부모 결정
        parent = (self.current_gwan or self.current_jeol or
                 self.current_jang or self.current_pyeon)
        parent_id = parent.full_id if parent else self.law_name
        parent_path = parent.unit_path if parent else ""

        jo_content = f"제{jo_number}"
        if jo_title:
            jo_content += f"({jo_title})"

        unit_path = f"{parent_path}_제{jo_number}" if parent_path else f"제{jo_number}"
        full_id = f"{parent_id}::제{jo_number}" if parent_id else f"제{jo_number}"

        # 중복 체크
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
        self.id_to_unit[full_id] = jo_unit
        self.current_jo = jo_unit
        self.current_hang = None
        self.current_ho = None

        self.order_counters[UnitType.HANG] = 0

    def _remove_toc_units(self):
        """목차 노드 제거"""
        print("\n[후처리] 목차 노드 제거 중...")

        # 1단계: 하위 절이 본문인 장도 본문으로 표시
        for unit in self.units:
            if unit.unit_type == UnitType.JANG and unit.is_toc:
                # 이 장의 하위 절들 중 본문인 것이 있는지 확인
                child_jeols = [u for u in self.units
                              if u.unit_type == UnitType.JEOL
                              and u.parent_id == unit.full_id
                              and not u.is_toc]
                if child_jeols:
                    unit.is_toc = False
                    print(f"  [수정] 하위 절이 본문이므로 장도 본문으로 변경: {unit.full_id}")

        original_count = len(self.units)

        # 2단계: is_toc=True인 노드 제거
        filtered_units = [u for u in self.units if not u.is_toc]

        removed_count = original_count - len(filtered_units)
        print(f"  제거된 목차 노드: {removed_count}개")

        if removed_count > 0:
            # 제거된 노드들 출력
            for u in self.units:
                if u.is_toc:
                    print(f"    - {u.full_id} (line {u.metadata['line_number']})")

        self.units = filtered_units

    # 나머지 메서드들은 기존 파서와 동일
    def _try_parse_pyeon(self, line: str, line_num: int) -> bool:
        """편 파싱"""
        match = self.patterns['pyeon'].match(line)
        if not match:
            return False

        number = match.group(1)
        title = match.group(2).strip() if match.group(2) else None

        unit_path = f"제{number}편"
        full_id = f"{self.law_name}::제{number}편" if self.law_name else f"제{number}편"

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
        self.id_to_unit[full_id] = pyeon_unit
        self.current_pyeon = pyeon_unit
        self.current_jang = None
        self.current_jeol = None
        self.current_gwan = None
        self.current_jo = None

        self.order_counters[UnitType.JANG] = 0

        return True

    def _try_parse_gwan(self, line: str, line_num: int) -> bool:
        """관 파싱"""
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
        self.id_to_unit[full_id] = gwan_unit
        self.current_gwan = gwan_unit
        self.current_jo = None

        return True

    def _parse_hang(self, line: str, match, content: str, line_num: int):
        """항 파싱"""
        hang_number = match.group(1) or match.group(2)

        revisions = self._extract_revisions(content)
        content = self.patterns['revision'].sub('', content).strip()

        unit_path = f"{self.current_jo.unit_path}_{hang_number}"
        full_id = f"{self.current_jo.full_id}::{hang_number}"

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
        self.id_to_unit[full_id] = hang_unit
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

        if full_id in self.seen_ids:
            return

        self.order_counters[UnitType.HO] += 1

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
        self.id_to_unit[full_id] = ho_unit
        self.current_ho = ho_unit

        self.order_counters[UnitType.MOK] = 0

    def _parse_mok(self, line: str, match, line_num: int):
        """목 파싱"""
        mok_char = match.group(1)
        mok_content = match.group(2)

        unit_path = f"{self.current_ho.unit_path}_{mok_char}목"
        full_id = f"{self.current_ho.full_id}::{mok_char}목"

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
        self.id_to_unit[full_id] = mok_unit

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
                'labels': [unit.unit_type.name],
                'properties': {
                    'number': unit.unit_number,
                    'title': unit.title,
                    'content': unit.content,
                    'full_id': unit.full_id,
                    'path': unit.unit_path,
                    'order': unit.order,
                }
            }

            if unit.revision_dates:
                node['properties']['revision_dates'] = unit.revision_dates

            if unit.metadata:
                node['properties']['metadata'] = json.dumps(unit.metadata, ensure_ascii=False)

            nodes.append(node)

        return nodes

    def to_neo4j_relationships(self) -> List[Dict]:
        """Neo4j 관계 형식으로 변환"""
        relationships = []

        for unit in self.units:
            if unit.parent_id:
                relationships.append({
                    'type': 'CONTAINS',
                    'from_id': unit.parent_id,
                    'to_id': unit.full_id,
                    'properties': {
                        'order': unit.order
                    }
                })

        return relationships
