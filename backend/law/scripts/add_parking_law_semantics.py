"""
Add semantic parking-law graph relationships after base JSON -> Neo4j load.

This keeps the existing law graph hierarchy intact and adds only durable
decision-grade links needed by the parking validator and parking agent.
"""

import argparse
import os
from datetime import datetime

from dotenv import load_dotenv
from neo4j import GraphDatabase


PARKING_DOMAIN = {
    "domain_id": "parking_regulation",
    "domain_name": "주차",
    "description": "주차장법 체계: 부설주차장 설치기준, 구조ㆍ설비기준, 조례 위임",
}

ACCESSIBLE_PARKING_DOMAIN = {
    "domain_id": "accessible_parking_regulation",
    "domain_name": "장애인 주차",
    "description": "장애인전용주차구획: 설치 대상, 설치 비율, 주차구획 치수, 편의시설 세부기준",
}


SEMANTIC_QUERY = """
MERGE (domain:Domain {domain_id: $domain_id})
ON CREATE SET
  domain.domain_name = $domain_name,
  domain.description = $description,
  domain.created_at = $now
ON MATCH SET
  domain.domain_name = $domain_name,
  domain.description = $description,
  domain.updated_at = $now

WITH domain
MATCH (law:LAW {full_id: '주차장법(법률)'})
MATCH (decree:LAW {full_id: '주차장법(시행령)'})
MATCH (rule:LAW {full_id: '주차장법(시행규칙)'})
MERGE (law)-[:ENFORCED_BY {base_law_name: '주차장법', scope: '전체'}]->(decree)
MERGE (decree)-[:DETAILED_BY {base_law_name: '주차장법', scope: '전체'}]->(rule)

WITH domain
MATCH (article19:JO {full_id: '주차장법(법률)::제5장::제19조'})
MATCH (decree6:JO {full_id: '주차장법(시행령)::제6조'})
MATCH (rule11:JO {full_id: '주차장법(시행규칙)::제11조'})
MERGE (article19)-[:DELEGATES_TO {
  basis: '주차장법 제19조제3항',
  delegated_subject: '부설주차장을 설치하여야 할 시설물의 종류와 설치기준'
}]->(decree6)
MERGE (decree6)-[:DETAILED_BY {
  basis: '주차장법 제6조제1항',
  delegated_subject: '부설주차장의 구조ㆍ설비기준'
}]->(rule11)
MERGE (article19)-[:BELONGS_TO_DOMAIN]->(domain)
MERGE (decree6)-[:BELONGS_TO_DOMAIN]->(domain)
MERGE (rule11)-[:BELONGS_TO_DOMAIN]->(domain)

WITH domain, article19, decree6, rule11
MATCH (decree6p1:HANG {full_id: '주차장법(시행령)::제6조::1'})
MERGE (appendix:APPENDIX {full_id: '주차장법(시행령)::별표1'})
ON CREATE SET
  appendix.law_name = '주차장법',
  appendix.law_type = '시행령',
  appendix.law_category = '시행령',
  appendix.base_law_name = '주차장법',
  appendix.agent_id = 'agent_주차장법',
  appendix.number = '별표 1',
  appendix.unit_number = '별표 1',
  appendix.title = '부설주차장의 설치대상 시설물 종류 및 설치기준',
  appendix.related_article = '주차장법 시행령 제6조제1항',
  appendix.source_url = 'https://www.law.go.kr/LSW/lsBylInfoPLinkR.do?lsiSeq=273373&lsNm=%EC%A3%BC%EC%B0%A8%EC%9E%A5%EB%B2%95+%EC%8B%9C%ED%96%89%EB%A0%B9&bylNo=0001&bylBrNo=00&bylCls=BE&bylEfYd=20250817&bylEfYdYn=Y',
  appendix.content_status = 'needs_structured_table_parse',
  appendix.created_at = datetime()
ON MATCH SET
  appendix.updated_at = datetime(),
  appendix.content_status = 'needs_structured_table_parse'
MERGE (decree6p1)-[:HAS_APPENDIX {
  reference_text: '별표 1과 같다',
  status: 'appendix_node_created_table_pending'
}]->(appendix)
MERGE (appendix)-[:BELONGS_TO_DOMAIN]->(domain)

WITH domain
MATCH (n)
WHERE n.full_id STARTS WITH '주차장법(법률)::제5장::제19조'
   OR n.full_id STARTS WITH '주차장법(시행령)::제6조'
   OR n.full_id STARTS WITH '주차장법(시행규칙)::제11조'
MERGE (n)-[:BELONGS_TO_DOMAIN]->(domain)

WITH domain
MATCH (n)-[:BELONGS_TO_DOMAIN]->(domain)
WITH domain, count(DISTINCT n) AS node_count
SET domain.node_count = node_count,
    domain.updated_at = $now
RETURN domain.domain_id AS domain_id, domain.node_count AS node_count
"""


VERIFY_QUERY = """
MATCH (domain:Domain {domain_id: 'parking_regulation'})
OPTIONAL MATCH (n)-[:BELONGS_TO_DOMAIN]->(domain)
WITH domain, count(DISTINCT n) AS domain_nodes
OPTIONAL MATCH (a:JO {full_id: '주차장법(법률)::제5장::제19조'})-[r1:DELEGATES_TO]->(d:JO {full_id: '주차장법(시행령)::제6조'})
OPTIONAL MATCH (h:HANG {full_id: '주차장법(시행령)::제6조::1'})-[r2:HAS_APPENDIX]->(ap:APPENDIX {full_id: '주차장법(시행령)::별표1'})
OPTIONAL MATCH (d)-[r3:DETAILED_BY]->(rule:JO {full_id: '주차장법(시행규칙)::제11조'})
RETURN
  domain.domain_id AS domain_id,
  domain_nodes,
  count(DISTINCT r1) AS delegates_to,
  count(DISTINCT r2) AS has_appendix,
  count(DISTINCT r3) AS detailed_by,
  ap.content_status AS appendix_status
"""


ACCESSIBLE_SEMANTIC_QUERY = """
MERGE (domain:Domain {domain_id: $domain_id})
ON CREATE SET
  domain.domain_name = $domain_name,
  domain.description = $description,
  domain.created_at = $now
ON MATCH SET
  domain.domain_name = $domain_name,
  domain.description = $description,
  domain.updated_at = $now

WITH domain
MATCH (parking:Domain {domain_id: 'parking_regulation'})
MERGE (domain)-[:RELATED_DOMAIN {reason: '장애인전용주차구획은 주차 산정과 배치 검토에 같이 필요'}]->(parking)

WITH domain
MATCH (parkingRule11:JO {full_id: '주차장법(시행규칙)::제11조'})
MATCH (parkingStall:JO {full_id: '주차장법(시행규칙)::제3조'})
MATCH (stallDimension:HO {full_id: '주차장법(시행규칙)::제3조::1::제2호'})
MATCH (roadAccessible:HO {full_id: '주차장법(시행규칙)::제4조::1::제8호'})
MATCH (roadAccessibleMin:MOK {full_id: '주차장법(시행규칙)::제4조::1::제8호::가목'})
MATCH (roadAccessibleRatio:MOK {full_id: '주차장법(시행규칙)::제4조::1::제8호::나목'})
MATCH (restrictedAreaMin:HANG {full_id: '주차장법(시행규칙)::제7조의2::5'})
MERGE (parkingRule11)-[:REFERENCES {reason: '부설주차장 구조ㆍ설비기준에서 주차구획 규격 준용'}]->(parkingStall)
MERGE (parkingStall)-[:DEFINES_STALL_DIMENSION {
  stall_type: '장애인전용',
  parking_pattern: '평행주차형식 외',
  width_m: 3.3,
  length_m: 5.0,
  source: '주차장법 시행규칙 제3조제1항제2호'
}]->(stallDimension)
MERGE (roadAccessible)-[:HAS_THRESHOLD {
  case: '20대 이상 50대 미만',
  required_min_spaces: 1,
  source: '주차장법 시행규칙 제4조제1항제8호가목'
}]->(roadAccessibleMin)
MERGE (roadAccessible)-[:HAS_RATIO_RANGE {
  case: '50대 이상',
  min_percent: 2,
  max_percent: 4,
  local_ordinance_required: true,
  source: '주차장법 시행규칙 제4조제1항제8호나목'
}]->(roadAccessibleRatio)
MERGE (restrictedAreaMin)-[:PROTECTS_MINIMUM_SPACES {
  protected_space_type: '장애인 등 교통약자',
  source: '주차장법 시행규칙 제7조의2제5항'
}]->(domain)
MERGE (parkingRule11)-[:BELONGS_TO_DOMAIN]->(domain)
MERGE (parkingStall)-[:BELONGS_TO_DOMAIN]->(domain)
MERGE (stallDimension)-[:BELONGS_TO_DOMAIN]->(domain)
MERGE (roadAccessible)-[:BELONGS_TO_DOMAIN]->(domain)
MERGE (roadAccessibleMin)-[:BELONGS_TO_DOMAIN]->(domain)
MERGE (roadAccessibleRatio)-[:BELONGS_TO_DOMAIN]->(domain)
MERGE (restrictedAreaMin)-[:BELONGS_TO_DOMAIN]->(domain)

WITH domain
MATCH (accessLaw:LAW {full_id: '장애인ㆍ노인ㆍ임산부 등의 편의증진 보장에 관한 법률(법률)'})
MATCH (accessDecree:LAW {full_id: '장애인ㆍ노인ㆍ임산부 등의 편의증진 보장에 관한 법률(시행령)'})
MATCH (accessRule:LAW {full_id: '장애인ㆍ노인ㆍ임산부 등의 편의증진 보장에 관한 법률(시행규칙)'})
MERGE (accessLaw)-[:ENFORCED_BY {base_law_name: '장애인ㆍ노인ㆍ임산부 등의 편의증진 보장에 관한 법률', scope: '전체'}]->(accessDecree)
MERGE (accessDecree)-[:DETAILED_BY {base_law_name: '장애인ㆍ노인ㆍ임산부 등의 편의증진 보장에 관한 법률', scope: '전체'}]->(accessRule)

WITH domain
MATCH (accessArticle8:JO {full_id: '장애인ㆍ노인ㆍ임산부 등의 편의증진 보장에 관한 법률(법률)::제8조'})
MATCH (accessDecree4:JO {full_id: '장애인ㆍ노인ㆍ임산부 등의 편의증진 보장에 관한 법률(시행령)::제4조'})
MATCH (accessRule2:JO {full_id: '장애인ㆍ노인ㆍ임산부 등의 편의증진 보장에 관한 법률(시행규칙)::제2조'})
MATCH (accessRule2p1:HANG {full_id: '장애인ㆍ노인ㆍ임산부 등의 편의증진 보장에 관한 법률(시행규칙)::제2조::1'})
MERGE (accessArticle8)-[:DELEGATES_TO {
  basis: '편의증진법 제8조',
  delegated_subject: '대상시설별 편의시설 종류 및 구조ㆍ재질 세부기준'
}]->(accessDecree4)
MERGE (accessDecree4)-[:DETAILED_BY {
  basis: '편의증진법 시행령 제4조',
  delegated_subject: '편의시설 세부기준'
}]->(accessRule2)
MERGE (accessAppendix:APPENDIX {full_id: '장애인ㆍ노인ㆍ임산부 등의 편의증진 보장에 관한 법률(시행규칙)::별표1'})
ON CREATE SET
  accessAppendix.law_name = '장애인ㆍ노인ㆍ임산부 등의 편의증진 보장에 관한 법률',
  accessAppendix.law_type = '시행규칙',
  accessAppendix.law_category = '시행규칙',
  accessAppendix.base_law_name = '장애인ㆍ노인ㆍ임산부 등의 편의증진 보장에 관한 법률',
  accessAppendix.agent_id = 'agent_장애인ㆍ노인ㆍ임산부 등의 편의증진 보장에 관한 법률',
  accessAppendix.number = '별표 1',
  accessAppendix.unit_number = '별표 1',
  accessAppendix.title = '편의시설의 구조ㆍ재질 등에 관한 세부기준',
  accessAppendix.related_article = '편의증진법 시행규칙 제2조제1항',
  accessAppendix.content_status = 'needs_structured_table_parse',
  accessAppendix.created_at = datetime()
ON MATCH SET
  accessAppendix.updated_at = datetime(),
  accessAppendix.content_status = 'needs_structured_table_parse'
MERGE (accessRule2p1)-[:HAS_APPENDIX {
  reference_text: '별표 1과 같다',
  status: 'appendix_node_created_table_pending'
}]->(accessAppendix)
MERGE (accessArticle8)-[:BELONGS_TO_DOMAIN]->(domain)
MERGE (accessDecree4)-[:BELONGS_TO_DOMAIN]->(domain)
MERGE (accessRule2)-[:BELONGS_TO_DOMAIN]->(domain)
MERGE (accessRule2p1)-[:BELONGS_TO_DOMAIN]->(domain)
MERGE (accessAppendix)-[:BELONGS_TO_DOMAIN]->(domain)

WITH domain
MATCH (n)-[:BELONGS_TO_DOMAIN]->(domain)
WITH domain, count(DISTINCT n) AS node_count
SET domain.node_count = node_count,
    domain.updated_at = $now
RETURN domain.domain_id AS domain_id, domain.node_count AS node_count
"""


ACCESSIBLE_VERIFY_QUERY = """
MATCH (domain:Domain {domain_id: 'accessible_parking_regulation'})
OPTIONAL MATCH (n)-[:BELONGS_TO_DOMAIN]->(domain)
WITH domain, count(DISTINCT n) AS domain_nodes
OPTIONAL MATCH (:JO {full_id: '주차장법(시행규칙)::제3조'})-[r1:DEFINES_STALL_DIMENSION]->(:HO {full_id: '주차장법(시행규칙)::제3조::1::제2호'})
OPTIONAL MATCH (:HO {full_id: '주차장법(시행규칙)::제4조::1::제8호'})-[r2:HAS_THRESHOLD]->(:MOK {full_id: '주차장법(시행규칙)::제4조::1::제8호::가목'})
OPTIONAL MATCH (:HO {full_id: '주차장법(시행규칙)::제4조::1::제8호'})-[r3:HAS_RATIO_RANGE]->(:MOK {full_id: '주차장법(시행규칙)::제4조::1::제8호::나목'})
OPTIONAL MATCH (:HANG {full_id: '장애인ㆍ노인ㆍ임산부 등의 편의증진 보장에 관한 법률(시행규칙)::제2조::1'})-[r4:HAS_APPENDIX]->(ap:APPENDIX {full_id: '장애인ㆍ노인ㆍ임산부 등의 편의증진 보장에 관한 법률(시행규칙)::별표1'})
RETURN
  domain.domain_id AS domain_id,
  domain_nodes,
  count(DISTINCT r1) AS stall_dimension,
  count(DISTINCT r2) AS threshold,
  count(DISTINCT r3) AS ratio_range,
  count(DISTINCT r4) AS access_appendix,
  ap.content_status AS appendix_status
"""


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("--uri", default=os.getenv("NEO4J_URI", "bolt://localhost:7687"))
    parser.add_argument("--user", default=os.getenv("NEO4J_USER", "neo4j"))
    parser.add_argument("--password", default=os.getenv("NEO4J_PASSWORD", "11111111"))
    args = parser.parse_args()

    driver = GraphDatabase.driver(args.uri, auth=(args.user, args.password))
    try:
        now = datetime.now().isoformat()
        params = {**PARKING_DOMAIN, "now": now}
        with driver.session() as session:
            result = session.run(SEMANTIC_QUERY, params).single()
            print("semantic_update", dict(result) if result else {})
            verify = session.run(VERIFY_QUERY).single()
            print("verify", dict(verify) if verify else {})
            access_params = {**ACCESSIBLE_PARKING_DOMAIN, "now": now}
            access_result = session.run(ACCESSIBLE_SEMANTIC_QUERY, access_params).single()
            print("accessible_semantic_update", dict(access_result) if access_result else {})
            access_verify = session.run(ACCESSIBLE_VERIFY_QUERY).single()
            print("accessible_verify", dict(access_verify) if access_verify else {})
    finally:
        driver.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
