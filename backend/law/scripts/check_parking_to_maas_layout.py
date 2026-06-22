"""
Check Graph DB parking requirements against MAAS parking layout candidates.

This is an integration smoke test:

PNU + parking rule scenario
-> Graph DB rule selection
-> required parking count
-> MAAS parking strategy
-> deterministic stall-coordinate layout candidate
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from neo4j import GraphDatabase
from shapely.geometry import box

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from design.maas.parking_strategy import infer_parking_strategy
from law.scripts.check_parking_counts import (
    _load_rules,
    _select_rule,
    calculate_accessible_spaces,
    calculate_required_spaces,
)


@dataclass(frozen=True)
class MaasParkingLayoutCase:
    name: str
    pnu: str
    rule_id: str
    metric: str
    metric_value: float
    building_type: str
    site_area_m2: float
    footprint_width_m: float
    footprint_depth_m: float
    site_width_m: float
    site_depth_m: float
    floors: int
    road_context: dict[str, Any] | None
    expected_status: str
    expected_required_spaces: int | None
    expected_layout_status: str | None = "pass"
    expected_min_provided_spaces: int = 0


CASES = [
    MaasParkingLayoutCase(
        name="gangnam_single_house_one_space_road_as_aisle",
        pnu="1168011800104670003",
        rule_id="parking_appendix1_row_04",
        metric="facility_area_m2",
        metric_value=51.0,
        building_type="단독주택",
        site_area_m2=90.0,
        footprint_width_m=5.0,
        footprint_depth_m=5.0,
        site_width_m=10.0,
        site_depth_m=9.0,
        floors=1,
        road_context={"road_width_m": 6.0, "has_sidewalk_separation": False},
        expected_status="computed",
        expected_required_spaces=1,
        expected_min_provided_spaces=1,
    ),
    MaasParkingLayoutCase(
        name="gangnam_row2_two_spaces_tandem_small_attached",
        pnu="1168011800100910005",
        rule_id="parking_appendix1_row_02",
        metric="facility_area_m2",
        metric_value=150.0,
        building_type="근린생활시설",
        site_area_m2=140.0,
        footprint_width_m=5.0,
        footprint_depth_m=10.0,
        site_width_m=14.0,
        site_depth_m=10.0,
        floors=3,
        road_context={"road_width_m": 6.0, "has_sidewalk_separation": False},
        expected_status="computed",
        expected_required_spaces=2,
        expected_min_provided_spaces=2,
    ),
    MaasParkingLayoutCase(
        name="songpa_warehouse_sixteen_spaces_internal_double_loaded",
        pnu="1171010100100010000",
        rule_id="parking_appendix1_row_08",
        metric="facility_area_m2",
        metric_value=4200.0,
        building_type="창고시설",
        site_area_m2=1000.0,
        footprint_width_m=40.0,
        footprint_depth_m=16.0,
        site_width_m=50.0,
        site_depth_m=20.0,
        floors=1,
        road_context=None,
        expected_status="computed",
        expected_required_spaces=16,
        expected_min_provided_spaces=16,
    ),
    MaasParkingLayoutCase(
        name="busan_fallback_zero_spaces_no_layout_pressure",
        pnu="2611010100100010000",
        rule_id="parking_appendix1_row_08",
        metric="facility_area_m2",
        metric_value=399.0,
        building_type="창고시설",
        site_area_m2=300.0,
        footprint_width_m=10.0,
        footprint_depth_m=10.0,
        site_width_m=20.0,
        site_depth_m=15.0,
        floors=1,
        road_context=None,
        expected_status="computed",
        expected_required_spaces=0,
        expected_min_provided_spaces=0,
    ),
    MaasParkingLayoutCase(
        name="gangnam_apartment_external_rule_stops_before_layout",
        pnu="1168011800104170004",
        rule_id="parking_appendix1_row_05",
        metric="household_or_unit_area",
        metric_value=850.0,
        building_type="공동주택",
        site_area_m2=250.0,
        footprint_width_m=12.5,
        footprint_depth_m=10.0,
        site_width_m=20.0,
        site_depth_m=12.5,
        floors=2,
        road_context={"road_width_m": 6.0, "has_sidewalk_separation": False},
        expected_status="needs_external_rule",
        expected_required_spaces=None,
        expected_layout_status=None,
    ),
]


def run_checks(uri: str, user: str, password: str) -> int:
    failures: list[str] = []
    driver = GraphDatabase.driver(uri, auth=(user, password))
    try:
        with driver.session() as session:
            rules = _load_rules(session)
            for case in CASES:
                rule = _select_rule(rules, case.pnu, case.rule_id)
                if not rule:
                    print(f"[FAIL] {case.name}: missing rule {case.rule_id}")
                    failures.append(case.name)
                    continue

                calc = calculate_required_spaces(rule, case.metric, case.metric_value)
                required_spaces = calc["required_spaces"]
                accessible = calculate_accessible_spaces(required_spaces)
                ok = (
                    calc["status"] == case.expected_status
                    and required_spaces == case.expected_required_spaces
                )

                layout_status = None
                provided_spaces = None
                placement_mode = None
                selected_strategy = None
                if required_spaces is not None:
                    footprint_area = case.footprint_width_m * case.footprint_depth_m
                    floor_area = case.metric_value
                    props = {
                        "footprint_area": footprint_area,
                        "floor_area": floor_area,
                        "num_floors": case.floors,
                        "bcr": footprint_area / case.site_area_m2 * 100.0,
                        "required_parking_spaces": required_spaces,
                        "required_accessible_parking_spaces": accessible["accessible_min"] or 0,
                        "parking_road_context": case.road_context,
                    }
                    strategy = infer_parking_strategy(
                        props,
                        site_area_m2=case.site_area_m2,
                        building_type=case.building_type,
                        footprint_utm=box(0, 0, case.footprint_width_m, case.footprint_depth_m),
                        site_utm=box(0, 0, case.site_width_m, case.site_depth_m),
                    )
                    selected_strategy = strategy["selected_strategy"]
                    layout = strategy.get("layout_candidate") or {}
                    layout_status = layout.get("status")
                    provided_spaces = layout.get("provided_spaces")
                    placement_mode = layout.get("placement_mode")
                    ok = ok and layout_status == case.expected_layout_status
                    ok = ok and (provided_spaces or 0) >= case.expected_min_provided_spaces
                    ok = ok and all(stall.get("polygon") for stall in layout.get("stalls", []))

                status = "PASS" if ok else "FAIL"
                print(
                    f"[{status}] {case.name}: pnu={case.pnu} selected_rule={rule.get('rule_id')} "
                    f"required={required_spaces} calc_status={calc['status']} accessible={accessible} "
                    f"strategy={selected_strategy} layout_status={layout_status} "
                    f"placement={placement_mode} provided={provided_spaces}"
                )
                if not ok:
                    failures.append(case.name)
    finally:
        driver.close()

    print(f"\nsummary: {len(CASES) - len(failures)}/{len(CASES)} graph-to-maas layout cases passed")
    if failures:
        print("failures:", ", ".join(failures))
        return 1
    return 0


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("--uri", default=os.getenv("NEO4J_URI", "bolt://localhost:7687"))
    parser.add_argument("--user", default=os.getenv("NEO4J_USER", "neo4j"))
    parser.add_argument("--password", default=os.getenv("NEO4J_PASSWORD", ""))
    args = parser.parse_args()
    return run_checks(args.uri, args.user, args.password)


if __name__ == "__main__":
    raise SystemExit(main())
