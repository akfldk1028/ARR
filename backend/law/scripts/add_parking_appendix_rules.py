"""
Load structured appendix rules for parking validation into Neo4j.

The law data lives in law/data/structured/parking_appendix_rules.json. This
script is only a loader: it should not be the source of legal rule content.
"""

import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from neo4j import GraphDatabase


DEFAULT_DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "structured" / "parking_appendix_rules.json"

PARKING_RULE_DEFAULTS = {
    "formula_detail": None,
    "external_reference": None,
    "requires_external_rule": False,
    "area_method": None,
    "specific_units_json": None,
    "min_area_m2_exclusive": None,
    "threshold_area_m2": None,
    "base_spaces": None,
    "increment_area_m2": None,
    "rounding_rule": "appendix_note_6",
    "rounding_rule_detail": None,
}

ACCESS_RULE_DEFAULTS = {
    "width_m": None,
    "length_m": None,
    "parallel_width_m": None,
    "parallel_length_m": None,
    "min_route_width_m": None,
    "max_slope": None,
    "max_slope_ratio": None,
    "floor_mark_width_m": None,
    "floor_mark_length_m": None,
    "stall_line_mark_width_m": None,
    "stall_line_mark_length_m": None,
    "sign_width_m": None,
    "sign_height_m": None,
    "sign_install_height_m": None,
    "requires_no_height_difference": None,
    "separated_from_vehicle_path": None,
    "slip_resistant": None,
    "requirement_level": None,
    "max_slope_requirement_level": None,
}

CONSTRAINTS = [
    "CREATE CONSTRAINT appendix_fullid_unique IF NOT EXISTS FOR (n:APPENDIX) REQUIRE n.full_id IS UNIQUE",
    "CREATE CONSTRAINT parking_requirement_rule_id_unique IF NOT EXISTS FOR (n:ParkingRequirementRule) REQUIRE n.rule_id IS UNIQUE",
    "CREATE CONSTRAINT accessible_parking_rule_id_unique IF NOT EXISTS FOR (n:AccessibleParkingFacilityRule) REQUIRE n.rule_id IS UNIQUE",
]


QUERY = """
MATCH (parkingDomain:Domain {domain_id: 'parking_regulation'})
MATCH (accessibleDomain:Domain {domain_id: 'accessible_parking_regulation'})
MATCH (parkingAppendix:APPENDIX {full_id: $parking_source.appendix_id})
SET parkingAppendix.content_status = 'structured_seed_loaded',
    parkingAppendix.source_parse_status = $parking_source.structured_by,
    parkingAppendix.source_title = $parking_source.source_title,
    parkingAppendix.source_url = $parking_source.source_url,
    parkingAppendix.pdf_path = $parking_source.pdf_path,
    parkingAppendix.text_path = $parking_source.text_path,
    parkingAppendix.effective_date = $parking_source.effective_date,
    parkingAppendix.updated_at = datetime()
WITH parkingDomain, accessibleDomain, parkingAppendix
UNWIND $parking_rules AS rule
MERGE (r:ParkingRequirementRule {rule_id: rule.rule_id})
SET r.row_no = rule.row_no,
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
    r.rounding_rule = rule.rounding_rule,
    r.rounding_rule_detail = rule.rounding_rule_detail,
    r.notes = rule.notes,
    r.source_appendix = parkingAppendix.full_id,
    r.source_parse_status = $parking_source.structured_by,
    r.updated_at = datetime()
MERGE (parkingAppendix)-[:HAS_REQUIREMENT_RULE]->(r)
MERGE (r)-[:BELONGS_TO_DOMAIN]->(parkingDomain)
WITH parkingDomain, accessibleDomain
MATCH (accessAppendix:APPENDIX {full_id: $access_source.appendix_id})
SET accessAppendix.content_status = 'structured_seed_loaded',
    accessAppendix.source_parse_status = $access_source.structured_by,
    accessAppendix.source_title = $access_source.source_title,
    accessAppendix.source_url = $access_source.source_url,
    accessAppendix.pdf_path = $access_source.pdf_path,
    accessAppendix.text_path = $access_source.text_path,
    accessAppendix.effective_date = $access_source.effective_date,
    accessAppendix.updated_at = datetime()
WITH accessibleDomain, accessAppendix
UNWIND $access_rules AS rule
MERGE (r:AccessibleParkingFacilityRule {rule_id: rule.rule_id})
SET r.category = rule.category,
    r.basis_metric = rule.basis_metric,
    r.width_m = rule.width_m,
    r.length_m = rule.length_m,
    r.parallel_width_m = rule.parallel_width_m,
    r.parallel_length_m = rule.parallel_length_m,
    r.min_route_width_m = rule.min_route_width_m,
    r.max_slope = rule.max_slope,
    r.max_slope_ratio = rule.max_slope_ratio,
    r.floor_mark_width_m = rule.floor_mark_width_m,
    r.floor_mark_length_m = rule.floor_mark_length_m,
    r.stall_line_mark_width_m = rule.stall_line_mark_width_m,
    r.stall_line_mark_length_m = rule.stall_line_mark_length_m,
    r.sign_width_m = rule.sign_width_m,
    r.sign_height_m = rule.sign_height_m,
    r.sign_install_height_m = rule.sign_install_height_m,
    r.requires_no_height_difference = rule.requires_no_height_difference,
    r.separated_from_vehicle_path = rule.separated_from_vehicle_path,
    r.slip_resistant = rule.slip_resistant,
    r.requirement_level = rule.requirement_level,
    r.max_slope_requirement_level = rule.max_slope_requirement_level,
    r.notes = rule.notes,
    r.source_appendix = accessAppendix.full_id,
    r.source_parse_status = $access_source.structured_by,
    r.updated_at = datetime()
MERGE (accessAppendix)-[:HAS_ACCESSIBILITY_RULE]->(r)
MERGE (r)-[:BELONGS_TO_DOMAIN]->(accessibleDomain)
WITH accessibleDomain
MATCH (n)-[:BELONGS_TO_DOMAIN]->(accessibleDomain)
WITH accessibleDomain, count(DISTINCT n) AS access_count
SET accessibleDomain.node_count = access_count,
    accessibleDomain.updated_at = $now
WITH access_count
MATCH (parkingDomain:Domain {domain_id: 'parking_regulation'})
MATCH (n)-[:BELONGS_TO_DOMAIN]->(parkingDomain)
WITH access_count, parkingDomain, count(DISTINCT n) AS parking_count
SET parkingDomain.node_count = parking_count,
    parkingDomain.updated_at = $now
RETURN parking_count, access_count
"""


VERIFY_QUERY = """
MATCH (pa:APPENDIX {full_id: '주차장법(시행령)::별표1'})-[:HAS_REQUIREMENT_RULE]->(r:ParkingRequirementRule)
WITH pa, count(r) AS parking_rule_count
MATCH (aa:APPENDIX {full_id: '장애인ㆍ노인ㆍ임산부 등의 편의증진 보장에 관한 법률(시행규칙)::별표1'})-[:HAS_ACCESSIBILITY_RULE]->(ar:AccessibleParkingFacilityRule)
RETURN
  pa.source_parse_status AS parking_parse_status,
  parking_rule_count,
  aa.source_parse_status AS accessibility_parse_status,
  count(ar) AS accessibility_rule_count
"""


def normalize_rules(rules: list[dict[str, Any]], defaults: dict[str, Any]) -> list[dict[str, Any]]:
    return [{**defaults, **rule} for rule in rules]


def load_rules(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    required = ["parking_source", "parking_rules", "access_source", "access_rules"]
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
    driver = GraphDatabase.driver(args.uri, auth=(args.user, args.password))
    try:
        with driver.session() as session:
            for constraint in CONSTRAINTS:
                session.run(constraint)
            now = datetime.now().isoformat()
            result = session.run(
                QUERY,
                parking_source=data["parking_source"],
                parking_rules=normalize_rules(data["parking_rules"], PARKING_RULE_DEFAULTS),
                access_source=data["access_source"],
                access_rules=normalize_rules(data["access_rules"], ACCESS_RULE_DEFAULTS),
                now=now,
            ).single()
            print("appendix_update", dict(result) if result else {})
            verify = session.run(VERIFY_QUERY).single()
            print("verify", dict(verify) if verify else {})
    finally:
        driver.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
