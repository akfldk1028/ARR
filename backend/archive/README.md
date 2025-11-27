# Archive - 보관된 파일들

이 디렉토리는 프로젝트 루트에서 정리된 파일들을 보관합니다.

**정리 날짜:** 2025-11-13

---

## 디렉토리 구조

### `check_scripts/`
분석 및 체크 스크립트들
- `check_*.py` - Neo4j 데이터 검증 스크립트
- `analyze_*.py` - 데이터 분석 스크립트

### `test_scripts/`
테스트 및 유틸리티 스크립트들
- `clean_*.py` - 데이터 정리 스크립트
- `create_*.py` - 테스트 데이터 생성
- `delete_*.py` - 데이터 삭제
- `rebuild_*.py` - 시스템 재구축
- `verify_*.py` - 검증 스크립트
- `process_law_full_auto.py` - 법률 자동 처리 (구버전)
- `add_hang_embeddings_fixed.py` - 임베딩 추가 (구버전)
- `initialize_domains.py` - 도메인 초기화 (현재: law/scripts/)

### `outputs/`
테스트 출력 및 로그 파일들
- `*.txt` - 출력 파일
- `*.log` - 로그 파일
- `rebalance_output.txt` - 도메인 리밸런싱 출력
- `step5_output.txt`, `step6_output.txt` - 단계별 출력

### `temp_docs/`
임시 문서 및 개발 노트
- `AGENTS.md` - 에이전트 시스템 문서 (구버전)
- `ARCHITECTURE*.md` - 아키텍처 문서 (구버전)
- `NEO4J_*.md` - Neo4j 관련 임시 문서
- `METADATA_FIX_SUMMARY.md` - 메타데이터 수정 요약
- `PARSING_FIX_SUMMARY.md` - 파싱 수정 요약
- `neo4j_triggers.md`, `fix_neo4j_triggers.cypher` - Neo4j 트리거 관련

### `temp_dirs/`
임시 디렉토리들
- `parsed/` - 임시 파싱 데이터
- `parser/` - 임시 파서 파일

### `backup_working_version_20250919/`
2025년 9월 19일 작동 버전 백업

---

## 주의사항

⚠️ 이 디렉토리의 파일들은 현재 시스템에서 사용되지 않습니다.

- 삭제하기 전에 내용 확인 권장
- 필요한 파일이 있다면 적절한 위치로 이동
- 일정 기간 후 전체 삭제 가능

---

## 현재 시스템 파일 위치

**법률 시스템:**
- 실행 스크립트: `law/STEP/`
- 원본 스크립트: `law/scripts/`
- 데이터: `law/data/`
- Neo4j 백업: `law/data/neo4j_backups/`

**문서:**
- 주요 문서: `docs/`
- 시스템 가이드: `law/SYSTEM_GUIDE.md`
- 설정 가이드: `docs/2025-11-13-LAW_NEO4J_COMPLETE_SETUP_GUIDE.md`

**프로젝트 구조:**
- Django 앱: `agents/`, `chat/`, `core/`, etc.
- 설정 파일: `backend/`, `manage.py`, `CLAUDE.md`
- 그래프 DB: `graph_db/`
- 공유 코드: `src/`
