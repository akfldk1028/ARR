"""
Load local parking ordinance overrides into Neo4j.

The structured ordinance data lives in law/data/structured. This script only
loads reviewed source artifacts and override relationships.
"""

import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from neo4j import GraphDatabase


DEFAULT_DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "structured" / "seoul_parking_ordinance_rules.json"

LOCAL_RULE_DEFAULTS = {
    "formula_detail": None,
    "external_reference": None,
    "requires_external_rule": False,
    "area_method": None,
    "specific_units_json": None,
    "min_area_m2_exclusive": None,
    "threshold_area_m2": None,
    "base_spaces": None,
    "increment_area_m2": None,
    "local_min_spaces_per_household": None,
    "local_min_spaces_under_30m2": None,
    "local_min_spaces_under_60m2": None,
    "rounding_rule": "ordinance_note_6_half_up_total_under_one_zero",
    "rounding_rule_detail": None,
    "notes": None,
}

CONSTRAINTS = [
    "CREATE CONSTRAINT local_ordinance_id_unique IF NOT EXISTS FOR (n:LocalOrdinance) REQUIRE n.ordinance_id IS UNIQUE",
    "CREATE CONSTRAINT local_parking_requirement_rule_id_unique IF NOT EXISTS FOR (n:LocalParkingRequirementRule) REQUIRE n.rule_id IS UNIQUE",
]

QUERY = """
MERGE (domain:Domain {domain_id: 'parking_regulation'})
ON CREATE SET domain.domain_name = '주차 규제'
MERGE (ordinance:LocalOrdinance {ordinance_id: $source.ordinance_id})
SET ordinance.appendix_id = $source.appendix_id,
    ordinance.jurisdiction_name = $source.jurisdiction_name,
    ordinance.jurisdiction_level = $source.jurisdiction_level,
    ordinance.pnu_prefix = $source.pnu_prefix,
    ordinance.source_title = $source.source_title,
    ordinance.source_url = $source.source_url,
    ordinance.text_path = $source.text_path,
    ordinance.effective_date = $source.effective_date,
    ordinance.appendix_revision_date = $source.appendix_revision_date,
    ordinance.ordinance_no = $source.ordinance_no,
    ordinance.source_parse_status = $source.structured_by,
    ordinance.updated_at = datetime()
MERGE (ordinance)-[:BELONGS_TO_DOMAIN]->(domain)
WITH ordinance, domain
UNWIND $rules AS rule
MATCH (base:ParkingRequirementRule {rule_id: rule.overrides_rule_id})
MERGE (r:LocalParkingRequirementRule {rule_id: rule.rule_id})
SET r.overrides_rule_id = rule.overrides_rule_id,
    r.row_no = rule.row_no,
    r.facility_group = rule.facility_group,
    r.basis_metric = rule.basis_metric,
    r.spaces_per = rule.spaces_per,
    r.formula = rule.formula,
    r.formula_detail = rule.formula_detail,
    r.external_reference = rule.external_reference,
    r.requires_external_rule = rule.requires_external_rule,
    r.area_method = rule.area_method,
    r.specific_units_json = rule.specific_units_json,
    r.min_area_m2_exclusive = rule.min_area_m2_exclusive,
    r.threshold_area_m2 = rule.threshold_area_m2,
    r.base_spaces = rule.base_spaces,
    r.increment_area_m2 = rule.increment_area_m2,
    r.local_min_spaces_per_household = rule.local_min_spaces_per_household,
    r.local_min_spaces_under_30m2 = rule.local_min_spaces_under_30m2,
    r.local_min_spaces_under_60m2 = rule.local_min_spaces_under_60m2,
    r.rounding_rule = rule.rounding_rule,
    r.rounding_rule_detail = rule.rounding_rule_detail,
    r.notes = rule.notes,
    r.source_ordinance = ordinance.ordinance_id,
    r.source_appendix = ordinance.appendix_id,
    r.source_parse_status = $source.structured_by,
    r.updated_at = datetime()
MERGE (ordinance)-[:HAS_REQUIREMENT_RULE]->(r)
MERGE (r)-[:OVERRIDES]->(base)
MERGE (r)-[:BELONGS_TO_DOMAIN]->(domain)
WITH domain
MATCH (n)-[:BELONGS_TO_DOMAIN]->(domain)
WITH domain, count(DISTINCT n) AS parking_count
SET domain.node_count = parking_count,
    domain.updated_at = $now
RETURN parking_count
"""

VERIFY_QUERY = """
MATCH (o:LocalOrdinance {ordinance_id: $ordinance_id})-[:HAS_REQUIREMENT_RULE]->(r:LocalParkingRequirementRule)
OPTIONAL MATCH (r)-[:OVERRIDES]->(base:ParkingRequirementRule)
RETURN o.jurisdiction_name AS jurisdiction_name,
       o.pnu_prefix AS pnu_prefix,
       count(r) AS local_rule_count,
       count(base) AS override_count
"""


def normalize_rules(rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{**LOCAL_RULE_DEFAULTS, **rule} for rule in rules]


def load_rules(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    required = ["ordinance_source", "local_parking_rules"]
    missing = [key for key in required if key not in data]
    if missing:
        raise ValueError(f"missing keys in {path}: {missing}")
    return data


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("--uri", default=os.getenv("NEO4J_URI", "bolt://localhost:7687"))
    parser.add_argument("--user", default=os.getenv("NEO4J_USER", "neo4j"))
    parser.add_argument("--password", default=os.getenv("NEO4J_PASSWORD", ""))
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA_PATH)
    args = parser.parse_args()

    data = load_rules(args.data)
    source = data["ordinance_source"]
    driver = GraphDatabase.driver(args.uri, auth=(args.user, args.password))
    try:
        with driver.session() as session:
            for constraint in CONSTRAINTS:
                session.run(constraint)
            result = session.run(
                QUERY,
                source=source,
                rules=normalize_rules(data["local_parking_rules"]),
                now=datetime.now().isoformat(),
            ).single()
            print("ordinance_update", dict(result) if result else {})
            verify = session.run(VERIFY_QUERY, ordinance_id=source["ordinance_id"]).single()
            print("verify", dict(verify) if verify else {})
    finally:
        driver.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
