"""
law.go.kr Open API 법령 다운로더

법률/시행령/시행규칙을 law.go.kr API에서 다운로드하여
기존 step2 (JSON->Neo4j) 파이프라인과 호환되는 JSON으로 저장.

Usage:
    python law_downloader.py --oc YOUR_EMAIL
    python law_downloader.py --list
    python law_downloader.py --force
    LAW_API_OC=email python law_downloader.py
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path


# --- Config ---

LAWS_TO_DOWNLOAD = [
    # --- 기존 6법 (18개) ---
    ("국토의 계획 및 이용에 관한 법률", "법률"),
    ("국토의 계획 및 이용에 관한 법률 시행령", "시행령"),
    ("국토의 계획 및 이용에 관한 법률 시행규칙", "시행규칙"),
    ("건축법", "법률"),
    ("건축법 시행령", "시행령"),
    ("건축법 시행규칙", "시행규칙"),
    ("농지법", "법률"),
    ("농지법 시행령", "시행령"),
    ("농지법 시행규칙", "시행규칙"),
    ("산지관리법", "법률"),
    ("산지관리법 시행령", "시행령"),
    ("산지관리법 시행규칙", "시행규칙"),
    ("자연공원법", "법률"),
    ("자연공원법 시행령", "시행령"),
    ("자연공원법 시행규칙", "시행규칙"),
    ("수도법", "법률"),
    ("수도법 시행령", "시행령"),
    ("수도법 시행규칙", "시행규칙"),
    # --- Phase 6A: 추가 11법 (33개) ---
    ("주택법", "법률"),
    ("주택법 시행령", "시행령"),
    ("주택법 시행규칙", "시행규칙"),
    ("주차장법", "법률"),
    ("주차장법 시행령", "시행령"),
    ("주차장법 시행규칙", "시행규칙"),
    ("하수도법", "법률"),
    ("하수도법 시행령", "시행령"),
    ("하수도법 시행규칙", "시행규칙"),
    ("경관법", "법률"),
    ("경관법 시행령", "시행령"),
    # 경관법 시행규칙은 존재하지 않음
    ("문화유산의 보존 및 활용에 관한 법률", "법률"),
    ("문화유산의 보존 및 활용에 관한 법률 시행령", "시행령"),
    ("문화유산의 보존 및 활용에 관한 법률 시행규칙", "시행규칙"),
    ("군사기지 및 군사시설 보호법", "법률"),
    ("군사기지 및 군사시설 보호법 시행령", "시행령"),
    ("군사기지 및 군사시설 보호법 시행규칙", "시행규칙"),
    ("학교보건법", "법률"),
    ("학교보건법 시행령", "시행령"),
    ("학교보건법 시행규칙", "시행규칙"),
    ("소방시설 설치 및 관리에 관한 법률", "법률"),
    ("소방시설 설치 및 관리에 관한 법률 시행령", "시행령"),
    ("소방시설 설치 및 관리에 관한 법률 시행규칙", "시행규칙"),
    ("장애인ㆍ노인ㆍ임산부 등의 편의증진 보장에 관한 법률", "법률"),
    ("장애인ㆍ노인ㆍ임산부 등의 편의증진 보장에 관한 법률 시행령", "시행령"),
    ("장애인ㆍ노인ㆍ임산부 등의 편의증진 보장에 관한 법률 시행규칙", "시행규칙"),
    ("녹색건축물 조성 지원법", "법률"),
    ("녹색건축물 조성 지원법 시행령", "시행령"),
    ("녹색건축물 조성 지원법 시행규칙", "시행규칙"),
    ("도시 및 주거환경정비법", "법률"),
    ("도시 및 주거환경정비법 시행령", "시행령"),
    ("도시 및 주거환경정비법 시행규칙", "시행규칙"),
    # --- Phase 6B: 추가 ---
    ("도시공원 및 녹지 등에 관한 법률", "법률"),
    ("도시공원 및 녹지 등에 관한 법률 시행령", "시행령"),
    ("도시공원 및 녹지 등에 관한 법률 시행규칙", "시행규칙"),
    ("도로법", "법률"),
    ("도로법 시행령", "시행령"),
    ("도로법 시행규칙", "시행규칙"),
    ("개발제한구역의 지정 및 관리에 관한 특별조치법", "법률"),
    ("개발제한구역의 지정 및 관리에 관한 특별조치법 시행령", "시행령"),
]

SEARCH_URL = "http://www.law.go.kr/DRF/lawSearch.do"
LAW_SERVICE_URL = "http://www.law.go.kr/DRF/lawService.do"

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data" / "api"

RATE_LIMIT_SEC = 0.5
MAX_RETRIES = 3

# 원문자 -> 숫자 매핑
CIRCLED_NUMBERS = {
    "\u2460": "1", "\u2461": "2", "\u2462": "3", "\u2463": "4", "\u2464": "5",
    "\u2465": "6", "\u2466": "7", "\u2467": "8", "\u2468": "9", "\u2469": "10",
    "\u246a": "11", "\u246b": "12", "\u246c": "13", "\u246d": "14", "\u246e": "15",
    "\u246f": "16", "\u2470": "17", "\u2471": "18", "\u2472": "19", "\u2473": "20",
}

# 법령구분 키워드 -> 타입 매핑
LAW_TYPE_MAP = {
    "법률": "법률",
    "대통령령": "시행령",
    "시행령": "시행령",
    "총리령": "시행규칙",
    "부령": "시행규칙",
    "시행규칙": "시행규칙",
}


# --- HTTP helpers ---

def api_get(url: str, params: dict) -> bytes:
    """GET request with retry and exponential backoff."""
    query = urllib.parse.urlencode(params, encoding='utf-8')
    full_url = f"{url}?{query}"

    for attempt in range(MAX_RETRIES):
        try:
            req = urllib.request.Request(full_url)
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.read()
        except (urllib.error.URLError, urllib.error.HTTPError, OSError) as e:
            if attempt == MAX_RETRIES - 1:
                raise
            wait = 2 ** attempt
            print(f"  Retry {attempt + 1}/{MAX_RETRIES} after {wait}s: {e}")
            time.sleep(wait)
    return b""  # unreachable


def parse_xml(data: bytes) -> ET.Element:
    """Parse XML bytes, handling BOM and encoding."""
    text = data.decode('utf-8', errors='replace')
    # Strip BOM if present
    if text.startswith('\ufeff'):
        text = text[1:]
    return ET.fromstring(text)


def xml_text(elem, tag: str, default: str = "") -> str:
    """Safely get text from XML child element."""
    child = elem.find(tag)
    if child is not None and child.text:
        return child.text.strip()
    return default


# --- Step 1: Search for law MST ---

def search_law(oc: str, law_name: str) -> list:
    """
    Search law.go.kr for a law by name.
    Returns list of (mst, name, law_type_raw) tuples.
    """
    params = {
        "OC": oc,
        "target": "law",
        "type": "XML",
        "query": law_name,
        "display": "20",
    }

    data = api_get(SEARCH_URL, params)
    root = parse_xml(data)

    results = []
    for item in root.iter("law"):
        mst = xml_text(item, "법령일련번호")
        name = xml_text(item, "법령명한글")
        law_type_raw = xml_text(item, "법령구분명")
        if mst and name:
            results.append((mst, name, law_type_raw))

    return results


def find_best_match(results: list, target_name: str, target_type: str) -> tuple:
    """
    Find the best matching law from search results.
    Returns (mst, name, law_type_raw) or None.
    """
    # Exact name match first
    def normalize_type(raw: str) -> str:
        if raw in LAW_TYPE_MAP:
            return LAW_TYPE_MAP[raw]
        # "국토교통부령", "환경부령" 등 → 시행규칙
        if raw.endswith("부령"):
            return "시행규칙"
        return raw

    for mst, name, law_type_raw in results:
        if name == target_name and normalize_type(law_type_raw) == target_type:
            return (mst, name, law_type_raw)

    # For 시행령/시행규칙, the API may return the base law name
    # e.g., searching "건축법 시행령" returns "건축법" with type "대통령령"
    base_name = target_name
    for suffix in (" 시행령", " 시행규칙"):
        if target_name.endswith(suffix):
            base_name = target_name[:-len(suffix)]
            break

    for mst, name, law_type_raw in results:
        if name == base_name and normalize_type(law_type_raw) == target_type:
            return (mst, name, law_type_raw)

    # Fallback: partial name match
    for mst, name, law_type_raw in results:
        if target_name in name and normalize_type(law_type_raw) == target_type:
            return (mst, name, law_type_raw)

    return None


# --- Step 2: Get law articles (조항호목) ---

def get_law_articles(oc: str, mst: str) -> ET.Element:
    """Fetch full law data including structured articles (조문단위).
    Uses target=law which returns everything (metadata + articles).
    target=lawjosub requires a JO parameter and returns empty without it.
    """
    params = {
        "OC": oc,
        "target": "law",
        "type": "XML",
        "MST": mst,
    }
    data = api_get(LAW_SERVICE_URL, params)
    return parse_xml(data)


# --- Step 3: Get law metadata ---

def get_law_metadata(oc: str, mst: str) -> dict:
    """Fetch law metadata (name, type, promulgation info)."""
    params = {
        "OC": oc,
        "target": "law",
        "type": "XML",
        "MST": mst,
    }
    data = api_get(LAW_SERVICE_URL, params)
    root = parse_xml(data)

    # law.go.kr wraps the response differently for target=law
    # Try common tag names
    info = root.find("기본정보") or root
    return {
        "법령명": xml_text(info, "법령명_한글") or xml_text(root, "법령명_한글") or xml_text(root, "법령명한글"),
        "법령구분": xml_text(info, "법종구분") or xml_text(root, "법종구분") or xml_text(root, "법종구분명"),
        "공포일자": xml_text(info, "공포일자") or xml_text(root, "공포일자"),
        "공포번호": xml_text(info, "공포번호") or xml_text(root, "공포번호"),
        "시행일자": xml_text(info, "시행일자") or xml_text(root, "시행일자"),
    }


# --- Convert API XML to standard JSON format ---

def strip_html_tags(text: str) -> str:
    """Remove HTML/XML inline tags from content."""
    return re.sub(r'<[^>]+>', '', text).strip()


def articles_xml_to_standard_json(root: ET.Element, law_name: str,
                                  law_type: str, mst: str) -> dict:
    """
    Convert lawjosub XML to the standard parsed JSON format
    compatible with json_to_neo4j.py / neo4j_preprocessor.py.
    """
    units = []
    order_counters = {}  # parent_id -> count

    # Track current structural context for parent chaining
    current_jang = None  # (full_id, unit_path)
    current_jeol = None
    current_gwan = None

    def next_order(parent_id: str) -> int:
        order_counters[parent_id] = order_counters.get(parent_id, 0) + 1
        return order_counters[parent_id]

    # The API returns <조문단위> elements inside <조문>, each containing 항/호/목 children
    for jo_elem in root.iter("조문단위"):
        jo_num_raw = xml_text(jo_elem, "조문번호")
        if not jo_num_raw:
            continue

        jo_content_raw = xml_text(jo_elem, "조문내용")
        jo_title_raw = xml_text(jo_elem, "조문제목")

        jo_content = strip_html_tags(jo_content_raw) if jo_content_raw else ""
        jo_title = strip_html_tags(jo_title_raw) if jo_title_raw else None

        # API returns 조문번호 as bare number ("1", "4") without "조" suffix.
        # For articles like 제4조의2, 조문번호 is still just "4".
        # Extract the full article number from 조문내용 (e.g., "제1조(목적)..." → "1조")
        # or "제4조의2(건축위원회...)" → "4조의2"
        jo_article_match = re.match(r'^제(\d+조(?:의\d+)?)', jo_content)
        if jo_article_match:
            jo_number = jo_article_match.group(1)  # "1조", "4조의2"
        else:
            # Fallback: bare number + "조"
            jo_number = jo_num_raw.strip() + "조"
        if not jo_number:
            continue

        # Check if this is a structural header (장/절/관/편)
        # These appear as 조문 with content like "제1장 총칙" and no article title
        struct_match = re.match(
            r'^제(\d+)(편|장|절|관)\s*(.*)', jo_content
        ) if jo_content else None

        if struct_match and not jo_title:
            struct_num = struct_match.group(1)
            struct_type = struct_match.group(2)
            struct_title = struct_match.group(3).strip() or None

            type_map = {"편": "편", "장": "장", "절": "절", "관": "관"}
            unit_type = type_map[struct_type]

            # Determine parent based on hierarchy
            if struct_type == "장":
                parent_id = law_name
                parent_path = ""
                current_jang = None
                current_jeol = None
                current_gwan = None
            elif struct_type == "절":
                parent_id = current_jang[0] if current_jang else law_name
                parent_path = current_jang[1] if current_jang else ""
                current_jeol = None
                current_gwan = None
            elif struct_type == "관":
                parent_id = current_jeol[0] if current_jeol else (
                    current_jang[0] if current_jang else law_name)
                parent_path = current_jeol[1] if current_jeol else (
                    current_jang[1] if current_jang else "")
                current_gwan = None
            else:  # 편
                parent_id = law_name
                parent_path = ""
                current_jang = None
                current_jeol = None
                current_gwan = None

            unit_path = (f"{parent_path}_제{struct_num}{struct_type}"
                         if parent_path
                         else f"제{struct_num}{struct_type}")
            full_id = f"{law_name}::{unit_path.replace('_', '::')}"

            units.append({
                "unit_type": unit_type,
                "unit_number": struct_num,
                "title": struct_title,
                "content": jo_content,
                "unit_path": unit_path,
                "full_id": full_id,
                "parent_id": parent_id,
                "order": next_order(parent_id),
                "revision_dates": [],
                "metadata": {},
            })

            # Update current context
            if struct_type == "장":
                current_jang = (full_id, unit_path)
            elif struct_type == "절":
                current_jeol = (full_id, unit_path)
            elif struct_type == "관":
                current_gwan = (full_id, unit_path)

            continue

        # Normal article (조)
        # Determine parent: 관 > 절 > 장 > 법률
        if current_gwan:
            jo_parent_id = current_gwan[0]
            jo_parent_path = current_gwan[1]
        elif current_jeol:
            jo_parent_id = current_jeol[0]
            jo_parent_path = current_jeol[1]
        elif current_jang:
            jo_parent_id = current_jang[0]
            jo_parent_path = current_jang[1]
        else:
            jo_parent_id = law_name
            jo_parent_path = ""

        jo_unit_path = (f"{jo_parent_path}_제{jo_number}"
                        if jo_parent_path
                        else f"제{jo_number}")
        jo_full_id = f"{law_name}::{jo_unit_path.replace('_', '::')}"

        # Build content: use 조문내용 if it has substance, else fallback to header
        jo_display_content = f"제{jo_number}"
        if jo_title:
            jo_display_content += f"({jo_title})"
        if jo_content and not jo_content.startswith(f"제{jo_number}"):
            # 조문내용 has actual body text beyond article header
            jo_display_content = jo_content

        # Extract revision dates
        revision_dates = []
        if jo_content:
            for rev_match in re.finditer(r'<([^>]*(?:개정|신설|삭제)[^>]*)>', jo_content):
                dates = re.findall(r'\d{4}\.\s*\d{1,2}\.\s*\d{1,2}\.?', rev_match.group(1))
                revision_dates.extend(dates)

        # Extract referenced laws
        referenced_laws = re.findall(r'「([^」]+)」', jo_content) if jo_content else []

        jo_metadata = {}
        if referenced_laws:
            jo_metadata["referenced_laws"] = referenced_laws

        units.append({
            "unit_type": "조",
            "unit_number": jo_number,
            "title": jo_title,
            "content": jo_display_content,
            "unit_path": jo_unit_path,
            "full_id": jo_full_id,
            "parent_id": jo_parent_id,
            "order": next_order(jo_parent_id),
            "revision_dates": revision_dates,
            "metadata": jo_metadata,
        })

        # Process 항 (paragraphs)
        hang_order = 0
        for hang_elem in jo_elem.iter("항"):
            hang_num_raw = xml_text(hang_elem, "항번호")
            hang_content_raw = xml_text(hang_elem, "항내용")

            if not hang_num_raw and not hang_content_raw:
                continue

            hang_number = hang_num_raw.strip() if hang_num_raw else ""
            # Convert circled number if present in content
            for circle, num in CIRCLED_NUMBERS.items():
                if hang_number == circle:
                    hang_number = num
                    break

            # If no hang number, use sequential
            if not hang_number:
                hang_order += 1
                hang_number = str(hang_order)
            else:
                hang_order += 1

            hang_content = strip_html_tags(hang_content_raw) if hang_content_raw else ""
            # Remove leading circled number from content
            for circle in CIRCLED_NUMBERS:
                if hang_content.startswith(circle):
                    hang_content = hang_content[len(circle):].strip()
                    break

            hang_unit_path = f"{jo_unit_path}_{hang_number}"
            hang_full_id = f"{jo_full_id}::{hang_number}"

            # Revision dates from hang content
            hang_revisions = []
            if hang_content:
                for rev_match in re.finditer(r'<([^>]*(?:개정|신설|삭제)[^>]*)>', hang_content_raw or ""):
                    dates = re.findall(r'\d{4}\.\s*\d{1,2}\.\s*\d{1,2}\.?', rev_match.group(1))
                    hang_revisions.extend(dates)

            units.append({
                "unit_type": "항",
                "unit_number": hang_number,
                "title": None,
                "content": hang_content,
                "unit_path": hang_unit_path,
                "full_id": hang_full_id,
                "parent_id": jo_full_id,
                "order": hang_order,
                "revision_dates": hang_revisions,
                "metadata": {},
            })

            # Process 호 (items) within this 항
            ho_order = 0
            for ho_elem in hang_elem.iter("호"):
                ho_num_raw = xml_text(ho_elem, "호번호")
                ho_content_raw = xml_text(ho_elem, "호내용")

                if not ho_num_raw and not ho_content_raw:
                    continue

                ho_content = strip_html_tags(ho_content_raw) if ho_content_raw else ""
                ho_order += 1

                # API returns 호번호 as "1.", "8." — unreliable for 의X (8의2 shows as 8)
                # Extract real number from content: "8의2.  결합건축..." → "8의2"
                ho_content_match = re.match(r'^(\d+(?:의\d+)?)\.\s', ho_content)
                if ho_content_match:
                    ho_number = ho_content_match.group(1)
                else:
                    ho_number = ho_num_raw.strip().rstrip('.') if ho_num_raw else str(ho_order)

                ho_referenced_laws = re.findall(r'「([^」]+)」', ho_content) if ho_content else []
                ho_metadata = {}
                if ho_referenced_laws:
                    ho_metadata["referenced_laws"] = ho_referenced_laws

                ho_unit_path = f"{hang_unit_path}_제{ho_number}호"
                ho_full_id = f"{hang_full_id}::제{ho_number}호"

                units.append({
                    "unit_type": "호",
                    "unit_number": ho_number,
                    "title": None,
                    "content": ho_content,
                    "unit_path": ho_unit_path,
                    "full_id": ho_full_id,
                    "parent_id": hang_full_id,
                    "order": ho_order,
                    "revision_dates": [],
                    "metadata": ho_metadata,
                })

                # Process 목 (sub-items) within this 호
                mok_order = 0
                for mok_elem in ho_elem.iter("목"):
                    mok_num_raw = xml_text(mok_elem, "목번호")
                    mok_content_raw = xml_text(mok_elem, "목내용")

                    if not mok_num_raw and not mok_content_raw:
                        continue

                    # Strip trailing dots from 목번호: "가." → "가"
                    mok_number = mok_num_raw.strip().rstrip('.') if mok_num_raw else ""
                    mok_order += 1
                    if not mok_number:
                        mok_number = str(mok_order)

                    mok_content = strip_html_tags(mok_content_raw) if mok_content_raw else ""

                    mok_unit_path = f"{ho_unit_path}_{mok_number}목"
                    mok_full_id = f"{ho_full_id}::{mok_number}목"

                    units.append({
                        "unit_type": "목",
                        "unit_number": mok_number,
                        "title": None,
                        "content": mok_content,
                        "unit_path": mok_unit_path,
                        "full_id": mok_full_id,
                        "parent_id": ho_full_id,
                        "order": mok_order,
                        "revision_dates": [],
                        "metadata": {},
                    })

    return {
        "law_info": {
            "law_name": law_name,
            "law_type": law_type,
            "law_mst": mst,
            "source": "law.go.kr Open API",
            "total_units": len(units),
        },
        "units": units,
    }


# --- File I/O ---

def output_filename(law_name: str, law_type: str) -> str:
    """Generate safe filename from law name and type."""
    safe = law_name.replace(" ", "_")
    return f"{safe}_{law_type}.json"


def save_json(data: dict, path: Path):
    """Save dict as JSON with UTF-8 encoding."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# --- Main workflow ---

def load_oc(args_oc: str = None) -> str:
    """Load OC from args, env, or .env file."""
    if args_oc:
        return args_oc

    oc = os.environ.get("LAW_API_OC")
    if oc:
        return oc

    # Try .env in project root
    for env_path in [
        Path(__file__).resolve().parent.parent.parent.parent / ".env",  # ARR/.env
        Path(__file__).resolve().parent.parent / ".env",  # ARR/backend/.env
    ]:
        if env_path.exists():
            with open(env_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("LAW_API_OC="):
                        return line.split("=", 1)[1].strip().strip('"').strip("'")

    return ""


def do_list(oc: str):
    """Search and list all target laws."""
    print(f"Searching {len(LAWS_TO_DOWNLOAD)} laws on law.go.kr...\n")

    for law_name, law_type in LAWS_TO_DOWNLOAD:
        print(f"  Searching: {law_name} ({law_type})")
        try:
            results = search_law(oc, law_name)
            match = find_best_match(results, law_name, law_type)

            if match:
                mst, name, type_raw = match
                print(f"    -> MST={mst}  {name} [{type_raw}]")
            else:
                print(f"    -> NOT FOUND (got {len(results)} results)")
                for mst, name, type_raw in results[:5]:
                    print(f"       {mst}: {name} [{type_raw}]")
        except Exception as e:
            print(f"    -> ERROR: {e}")

        time.sleep(RATE_LIMIT_SEC)


def do_download(oc: str, force: bool = False):
    """Download all target laws."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    total = len(LAWS_TO_DOWNLOAD)
    success = 0
    skipped = 0
    errors = []

    print(f"Downloading {total} laws from law.go.kr...")
    print(f"Output: {OUTPUT_DIR}\n")

    for i, (law_name, law_type) in enumerate(LAWS_TO_DOWNLOAD, 1):
        prefix = f"[{i}/{total}]"
        print(f"{prefix} {law_name} ({law_type})")

        try:
            # Step 1: Search (always needed to get matched_name)
            print(f"  Searching...")
            results = search_law(oc, law_name)
            match = find_best_match(results, law_name, law_type)

            if not match:
                msg = f"Not found in search results ({len(results)} results)"
                print(f"  WARNING: {msg}")
                errors.append((law_name, msg))
                time.sleep(RATE_LIMIT_SEC)
                continue

            mst, matched_name, type_raw = match
            time.sleep(RATE_LIMIT_SEC)

            # Strip 시행령/시행규칙 suffix to get base law name
            # json_to_neo4j.py re-adds as "법이름(법종류)" format
            base_name = matched_name
            if law_type != "법률":
                suffix = f" {law_type}"
                if matched_name.endswith(suffix):
                    base_name = matched_name[:-len(suffix)]
            print(f"  Found: MST={mst} [{type_raw}] base={base_name}")

            fname = output_filename(base_name, law_type)
            out_path = OUTPUT_DIR / fname

            # Skip if exists
            if out_path.exists() and not force:
                print(f"  SKIP (exists): {fname}")
                skipped += 1
                continue

            # Step 2: Get articles
            print(f"  Fetching articles...")
            articles_root = get_law_articles(oc, mst)
            time.sleep(RATE_LIMIT_SEC)

            # Convert to standard JSON using base_name (without suffix)
            print(f"  Converting...")
            data = articles_xml_to_standard_json(articles_root, base_name, law_type, mst)

            # Save
            save_json(data, out_path)
            unit_count = data["law_info"]["total_units"]
            size_kb = out_path.stat().st_size / 1024
            print(f"  Saved: {fname} ({unit_count} units, {size_kb:.1f} KB)")
            success += 1

        except KeyboardInterrupt:
            print(f"\n\nInterrupted at {law_name}. {success} files saved so far.")
            sys.exit(1)
        except Exception as e:
            print(f"  ERROR: {e}")
            errors.append((law_name, str(e)))

        time.sleep(RATE_LIMIT_SEC)

    # Summary
    print(f"\n{'=' * 60}")
    print(f"Done: {success} downloaded, {skipped} skipped, {len(errors)} errors")
    if errors:
        print(f"\nErrors:")
        for name, err in errors:
            print(f"  - {name}: {err}")
    print(f"Output: {OUTPUT_DIR}")


def main():
    global OUTPUT_DIR

    # UTF-8 stdout on Windows
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')

    parser = argparse.ArgumentParser(
        description="Download Korean law data from law.go.kr Open API"
    )
    parser.add_argument(
        "--oc", type=str, default=None,
        help="Organization Code (law.go.kr login ID / email)"
    )
    parser.add_argument(
        "--list", action="store_true",
        help="Search and list available laws without downloading"
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Re-download even if file already exists"
    )
    parser.add_argument(
        "--output", type=str, default=None,
        help="Output directory (default: data/api/)"
    )

    args = parser.parse_args()

    if args.output:
        OUTPUT_DIR = Path(args.output)

    oc = load_oc(args.oc)
    if not oc:
        print("ERROR: OC (Organization Code) is required.")
        print()
        print("Provide it via one of:")
        print("  1. --oc YOUR_EMAIL")
        print("  2. LAW_API_OC=YOUR_EMAIL environment variable")
        print("  3. LAW_API_OC=YOUR_EMAIL in .env file")
        print()
        print("Register at: https://www.law.go.kr/LSW/openApi/main.do")
        sys.exit(1)

    print(f"OC: {oc}")

    if args.list:
        do_list(oc)
    else:
        do_download(oc, force=args.force)


if __name__ == "__main__":
    main()
