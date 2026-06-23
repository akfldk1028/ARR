#!/usr/bin/env python3
"""Smoke-test the MAAS legal design agent flow through AG-light bus."""

from __future__ import annotations

import argparse
import json
import time
import uuid
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


DEFAULT_BASE_URL = "http://127.0.0.1:8200"
DEFAULT_TEAM_JSON = Path(__file__).resolve().parents[4] / "JSON_MODULES" / "teams" / "041_MAAS_Legal_Design_Team.json"

FLOW_STEPS = [
    ("user", "design_orchestrator", "PNU/design 후보를 받으면 법규-주차-매스-검토 순서로 협업을 시작해."),
    ("design_orchestrator", "law_graph_agent", "Graph DB 법규 근거와 누락 evidence를 rule_id 중심으로 확인해."),
    ("law_graph_agent", "parking_agent", "법규 검토 결과를 받아 주차 산정 대수와 연접/차로 조건을 검토해."),
    ("parking_agent", "maas_geometry_agent", "주차 조건을 반영해 가능한 MAAS 매스 repair operation을 제안해."),
    ("maas_geometry_agent", "review_agent", "법규/주차/매스 evidence를 묶어 통과/보류/실패 리스크를 판정해."),
    ("review_agent", "design_orchestrator", "최종 판단과 다음 수정 지시를 사용자에게 전달할 형태로 정리해."),
]


def request_json(method: str, url: str, payload: dict[str, Any] | None = None) -> Any:
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = Request(
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    with urlopen(request, timeout=8) as response:
        raw = response.read().decode("utf-8")
    return json.loads(raw) if raw else None


def load_team_agents(team_json: Path) -> set[str]:
    data = json.loads(team_json.read_text(encoding="utf-8"))
    participants = data.get("config", {}).get("participants", [])
    return {
        participant.get("config", {}).get("name")
        for participant in participants
        if participant.get("config", {}).get("name")
    }


def send_step(base_url: str, run_id: str, scenario: str, index: int, source: str, target: str, message: str) -> None:
    request_json("POST", f"{base_url}/bus/send", {
        "from_agent": source,
        "to_agent": target,
        "message": message,
        "metadata": {
            "source": "arr_ag_light_agent_flow_cli",
            "run_id": run_id,
            "scenario": scenario,
            "step": index,
        },
    })


def fetch_run_events(base_url: str, run_id: str, limit: int) -> list[dict[str, Any]]:
    query = urlencode({"limit": limit})
    events = request_json("GET", f"{base_url}/bus/log?{query}")
    return [
        event for event in events
        if isinstance(event, dict)
        and isinstance(event.get("metadata"), dict)
        and event["metadata"].get("run_id") == run_id
    ]


def run_once(base_url: str, scenario: str, delay: float, limit: int) -> dict[str, Any]:
    run_id = f"arr-ag-light-{uuid.uuid4().hex[:12]}"
    for index, (source, target, message) in enumerate(FLOW_STEPS, start=1):
        send_step(base_url, run_id, scenario, index, source, target, message)
        if delay:
            time.sleep(delay)

    events = fetch_run_events(base_url, run_id, limit)
    observed = {(event.get("from_agent"), event.get("to_agent")) for event in events}
    expected = {(source, target) for source, target, _ in FLOW_STEPS}
    missing = sorted([f"{source}->{target}" for source, target in expected - observed])
    return {
        "run_id": run_id,
        "success": not missing,
        "expected_steps": len(FLOW_STEPS),
        "observed_steps": len(observed & expected),
        "missing": missing,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run AG-light MAAS agent-to-agent bus smoke tests.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--team-json", type=Path, default=DEFAULT_TEAM_JSON)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--scenario", default="maas_legal_design_agent_flow")
    parser.add_argument("--delay", type=float, default=0.05)
    parser.add_argument("--json-output", type=Path)
    args = parser.parse_args()

    try:
      health = request_json("GET", f"{args.base_url}/health")
    except (URLError, TimeoutError, OSError) as exc:
      print(f"AG-light not reachable: {args.base_url} ({exc})")
      return 2

    team_agents = load_team_agents(args.team_json)
    required_agents = {agent for step in FLOW_STEPS for agent in step[:2] if agent not in {"user", "design_orchestrator"}}
    missing_agents = sorted(required_agents - team_agents)
    if missing_agents:
        print(f"Team JSON missing agents: {', '.join(missing_agents)}")
        return 3

    runs = [run_once(args.base_url, args.scenario, args.delay, max(120, args.runs * len(FLOW_STEPS) + 80)) for _ in range(args.runs)]
    success_count = sum(1 for run in runs if run["success"])
    success_rate = success_count / args.runs * 100 if args.runs else 0.0
    result = {
        "base_url": args.base_url,
        "service_status": health.get("status"),
        "team_json": str(args.team_json),
        "scenario": args.scenario,
        "runs": args.runs,
        "success": success_count,
        "success_rate": success_rate,
        "failures": [run for run in runs if not run["success"]],
        "run_results": runs,
    }

    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print("AG-light agent flow CLI")
    print(f"runs: {args.runs}")
    print(f"success: {success_count}")
    print(f"success_rate: {success_rate:.1f}%")
    print(f"failures: {len(result['failures'])}")
    if result["failures"]:
        for failure in result["failures"]:
            print(f"- {failure['run_id']}: missing {', '.join(failure['missing'])}")
    return 0 if success_count == args.runs else 1


if __name__ == "__main__":
    raise SystemExit(main())
