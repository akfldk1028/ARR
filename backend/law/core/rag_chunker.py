"""
RAG 청킹 모듈
표준 JSON을 RAG 시스템용 청크로 변환
"""
from typing import Dict, List
import re


class LegalRAGChunker:
    """
    법령 문서를 RAG용 청크로 변환하는 클래스

    다중 레벨 청킹 지원:
    - Level 1: 조 전체
    - Level 2: 항 단위
    - Level 3: 호 단위 (가장 세밀)
    """

    def chunk(self, data: Dict) -> List[Dict]:
        """
        표준 JSON에서 RAG 청크 생성

        Args:
            data: 표준 JSON 데이터

        Returns:
            청크 리스트
        """
        chunks = []
        chunk_counter = 0

        law_info = data['law_info']
        units = data['units']

        # 조(JO) 단위로 그룹화
        jo_groups = self._group_by_jo(units)

        # 각 조에 대해 청크 생성
        for jo, jo_children in jo_groups:
            # Level 1: 조 전체 청크
            chunk_counter += 1
            jo_chunk = self._create_jo_chunk(jo, jo_children, chunk_counter, law_info)
            chunks.append(jo_chunk)

            # Level 2: 항별 청크
            hang_groups = self._group_by_hang(jo_children)

            for hang, hang_children in hang_groups:
                chunk_counter += 1
                hang_chunk = self._create_hang_chunk(jo, hang, hang_children, chunk_counter, law_info)
                chunks.append(hang_chunk)

                # Level 3: 호별 청크
                ho_groups = self._group_by_ho(hang_children)

                for ho, mok_children in ho_groups:
                    chunk_counter += 1
                    ho_chunk = self._create_ho_chunk(jo, hang, ho, mok_children, chunk_counter, law_info)
                    chunks.append(ho_chunk)

        return chunks

    def _group_by_jo(self, units: List[Dict]) -> List[tuple]:
        """조 단위로 그룹화"""
        jo_groups = []
        current_jo = None
        current_jo_children = []

        for unit in units:
            if unit['unit_type'] == '조':
                if current_jo:
                    jo_groups.append((current_jo, current_jo_children))
                current_jo = unit
                current_jo_children = []
            elif current_jo:
                current_jo_children.append(unit)

        if current_jo:
            jo_groups.append((current_jo, current_jo_children))

        return jo_groups

    def _group_by_hang(self, units: List[Dict]) -> List[tuple]:
        """항 단위로 그룹화"""
        hang_groups = []
        current_hang = None
        current_hang_children = []

        for unit in units:
            if unit['unit_type'] == '항':
                if current_hang:
                    hang_groups.append((current_hang, current_hang_children))
                current_hang = unit
                current_hang_children = []
            elif current_hang and unit['unit_type'] in ['호', '목']:
                current_hang_children.append(unit)

        if current_hang:
            hang_groups.append((current_hang, current_hang_children))

        return hang_groups

    def _group_by_ho(self, units: List[Dict]) -> List[tuple]:
        """호 단위로 그룹화"""
        ho_groups = []
        current_ho = None
        current_ho_children = []

        for unit in units:
            if unit['unit_type'] == '호':
                if current_ho:
                    ho_groups.append((current_ho, current_ho_children))
                current_ho = unit
                current_ho_children = []
            elif current_ho and unit['unit_type'] == '목':
                current_ho_children.append(unit)

        if current_ho:
            ho_groups.append((current_ho, current_ho_children))

        return ho_groups

    def _create_jo_chunk(self, jo: Dict, children: List[Dict], chunk_id: int, law_info: Dict) -> Dict:
        """조 전체 청크 생성"""
        jo_title = f"제{jo['unit_number']}"
        if jo['title']:
            jo_title += f"({jo['title']})"

        content_parts = [jo_title]
        for child in children:
            content_parts.append(self._format_unit_content(child))

        content = " ".join(content_parts)

        return {
            "chunk_id": f"chunk_{chunk_id:05d}",
            "chunk_level": "조전체",
            "content": content,
            "source_ids": [jo['full_id']] + [c['full_id'] for c in children],
            "metadata": {
                "law_name": law_info['law_name'],
                "law_type": law_info['law_type'],
                "law_category": law_info.get('law_category'),
                "base_law_name": law_info.get('base_law_name'),
                "agent_id": law_info.get('agent_id'),
                "jo_number": jo['unit_number'],
                "jo_title": jo['title'],
                "jo_id": jo['full_id'],
                "unit_count": 1 + len(children),
                "revision_dates": jo['revision_dates']
            }
        }

    def _create_hang_chunk(self, jo: Dict, hang: Dict, children: List[Dict], chunk_id: int, law_info: Dict) -> Dict:
        """항 단위 청크 생성"""
        jo_title = f"제{jo['unit_number']}"
        if jo['title']:
            jo_title += f"({jo['title']})"

        hang_content = self._clean_content(hang['content'])

        content_parts = [jo_title, f"{hang['unit_number']} {hang_content}"]
        for child in children:
            content_parts.append(self._format_unit_content(child))

        content = " ".join(content_parts)

        return {
            "chunk_id": f"chunk_{chunk_id:05d}",
            "chunk_level": "항단위",
            "content": content,
            "source_ids": [jo['full_id'], hang['full_id']] + [c['full_id'] for c in children],
            "metadata": {
                "law_name": law_info['law_name'],
                "law_type": law_info['law_type'],
                "law_category": law_info.get('law_category'),
                "base_law_name": law_info.get('base_law_name'),
                "agent_id": law_info.get('agent_id'),
                "jo_number": jo['unit_number'],
                "jo_title": jo['title'],
                "jo_id": jo['full_id'],
                "hang_number": hang['unit_number'],
                "hang_id": hang['full_id'],
                "unit_count": 2 + len(children),
                "revision_dates": hang['revision_dates']
            }
        }

    def _create_ho_chunk(self, jo: Dict, hang: Dict, ho: Dict, mok_children: List[Dict], chunk_id: int, law_info: Dict) -> Dict:
        """호 단위 청크 생성 (법적 맥락 보존)"""
        jo_title = f"제{jo['unit_number']}"
        if jo['title']:
            jo_title += f"({jo['title']})"

        hang_intro = self._clean_content(hang['content'])[:100]
        ho_content = self._clean_content(ho['content'])

        content_parts = [
            jo_title,
            f"{hang['unit_number']} {hang_intro}",
            f"{ho['unit_number']}. {ho_content}"
        ]

        for mok in mok_children:
            content_parts.append(self._format_unit_content(mok))

        content = " ".join(content_parts)

        return {
            "chunk_id": f"chunk_{chunk_id:05d}",
            "chunk_level": "호단위",
            "content": content,
            "source_ids": [jo['full_id'], hang['full_id'], ho['full_id']] +
                         [m['full_id'] for m in mok_children],
            "metadata": {
                "law_name": law_info['law_name'],
                "law_type": law_info['law_type'],
                "law_category": law_info.get('law_category'),
                "base_law_name": law_info.get('base_law_name'),
                "agent_id": law_info.get('agent_id'),
                "jo_number": jo['unit_number'],
                "jo_title": jo['title'],
                "jo_id": jo['full_id'],
                "hang_number": hang['unit_number'],
                "hang_id": hang['full_id'],
                "ho_number": ho['unit_number'],
                "ho_id": ho['full_id'],
                "unit_count": 3 + len(mok_children),
                "referenced_laws": ho['metadata'].get('referenced_laws', [])
            }
        }

    def _format_unit_content(self, unit: Dict) -> str:
        """단위 내용 포맷팅"""
        content = self._clean_content(unit['content'])

        if unit['unit_type'] == '항':
            return f"{unit['unit_number']} {content}"
        elif unit['unit_type'] == '호':
            return f"{unit['unit_number']}. {content}"
        elif unit['unit_type'] == '목':
            return f"{unit['unit_number']}. {content}"
        else:
            return content

    def _clean_content(self, text: str) -> str:
        """개정 표시 등 제거"""
        return re.sub(r'<[^>]+>', '', text).strip()
