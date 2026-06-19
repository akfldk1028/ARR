"""Tests for interactive mass patch planning."""

from django.test import TestCase

from design.services.interactive_patch import build_interactive_patch_plan
from design.services.interactive_apply import build_interactive_preview


class InteractivePatchServiceTest(TestCase):
    def test_north_stepback_request_returns_dry_run_candidate(self):
        result = build_interactive_patch_plan(
            "북측 상부를 4단으로 자연스럽게 후퇴시켜줘. 용적률은 5% 이상 잃지 말고.",
            selected_design={"id": 3, "algorithm": "tower_podium"},
            mass_geojson={"properties": {"step_floor": 8, "far": 610}},
            constraints=[{"name": "height"}],
        )

        self.assertEqual(result["mode"], "dry_run")
        self.assertEqual(result["selected_design_id"], 3)
        self.assertIn("north_sunlight_stepback", result["interpreted_intents"])
        self.assertEqual(result["candidates"][0]["id"], "smooth-north-stepback")
        self.assertIn("north_sunlight", result["candidates"][0]["constraints"])

    def test_core_flow_request_does_not_misread_direction_as_east(self):
        result = build_interactive_patch_plan(
            "코어 동선이 답답해. 외곽으로 붙일 수 있는지 봐줘.",
            selected_design={"id": 0, "algorithm": "subtractive"},
        )

        self.assertEqual(result["selected_design_id"], 0)
        self.assertIn("core_relocation", result["interpreted_intents"])
        core = next(c for c in result["candidates"] if c["id"] == "move-core-to-edge")
        self.assertEqual(core["patch"]["target"], "edge")

    def test_explicit_core_direction_is_preserved(self):
        result = build_interactive_patch_plan(
            "코어를 동측 외곽으로 붙여줘.",
            selected_design={"id": 5},
        )

        core = next(c for c in result["candidates"] if c["id"] == "move-core-to-edge")
        self.assertEqual(core["patch"]["target"], "east")


class InteractivePatchEndpointTest(TestCase):
    def _site_polygon(self):
        return {
            "type": "Polygon",
            "coordinates": [[
                [127.0000, 37.0000],
                [127.0010, 37.0000],
                [127.0010, 37.0010],
                [127.0000, 37.0010],
                [127.0000, 37.0000],
            ]],
        }

    def _additive_inputs(self):
        inputs = []
        for _ in range(5):
            inputs.extend([[0.0], [0.0], [20.0], [18.0], [0.0]])
        inputs.extend([[5.0], [0.0], [0.9], [0.7]])
        return inputs

    def test_endpoint_returns_patch_candidates(self):
        response = self.client.post(
            "/design/interactive/patch/",
            data={
                "message": "도로 쪽 저층부를 포디움처럼 더 강하게 만들고 코어는 동측으로 붙여줘.",
                "selected_design": {"id": 7, "algorithm": "tower_podium"},
                "mass_geojson": {"properties": {"far": 620, "bcr": 52, "height": 38}},
                "constraints": [{"name": "far"}, {"name": "height"}],
            },
            content_type="application/json",
            HTTP_HOST="127.0.0.1",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["mode"], "dry_run")
        self.assertEqual(data["selected_design_id"], 7)
        self.assertIn("road_side_podium", data["interpreted_intents"])
        self.assertIn("core_relocation", data["interpreted_intents"])
        self.assertEqual(
            [c["id"] for c in data["candidates"]],
            ["strengthen-road-podium", "move-core-to-edge"],
        )

    def test_endpoint_requires_message(self):
        response = self.client.post(
            "/design/interactive/patch/",
            data={"message": "   "},
            content_type="application/json",
            HTTP_HOST="127.0.0.1",
        )

        self.assertEqual(response.status_code, 400)

    def test_preview_endpoint_returns_candidate_geometry(self):
        patch_plan = build_interactive_patch_plan(
            "북측 상부를 부드럽게 후퇴시켜줘.",
            selected_design={"id": 0, "inputs": self._additive_inputs(), "algorithm": "additive"},
        )

        response = self.client.post(
            "/design/interactive/preview/",
            data={
                "patch_plan": patch_plan,
                "selected_design": {"id": 0, "inputs": self._additive_inputs(), "algorithm": "additive"},
                "site_polygon": self._site_polygon(),
                "site_area_m2": 9800.0,
                "constraints": [{"name": "far", "type": "Constraint", "Requirement": "Less than", "val": 300, "unit": "%"}],
                "building_type": "공동주택",
                "algorithm": "additive",
            },
            content_type="application/json",
            HTTP_HOST="127.0.0.1",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["mode"], "preview")
        self.assertEqual(data["selected_design_id"], 0)
        self.assertGreaterEqual(len(data["candidates"]), 1)
        self.assertEqual(data["candidates"][0]["mass_geojson"]["type"], "Feature")


class InteractivePreviewServiceTest(TestCase):
    def _site_polygon(self):
        return {
            "type": "Polygon",
            "coordinates": [[
                [127.0000, 37.0000],
                [127.0010, 37.0000],
                [127.0010, 37.0010],
                [127.0000, 37.0010],
                [127.0000, 37.0000],
            ]],
        }

    def _additive_inputs(self):
        inputs = []
        for _ in range(5):
            inputs.extend([[0.0], [0.0], [20.0], [18.0], [0.0]])
        inputs.extend([[5.0], [0.0], [0.9], [0.7]])
        return inputs

    def test_preview_returns_geojson_candidate(self):
        patch_plan = build_interactive_patch_plan(
            "북측 상부를 부드럽게 후퇴시켜줘.",
            selected_design={"id": 0, "inputs": self._additive_inputs(), "algorithm": "additive"},
            mass_geojson={"properties": {"step_floor": 4}},
        )

        result = build_interactive_preview(
            patch_plan=patch_plan,
            selected_design={"id": 0, "inputs": self._additive_inputs(), "algorithm": "additive"},
            site_polygon_geojson=self._site_polygon(),
            site_area_m2=9800.0,
            constraints=[{"name": "far", "type": "Constraint", "Requirement": "Less than", "val": 300, "unit": "%"}],
            building_type="공동주택",
            algorithm="additive",
        )

        self.assertEqual(result["mode"], "preview")
        self.assertEqual(result["selected_design_id"], 0)
        self.assertGreaterEqual(len(result["candidates"]), 1)
        first = result["candidates"][0]
        self.assertIn("metrics", first)
        self.assertIsNotNone(first["mass_geojson"])
        self.assertEqual(first["mass_geojson"]["type"], "Feature")
