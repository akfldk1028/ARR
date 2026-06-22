"""
Load structured parking layout rules into Neo4j.

The content lives in law/data/structured/parking_layout_rules.json. This loader
turns reviewed Article 11 small attached-parking layout rules into queryable
ParkingLayoutRule nodes for MAAS and parking agents.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from neo4j import GraphDatabase


DEFAULT_DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "structured" / "parking_layout_rules.json"

LAYOUT_RULE_DEFAULTS = {
    "max_total_spaces": None,
    "min_lane_width_m": None,
    "max_road_width_m_exclusive": None,
    "min_road_width_m": None,
    "requires_no_sidewalk_separation": None,
    "requires_sidewalk_separation": None,
    "min_aisle_width_counting_road_m": None,
    "min_parallel_aisle_width_counting_road_m": None,
    "road_inclusion_scope": None,
    "parking_angle": None,
    "requires_no_obstruction_to_parking_use": None,
    "max_depth_from_aisle": None,
    "min_entrance_width_m": None,
    "dead_end_road_authority_approval_min_width_m": None,
    "prohibits_obstacle_between_road_and_stall": None,
}

CONSTRAINTS = [
    "CREATE CONSTRAINT parking_layout_rule_id_unique IF NOT EXISTS FOR (n:ParkingLayoutRule) REQUIRE n.rule_id IS UNIQUE",
]

QUERY = """
MATCH (parkingDomain:Domain {domain_id: 'parking_regulation'})
MATCH (source:JO {full_id: $layout_source.source_id})
SET source.content_status = coalesce(source.content_status, 'raw_law_loaded'),
    source.layout_parse_status = $layout_source.structured_by,
    source.layout_source_title = $layout_source.source_title,
    source.layout_source_url = $layout_source.source_url,
    source.layout_effective_date = $layout_source.effective_date,
    source.updated_at = datetime()
WITH parkingDomain, source
UNWIND $layout_rules AS rule
MERGE (r:ParkingLayoutRule {rule_id: rule.rule_id})
SET r.category = rule.category,
    r.condition = rule.condition,
    r.max_total_spaces = rule.max_total_spaces,
    r.rule_type = rule.rule_type,
    r.min_lane_width_m = rule.min_lane_width_m,
    r.max_road_width_m_exclusive = rule.max_road_width_m_exclusive,
    r.min_road_width_m = rule.min_road_width_m,
    r.requires_no_sidewalk_separation = rule.requires_no_sidewalk_separation,
    r.requires_sidewalk_separation = rule.requires_sidewalk_separation,
    r.min_aisle_width_counting_road_m = rule.min_aisle_width_counting_road_m,
    r.min_parallel_aisle_width_counting_road_m = rule.min_parallel_aisle_width_counting_road_m,
    r.road_inclusion_scope = rule.road_inclusion_scope,
    r.parking_angle = rule.parking_angle,
    r.requires_no_obstruction_to_parking_use = rule.requires_no_obstruction_to_parking_use,
    r.max_depth_from_aisle = rule.max_depth_from_aisle,
    r.min_entrance_width_m = rule.min_entrance_width_m,
    r.dead_end_road_authority_approval_min_width_m = rule.dead_end_road_authority_approval_min_width_m,
    r.prohibits_obstacle_between_road_and_stall = rule.prohibits_obstacle_between_road_and_stall,
    r.formula_detail = rule.formula_detail,
    r.requirement_level = rule.requirement_level,
    r.notes = rule.notes,
    r.source_full_id = rule.source_full_id,
    r.source_article = source.full_id,
    r.source_parse_status = $layout_source.structured_by,
    r.updated_at = datetime()
MERGE (source)-[:HAS_LAYOUT_RULE]->(r)
MERGE (r)-[:BELONGS_TO_DOMAIN]->(parkingDomain)
WITH r, rule
OPTIONAL MATCH (sourceUnit {full_id: rule.source_full_id})
FOREACH (_ IN CASE WHEN sourceUnit IS NULL THEN [] ELSE [1] END |
  MERGE (r)-[:DERIVED_FROM]->(sourceUnit)
)
WITH count(r) AS layout_rule_count
MATCH (parkingDomain:Domain {domain_id: 'parking_regulation'})
MATCH (n)-[:BELONGS_TO_DOMAIN]->(parkingDomain)
WITH layout_rule_count, parkingDomain, count(DISTINCT n) AS parking_count
SET parkingDomain.node_count = parking_count,
    parkingDomain.updated_at = $now
RETURN layout_rule_count, parking_count
"""

VERIFY_QUERY = """
MATCH (:JO {full_id: '주차장법(시행규칙)::제11조'})-[:HAS_LAYOUT_RULE]->(r:ParkingLayoutRule)
RETURN count(r) AS layout_rule_count,
       collect(r.rule_id) AS rule_ids
"""


def load_rules(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    required = ["layout_source", "layout_rules"]
    missing = [key for key in required if key not in data]
    if missing:
        raise ValueError(f"missing keys in {path}: {missing}")
    return data


def normalize_rules(rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{**LAYOUT_RULE_DEFAULTS, **rule} for rule in rules]


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
                layout_source=data["layout_source"],
                layout_rules=normalize_rules(data["layout_rules"]),
                now=now,
            ).single()
            print("layout_update", dict(result) if result else {})
            verify = session.run(VERIFY_QUERY).single()
            print("verify", dict(verify) if verify else {})
    finally:
        driver.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
