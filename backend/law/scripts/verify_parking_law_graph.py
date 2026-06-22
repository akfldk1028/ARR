"""
Verify Parking Lot Act graph coverage in Neo4j.

This script is intentionally narrow: it checks whether the parking-law graph is
usable by a deterministic parking validator and a future AG-light parking agent.
"""

import argparse
import os
from dataclasses import dataclass
from typing import Any, Callable

from dotenv import load_dotenv
from neo4j import GraphDatabase


@dataclass
class Check:
    name: str
    query: str
    validate: Callable[[list[dict[str, Any]]], tuple[bool, str]]


def one_row_value(key: str, expected: Any) -> Callable[[list[dict[str, Any]]], tuple[bool, str]]:
    def _validate(rows: list[dict[str, Any]]) -> tuple[bool, str]:
        actual = rows[0].get(key) if rows else None
        return actual == expected, f"{key}={actual!r}, expected={expected!r}"

    return _validate


def min_count(key: str, expected_min: int) -> Callable[[list[dict[str, Any]]], tuple[bool, str]]:
    def _validate(rows: list[dict[str, Any]]) -> tuple[bool, str]:
        actual = rows[0].get(key) if rows else 0
        return actual >= expected_min, f"{key}={actual}, expected>={expected_min}"

    return _validate


def exact_rows(expected_count: int) -> Callable[[list[dict[str, Any]]], tuple[bool, str]]:
    def _validate(rows: list[dict[str, Any]]) -> tuple[bool, str]:
        return len(rows) == expected_count, f"rows={len(rows)}, expected={expected_count}"

    return _validate


def all_true(key: str) -> Callable[[list[dict[str, Any]]], tuple[bool, str]]:
    def _validate(rows: list[dict[str, Any]]) -> tuple[bool, str]:
        bad = [row for row in rows if not row.get(key)]
        return not bad, f"bad_rows={bad[:3]}"

    return _validate


CHECKS = [
    Check(
        "connection",
        "RETURN 1 AS ok",
        one_row_value("ok", 1),
    ),
    Check(
        "parking_law_roots",
        """
        MATCH (l:LAW)
        WHERE l.full_id IN ['주차장법(법률)', '주차장법(시행령)', '주차장법(시행규칙)']
        RETURN l.full_id AS full_id, l.law_type AS law_type, l.base_law_name AS base_law_name
        ORDER BY full_id
        """,
        exact_rows(3),
    ),
    Check(
        "parking_total_nodes",
        """
        MATCH (n)
        WHERE n.full_id STARTS WITH '주차장법(법률)'
           OR n.full_id STARTS WITH '주차장법(시행령)'
           OR n.full_id STARTS WITH '주차장법(시행규칙)'
        RETURN count(n) AS count
        """,
        min_count("count", 1000),
    ),
    Check(
        "parking_root_contains",
        """
        UNWIND ['주차장법(법률)', '주차장법(시행령)', '주차장법(시행규칙)'] AS root
        MATCH (:LAW {full_id: root})-[r:CONTAINS]->()
        RETURN root, count(r) > 0 AS ok
        ORDER BY root
        """,
        all_true("ok"),
    ),
    Check(
        "article_19_exists",
        """
        MATCH (j:JO {full_id: '주차장법(법률)::제5장::제19조'})
        RETURN j.title AS title, j.title = '부설주차장의 설치ㆍ지정' AS ok
        """,
        all_true("ok"),
    ),
    Check(
        "decree_article_6_exists",
        """
        MATCH (j:JO {full_id: '주차장법(시행령)::제6조'})
        RETURN j.title AS title, j.title = '부설주차장의 설치기준' AS ok
        """,
        all_true("ok"),
    ),
    Check(
        "rule_article_11_exists",
        """
        MATCH (j:JO {full_id: '주차장법(시행규칙)::제11조'})
        RETURN j.title AS title, j.title = '부설주차장의 구조ㆍ설비기준' AS ok
        """,
        all_true("ok"),
    ),
    Check(
        "article_19_children",
        """
        MATCH (:JO {full_id: '주차장법(법률)::제5장::제19조'})-[:CONTAINS]->(h:HANG)
        RETURN count(h) AS count
        """,
        min_count("count", 17),
    ),
    Check(
        "decree_6_children",
        """
        MATCH (:JO {full_id: '주차장법(시행령)::제6조'})-[:CONTAINS]->(h:HANG)
        RETURN count(h) AS count
        """,
        min_count("count", 4),
    ),
    Check(
        "rule_11_children",
        """
        MATCH (:JO {full_id: '주차장법(시행규칙)::제11조'})-[:CONTAINS]->(h:HANG)
        RETURN count(h) AS count
        """,
        min_count("count", 6),
    ),
    Check(
        "law_to_decree_semantic_chain",
        """
        MATCH (:LAW {full_id: '주차장법(법률)'})-[r:ENFORCED_BY]->(:LAW {full_id: '주차장법(시행령)'})
        RETURN count(r) AS count
        """,
        one_row_value("count", 1),
    ),
    Check(
        "decree_to_rule_semantic_chain",
        """
        MATCH (:LAW {full_id: '주차장법(시행령)'})-[r:DETAILED_BY]->(:LAW {full_id: '주차장법(시행규칙)'})
        RETURN count(r) AS count
        """,
        one_row_value("count", 1),
    ),
    Check(
        "article_19_delegates_to_decree_6",
        """
        MATCH (:JO {full_id: '주차장법(법률)::제5장::제19조'})-[r:DELEGATES_TO]->(:JO {full_id: '주차장법(시행령)::제6조'})
        RETURN count(r) AS count
        """,
        one_row_value("count", 1),
    ),
    Check(
        "decree_6_detailed_by_rule_11",
        """
        MATCH (:JO {full_id: '주차장법(시행령)::제6조'})-[r:DETAILED_BY]->(:JO {full_id: '주차장법(시행규칙)::제11조'})
        RETURN count(r) AS count
        """,
        one_row_value("count", 1),
    ),
    Check(
        "appendix_1_structured_seed_loaded",
        """
        MATCH (ap:APPENDIX {full_id: '주차장법(시행령)::별표1'})
        RETURN ap.title AS title, ap.content_status AS content_status,
               ap.content_status IN ['needs_structured_table_parse', 'structured_seed_loaded'] AS ok
        """,
        all_true("ok"),
    ),
    Check(
        "decree_6_has_appendix_1",
        """
        MATCH (:HANG {full_id: '주차장법(시행령)::제6조::1'})-[r:HAS_APPENDIX]->(:APPENDIX {full_id: '주차장법(시행령)::별표1'})
        RETURN count(r) AS count
        """,
        one_row_value("count", 1),
    ),
    Check(
        "parking_domain_exists",
        """
        MATCH (d:Domain {domain_id: 'parking_regulation'})
        RETURN d.domain_name AS domain_name, d.node_count AS node_count
        """,
        min_count("node_count", 198),
    ),
    Check(
        "parking_domain_covers_key_nodes",
        """
        UNWIND [
          '주차장법(법률)::제5장::제19조',
          '주차장법(시행령)::제6조',
          '주차장법(시행규칙)::제11조',
          '주차장법(시행령)::별표1'
        ] AS full_id
        MATCH (n {full_id: full_id})-[:BELONGS_TO_DOMAIN]->(:Domain {domain_id: 'parking_regulation'})
        RETURN full_id, true AS ok
        ORDER BY full_id
        """,
        exact_rows(4),
    ),
    Check(
        "parking_layout_rules_loaded",
        """
        MATCH (:JO {full_id: '주차장법(시행규칙)::제11조'})-[:HAS_LAYOUT_RULE]->(r:ParkingLayoutRule)
        RETURN count(r) AS count
        """,
        one_row_value("count", 7),
    ),
    Check(
        "parking_layout_rules_source_links",
        """
        MATCH (r:ParkingLayoutRule)
        WHERE r.rule_id IN [
          'parking_layout_rule_road_as_aisle_undivided_under_12m',
          'parking_layout_rule_road_as_aisle_sidewalk_12m_perpendicular_under_5',
          'parking_layout_rule_tandem_under_5',
          'parking_layout_rule_attached_entrance_width'
        ]
        OPTIONAL MATCH (r)-[:DERIVED_FROM]->(source)
        RETURN r.rule_id AS rule_id, source.full_id IS NOT NULL AS ok
        ORDER BY rule_id
        """,
        all_true("ok"),
    ),
    Check(
        "small_attached_road_as_aisle_rule",
        """
        MATCH (r:ParkingLayoutRule {rule_id: 'parking_layout_rule_road_as_aisle_undivided_under_12m'})
        RETURN r.max_total_spaces AS max_total_spaces,
               r.max_road_width_m_exclusive AS max_road_width_m_exclusive,
               r.min_aisle_width_counting_road_m AS min_aisle_width_counting_road_m,
               r.min_parallel_aisle_width_counting_road_m AS min_parallel_aisle_width_counting_road_m
        """,
        lambda rows: (
            bool(rows)
            and rows[0].get("max_total_spaces") == 8
            and rows[0].get("max_road_width_m_exclusive") == 12.0
            and rows[0].get("min_aisle_width_counting_road_m") == 6.0
            and rows[0].get("min_parallel_aisle_width_counting_road_m") == 4.0,
            f"row={rows[0] if rows else None}",
        ),
    ),
    Check(
        "small_attached_tandem_rule",
        """
        MATCH (r:ParkingLayoutRule {rule_id: 'parking_layout_rule_tandem_under_5'})
        RETURN r.max_total_spaces AS max_total_spaces,
               r.max_depth_from_aisle AS max_depth_from_aisle
        """,
        lambda rows: (
            bool(rows)
            and rows[0].get("max_total_spaces") == 5
            and rows[0].get("max_depth_from_aisle") == 2,
            f"row={rows[0] if rows else None}",
        ),
    ),
    Check(
        "parking_keyword_search_smoke",
        """
        MATCH (n)-[:BELONGS_TO_DOMAIN]->(:Domain {domain_id: 'parking_regulation'})
        WHERE coalesce(n.title, '') CONTAINS '부설주차장'
           OR coalesce(n.content, '') CONTAINS '부설주차장'
        RETURN count(DISTINCT n) AS count
        """,
        min_count("count", 20),
    ),
    Check(
        "accessibility_law_roots",
        """
        MATCH (l:LAW)
        WHERE l.full_id IN [
          '장애인ㆍ노인ㆍ임산부 등의 편의증진 보장에 관한 법률(법률)',
          '장애인ㆍ노인ㆍ임산부 등의 편의증진 보장에 관한 법률(시행령)',
          '장애인ㆍ노인ㆍ임산부 등의 편의증진 보장에 관한 법률(시행규칙)'
        ]
        RETURN l.full_id AS full_id, l.law_type AS law_type
        ORDER BY full_id
        """,
        exact_rows(3),
    ),
    Check(
        "accessible_parking_domain_exists",
        """
        MATCH (d:Domain {domain_id: 'accessible_parking_regulation'})
        RETURN d.domain_name AS domain_name, d.node_count AS node_count
        """,
        min_count("node_count", 12),
    ),
    Check(
        "accessible_stall_dimension_text",
        """
        MATCH (n:HO {full_id: '주차장법(시행규칙)::제3조::1::제2호'})
        RETURN n.content CONTAINS '장애인전용' AND
               n.content CONTAINS '3.3미터 이상' AND
               n.content CONTAINS '5.0미터 이상' AS ok
        """,
        all_true("ok"),
    ),
    Check(
        "accessible_stall_dimension_semantic_edge",
        """
        MATCH (:JO {full_id: '주차장법(시행규칙)::제3조'})-[r:DEFINES_STALL_DIMENSION]->(:HO {full_id: '주차장법(시행규칙)::제3조::1::제2호'})
        RETURN count(r) AS count,
               collect(r.width_m)[0] AS width_m,
               collect(r.length_m)[0] AS length_m
        """,
        lambda rows: (
            bool(rows)
            and rows[0].get("count") == 1
            and float(rows[0].get("width_m")) == 3.3
            and float(rows[0].get("length_m")) == 5.0,
            f"row={rows[0] if rows else None}, expected width_m=3.3 length_m=5.0",
        ),
    ),
    Check(
        "accessible_road_parking_threshold",
        """
        MATCH (:HO {full_id: '주차장법(시행규칙)::제4조::1::제8호'})-[r:HAS_THRESHOLD]->(:MOK {full_id: '주차장법(시행규칙)::제4조::1::제8호::가목'})
        RETURN count(r) AS count, collect(r.required_min_spaces)[0] AS required_min_spaces
        """,
        lambda rows: (
            bool(rows)
            and rows[0].get("count") == 1
            and rows[0].get("required_min_spaces") == 1,
            f"row={rows[0] if rows else None}, expected required_min_spaces=1",
        ),
    ),
    Check(
        "accessible_road_parking_ratio_range",
        """
        MATCH (:HO {full_id: '주차장법(시행규칙)::제4조::1::제8호'})-[r:HAS_RATIO_RANGE]->(:MOK {full_id: '주차장법(시행규칙)::제4조::1::제8호::나목'})
        RETURN count(r) AS count, collect(r.min_percent)[0] AS min_percent, collect(r.max_percent)[0] AS max_percent
        """,
        lambda rows: (
            bool(rows)
            and rows[0].get("count") == 1
            and rows[0].get("min_percent") == 2
            and rows[0].get("max_percent") == 4,
            f"row={rows[0] if rows else None}, expected min_percent=2 max_percent=4",
        ),
    ),
    Check(
        "accessibility_article_chain",
        """
        MATCH (:JO {full_id: '장애인ㆍ노인ㆍ임산부 등의 편의증진 보장에 관한 법률(법률)::제8조'})-[r1:DELEGATES_TO]->(:JO {full_id: '장애인ㆍ노인ㆍ임산부 등의 편의증진 보장에 관한 법률(시행령)::제4조'})
        MATCH (:JO {full_id: '장애인ㆍ노인ㆍ임산부 등의 편의증진 보장에 관한 법률(시행령)::제4조'})-[r2:DETAILED_BY]->(:JO {full_id: '장애인ㆍ노인ㆍ임산부 등의 편의증진 보장에 관한 법률(시행규칙)::제2조'})
        RETURN count(DISTINCT r1) AS delegates_to, count(DISTINCT r2) AS detailed_by
        """,
        lambda rows: (
            bool(rows)
            and rows[0].get("delegates_to") == 1
            and rows[0].get("detailed_by") == 1,
            f"row={rows[0] if rows else None}, expected delegates_to=1 detailed_by=1",
        ),
    ),
    Check(
        "accessibility_appendix_structured_seed_loaded",
        """
        MATCH (:HANG {full_id: '장애인ㆍ노인ㆍ임산부 등의 편의증진 보장에 관한 법률(시행규칙)::제2조::1'})-[r:HAS_APPENDIX]->(ap:APPENDIX {full_id: '장애인ㆍ노인ㆍ임산부 등의 편의증진 보장에 관한 법률(시행규칙)::별표1'})
        RETURN count(r) AS count, ap.content_status AS content_status
        """,
        lambda rows: (
            bool(rows)
            and rows[0].get("count") == 1
            and rows[0].get("content_status") in ["needs_structured_table_parse", "structured_seed_loaded"],
            f"row={rows[0] if rows else None}, expected appendix node",
        ),
    ),
    Check(
        "parking_appendix_requirement_rules_loaded",
        """
        MATCH (:APPENDIX {full_id: '주차장법(시행령)::별표1'})-[:HAS_REQUIREMENT_RULE]->(r:ParkingRequirementRule)
        RETURN count(r) AS count
        """,
        min_count("count", 11),
    ),
    Check(
        "parking_appendix_rule_ids_unique",
        """
        MATCH (r:ParkingRequirementRule)
        WITH r.rule_id AS rule_id, count(r) AS count
        WHERE count > 1
        RETURN count(*) AS duplicate_count
        """,
        one_row_value("duplicate_count", 0),
    ),
    Check(
        "accessibility_appendix_rule_ids_unique",
        """
        MATCH (r:AccessibleParkingFacilityRule)
        WITH r.rule_id AS rule_id, count(r) AS count
        WHERE count > 1
        RETURN count(*) AS duplicate_count
        """,
        one_row_value("duplicate_count", 0),
    ),
    Check(
        "appendix_full_ids_unique",
        """
        MATCH (a:APPENDIX)
        WITH a.full_id AS full_id, count(a) AS count
        WHERE count > 1
        RETURN count(*) AS duplicate_count
        """,
        one_row_value("duplicate_count", 0),
    ),
    Check(
        "parking_appendix_core_area_rules",
        """
        MATCH (r:ParkingRequirementRule)
        WHERE r.rule_id IN [
          'parking_appendix1_row_01',
          'parking_appendix1_row_02',
          'parking_appendix1_row_03',
          'parking_appendix1_row_07',
          'parking_appendix1_row_08',
          'parking_appendix1_row_09',
          'parking_appendix1_row_10',
          'parking_appendix1_row_11'
        ]
        RETURN collect(r.spaces_per) AS values
        """,
        lambda rows: (
            bool(rows)
            and set(rows[0].get("values", [])) >= {100.0, 150.0, 200.0, 300.0, 350.0, 400.0},
            f"row={rows[0] if rows else None}, expected area divisors",
        ),
    ),
    Check(
        "parking_appendix_rounding_interpretation",
        """
        MATCH (r:ParkingRequirementRule)
        WHERE r.rule_id IN [
          'parking_appendix1_row_01',
          'parking_appendix1_row_02',
          'parking_appendix1_row_03',
          'parking_appendix1_row_04',
          'parking_appendix1_row_06',
          'parking_appendix1_row_07',
          'parking_appendix1_row_08',
          'parking_appendix1_row_09',
          'parking_appendix1_row_10',
          'parking_appendix1_row_11'
        ]
        RETURN count(r) AS count,
               sum(CASE WHEN r.formula STARTS WITH 'ceil(' THEN 1 ELSE 0 END) AS ceil_count,
               sum(CASE WHEN r.rounding_rule = 'appendix_note_6_half_up_total_under_one_zero' THEN 1 ELSE 0 END) AS note6_count,
               sum(CASE WHEN r.rounding_rule_detail CONTAINS '0.5 이상' THEN 1 ELSE 0 END) AS detail_count
        """,
        lambda rows: (
            bool(rows)
            and rows[0].get("count") == 10
            and rows[0].get("ceil_count") == 0
            and rows[0].get("note6_count") == 10
            and rows[0].get("detail_count") == 10,
            f"row={rows[0] if rows else None}, expected note 6 rounding interpretation and no ceil formulas",
        ),
    ),
    Check(
        "parking_appendix_row_04_single_house_formula",
        """
        MATCH (r:ParkingRequirementRule {rule_id: 'parking_appendix1_row_04'})
        RETURN r.min_area_m2_exclusive AS min_area_m2_exclusive,
               r.threshold_area_m2 AS threshold_area_m2,
               r.base_spaces AS base_spaces,
               r.increment_area_m2 AS increment_area_m2,
               r.formula_detail CONTAINS '50제곱미터 초과' AS has_50_threshold,
               r.formula_detail CONTAINS '150제곱미터 초과' AS has_150_formula
        """,
        lambda rows: (
            bool(rows)
            and float(rows[0].get("min_area_m2_exclusive")) == 50.0
            and float(rows[0].get("threshold_area_m2")) == 150.0
            and float(rows[0].get("base_spaces")) == 1.0
            and float(rows[0].get("increment_area_m2")) == 100.0
            and rows[0].get("has_50_threshold")
            and rows[0].get("has_150_formula"),
            f"row={rows[0] if rows else None}, expected single-house thresholds/formula",
        ),
    ),
    Check(
        "parking_appendix_row_05_external_housing_rule",
        """
        MATCH (r:ParkingRequirementRule {rule_id: 'parking_appendix1_row_05'})
        RETURN r.requires_external_rule AS requires_external_rule,
               r.external_reference AS external_reference,
               r.area_method AS area_method,
               r.rounding_rule AS rounding_rule
        """,
        lambda rows: (
            bool(rows)
            and rows[0].get("requires_external_rule") is True
            and rows[0].get("external_reference") == "주택건설기준 등에 관한 규정 제27조제1항"
            and rows[0].get("area_method") == "공동주택 전용면적 산정방법"
            and rows[0].get("rounding_rule") == "external_reference_article_27_1",
            f"row={rows[0] if rows else None}, expected delegated housing rule metadata",
        ),
    ),
    Check(
        "parking_appendix_row_06_specific_unit_rule",
        """
        MATCH (r:ParkingRequirementRule {rule_id: 'parking_appendix1_row_06'})
        RETURN r.specific_units_json CONTAINS '골프장' AS has_golf,
               r.specific_units_json CONTAINS '옥외수영장' AS has_pool,
               r.formula_detail CONTAINS '관람장 정원 100명당 1대' AS has_spectator
        """,
        lambda rows: (
            bool(rows)
            and rows[0].get("has_golf")
            and rows[0].get("has_pool")
            and rows[0].get("has_spectator"),
            f"row={rows[0] if rows else None}, expected facility-specific unit details",
        ),
    ),
    Check(
        "seoul_parking_ordinance_loaded",
        """
        MATCH (o:LocalOrdinance {ordinance_id: 'seoul_parking_ordinance'})-[:HAS_REQUIREMENT_RULE]->(r:LocalParkingRequirementRule)
        RETURN o.jurisdiction_name AS jurisdiction_name,
               o.pnu_prefix AS pnu_prefix,
               o.effective_date AS effective_date,
               count(r) AS local_rule_count
        """,
        lambda rows: (
            bool(rows)
            and rows[0].get("jurisdiction_name") == "서울특별시"
            and rows[0].get("pnu_prefix") == "11"
            and rows[0].get("effective_date") == "2026-03-30"
            and rows[0].get("local_rule_count") >= 14,
            f"row={rows[0] if rows else None}, expected Seoul ordinance metadata and local rules",
        ),
    ),
    Check(
        "seoul_parking_ordinance_override_links",
        """
        MATCH (r:LocalParkingRequirementRule)-[:OVERRIDES]->(base:ParkingRequirementRule)
        WHERE r.source_ordinance = 'seoul_parking_ordinance'
        RETURN count(r) AS override_count,
               count(DISTINCT base.rule_id) AS base_rule_count
        """,
        lambda rows: (
            bool(rows)
            and rows[0].get("override_count") >= 14
            and rows[0].get("base_rule_count") >= 10,
            f"row={rows[0] if rows else None}, expected local override relationships",
        ),
    ),
    Check(
        "seoul_parking_core_area_rules",
        """
        MATCH (r:LocalParkingRequirementRule)
        WHERE r.rule_id IN [
          'seoul_parking_appendix2_row_01',
          'seoul_parking_appendix2_row_02',
          'seoul_parking_appendix2_row_03',
          'seoul_parking_appendix2_row_07',
          'seoul_parking_appendix2_row_08',
          'seoul_parking_appendix2_row_09',
          'seoul_parking_appendix2_row_10_other'
        ]
        RETURN collect(r.spaces_per) AS values
        """,
        lambda rows: (
            bool(rows)
            and set(rows[0].get("values", [])) >= {67.0, 100.0, 134.0, 200.0, 233.0, 267.0, 400.0},
            f"row={rows[0] if rows else None}, expected Seoul ordinance area divisors",
        ),
    ),
    Check(
        "seoul_parking_row_05_local_housing_minimum",
        """
        MATCH (r:LocalParkingRequirementRule {rule_id: 'seoul_parking_appendix2_row_05'})
        RETURN r.requires_external_rule AS requires_external_rule,
               r.external_reference AS external_reference,
               r.local_min_spaces_per_household AS local_min_spaces_per_household,
               r.local_min_spaces_under_30m2 AS local_min_spaces_under_30m2,
               r.local_min_spaces_under_60m2 AS local_min_spaces_under_60m2
        """,
        lambda rows: (
            bool(rows)
            and rows[0].get("requires_external_rule") is True
            and rows[0].get("external_reference") == "주택건설기준 등에 관한 규정 제27조제1항"
            and float(rows[0].get("local_min_spaces_per_household")) == 1.0
            and float(rows[0].get("local_min_spaces_under_30m2")) == 0.5
            and float(rows[0].get("local_min_spaces_under_60m2")) == 0.8,
            f"row={rows[0] if rows else None}, expected Seoul housing local minimum metadata",
        ),
    ),
    Check(
        "accessibility_appendix_rules_loaded",
        """
        MATCH (:APPENDIX {full_id: '장애인ㆍ노인ㆍ임산부 등의 편의증진 보장에 관한 법률(시행규칙)::별표1'})-[:HAS_ACCESSIBILITY_RULE]->(r:AccessibleParkingFacilityRule)
        RETURN count(r) AS count
        """,
        min_count("count", 4),
    ),
    Check(
        "accessibility_appendix_access_route_values",
        """
        MATCH (r:AccessibleParkingFacilityRule {rule_id: 'accessibility_appendix1_access_aisle'})
        RETURN r.min_route_width_m AS min_route_width_m,
               r.requires_no_height_difference AS requires_no_height_difference,
               r.separated_from_vehicle_path AS separated_from_vehicle_path
        """,
        lambda rows: (
            bool(rows)
            and float(rows[0].get("min_route_width_m")) == 1.2
            and rows[0].get("requires_no_height_difference") is True
            and rows[0].get("separated_from_vehicle_path") is True,
            f"row={rows[0] if rows else None}, expected access route width/no-height/path separation",
        ),
    ),
    Check(
        "accessibility_appendix_surface_values",
        """
        MATCH (r:AccessibleParkingFacilityRule {rule_id: 'accessibility_appendix1_surface'})
        RETURN r.max_slope AS max_slope,
               r.max_slope_ratio AS max_slope_ratio,
               r.max_slope_requirement_level AS max_slope_requirement_level,
               r.requires_no_height_difference AS requires_no_height_difference,
               r.slip_resistant AS slip_resistant,
               r.requirement_level AS requirement_level
        """,
        lambda rows: (
            bool(rows)
            and float(rows[0].get("max_slope")) == 0.02
            and rows[0].get("max_slope_ratio") == "1/50"
            and rows[0].get("max_slope_requirement_level") == "recommended"
            and rows[0].get("requires_no_height_difference") is True
            and rows[0].get("slip_resistant") is True
            and rows[0].get("requirement_level") == "mixed",
            f"row={rows[0] if rows else None}, expected mandatory surface values with recommended slope flag",
        ),
    ),
    Check(
        "accessibility_appendix_marking_values",
        """
        MATCH (r:AccessibleParkingFacilityRule {rule_id: 'accessibility_appendix1_markings'})
        RETURN r.floor_mark_width_m AS floor_mark_width_m,
               r.floor_mark_length_m AS floor_mark_length_m,
               r.stall_line_mark_width_m AS stall_line_mark_width_m,
               r.stall_line_mark_length_m AS stall_line_mark_length_m,
               r.sign_width_m AS sign_width_m,
               r.sign_height_m AS sign_height_m,
               r.sign_install_height_m AS sign_install_height_m
        """,
        lambda rows: (
            bool(rows)
            and float(rows[0].get("floor_mark_width_m")) == 1.3
            and float(rows[0].get("floor_mark_length_m")) == 1.5
            and float(rows[0].get("stall_line_mark_width_m")) == 0.5
            and float(rows[0].get("stall_line_mark_length_m")) == 0.58
            and float(rows[0].get("sign_width_m")) == 0.7
            and float(rows[0].get("sign_height_m")) == 0.6
            and float(rows[0].get("sign_install_height_m")) == 1.5,
            f"row={rows[0] if rows else None}, expected marking/sign values",
        ),
    ),
    Check(
        "accessibility_appendix_stall_rule_values",
        """
        MATCH (r:AccessibleParkingFacilityRule {rule_id: 'accessibility_appendix1_parking_space'})
        RETURN r.width_m AS width_m, r.length_m AS length_m,
               r.parallel_width_m AS parallel_width_m, r.parallel_length_m AS parallel_length_m
        """,
        lambda rows: (
            bool(rows)
            and float(rows[0].get("width_m")) == 3.3
            and float(rows[0].get("length_m")) == 5.0
            and float(rows[0].get("parallel_width_m")) == 2.0
            and float(rows[0].get("parallel_length_m")) == 6.0,
            f"row={rows[0] if rows else None}, expected accessible appendix stall values",
        ),
    ),
]


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("--uri", default=os.getenv("NEO4J_URI", "bolt://localhost:7687"))
    parser.add_argument("--user", default=os.getenv("NEO4J_USER", "neo4j"))
    parser.add_argument("--password", default=os.getenv("NEO4J_PASSWORD", ""))
    args = parser.parse_args()

    driver = GraphDatabase.driver(args.uri, auth=(args.user, args.password))
    failures: list[str] = []

    try:
        with driver.session() as session:
            for check in CHECKS:
                rows = [dict(row) for row in session.run(check.query)]
                passed, detail = check.validate(rows)
                status = "PASS" if passed else "FAIL"
                print(f"[{status}] {check.name}: {detail}")
                if not passed:
                    failures.append(check.name)
    finally:
        driver.close()

    print(f"\nsummary: {len(CHECKS) - len(failures)}/{len(CHECKS)} passed")
    if failures:
        print("failures:", ", ".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
