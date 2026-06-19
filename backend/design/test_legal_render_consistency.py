"""Tests that evaluated legal masses and rendered GeoJSON stay consistent."""

from django.test import TestCase

from design.engine.objects import Design
from design.services.mass_evaluator import evaluate_designs
from design.services.mass_renderer import design_to_geojson
from design.services.site_geometry import geojson_to_polygon, wgs84_to_utm


class LegalRenderConsistencyTest(TestCase):
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

    def _oversized_additive_inputs(self):
        inputs = []
        for _ in range(5):
            inputs.extend([[0.0], [0.0], [90.0], [90.0], [0.0]])
        inputs.extend([[10.0], [0.0], [1.0], [0.8]])
        return inputs

    def test_repaired_evaluation_and_geojson_use_same_bcr_limit(self):
        outputs_def = [
            {"name": "floor_area", "type": "Objective", "Goal": "Maximize"},
            {"name": "daylight_score", "type": "Objective", "Goal": "Maximize"},
            {"name": "bcr", "type": "Constraint", "Requirement": "Less than", "val": 20, "unit": "%"},
            {"name": "far", "type": "Constraint", "Requirement": "Less than", "val": 200, "unit": "%"},
            {"name": "height", "type": "Constraint", "Requirement": "Less than", "val": 50, "unit": "m"},
        ]
        site_polygon = geojson_to_polygon(self._site_polygon())
        site_area_m2 = wgs84_to_utm(site_polygon).area
        design = Design(_id=1, des_num=0, gen_num=0)
        design.set_inputs(self._oversized_additive_inputs())

        evaluated = evaluate_designs(
            [design],
            site_polygon=site_polygon,
            site_area_m2=site_area_m2,
            outputs_def=outputs_def,
            building_type="공동주택",
            algorithm="additive",
            enable_repair=True,
        )[0]
        design.set_outputs(evaluated, outputs_def)

        repaired_geojson = design_to_geojson(
            self._oversized_additive_inputs(),
            site_polygon,
            site_area_m2,
            "공동주택",
            "additive",
            enable_repair=True,
            outputs_def=outputs_def,
        )

        self.assertTrue(design.feasible)
        self.assertIsNotNone(repaired_geojson)
        self.assertLessEqual(repaired_geojson["properties"]["bcr"], 20.1)
        self.assertLessEqual(repaired_geojson["properties"]["far"], 200.1)
