"""Tests for ARR-local MAAS OpenSCAD export."""

import json
import os
import tempfile

from django.core.management import call_command
from django.test import TestCase
from shapely.geometry import Polygon, box
from unittest.mock import patch

from design.maas import export_mass_geojson_to_scad, generate_legal_mass_variants, mass_geojson_to_scad
from design.maas.aesthetic import build_aesthetic_image_job, build_aesthetic_pipeline_result, validate_aesthetic_job
from design.maas.aesthetic.contracts import ProviderResult
from design.maas.aesthetic.projection_assets import attach_facade_panel_assets
from design.maas.aesthetic.projection_bake import attach_baked_projection_assets
from design.maas.aesthetic.projection_export import attach_textured_mesh_assets
from design.maas.aesthetic.renderers import MultiViewReferencePackRenderer, ReferencePngRenderer
from design.maas.grammar import generate_grammar_variants, load_term_ontology, resolve_intent_to_sequence
from design.maas.parking_layout import (
    _drive_entrance_access,
    _solve_grid_parking_layout,
    evaluate_small_attached_parking_relief,
    generate_parking_layout_candidate,
)
from design.maas.parking_requirements import resolve_candidate_parking_requirement
from design.maas.parking_strategy import infer_parking_strategy
from design.maas.training import build_examples_from_design_results, build_sft_examples, evidence_to_review_example, export_sft_seed
from design.models import DesignResult, OptimizationJob


class MaasScadExportServiceTest(TestCase):
    def _base_feature(self):
        return {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [127.0000, 37.0000],
                    [127.0005, 37.0000],
                    [127.0005, 37.0004],
                    [127.0000, 37.0004],
                    [127.0000, 37.0000],
                ]],
            },
            "properties": {
                "height": 18.0,
                "num_floors": 6,
                "floor_height": 3.0,
                "far": 180.0,
                "bcr": 45.0,
                "mass_shape": "additive",
            },
        }

    def test_exports_single_mass_to_scad(self):
        result = export_mass_geojson_to_scad(self._base_feature(), name="test mass")

        self.assertEqual(result["mode"], "maas_scad_export")
        self.assertEqual(result["name"], "test_mass")
        self.assertIn("linear_extrude(height=18.0000)", result["scad_text"])
        self.assertIn("polygon(points=", result["scad_text"])
        self.assertFalse(result["metadata"]["has_stepback"])

    def test_exports_stepback_as_two_extrusions(self):
        feature = self._base_feature()
        feature["properties"]["lower_height"] = 9.0
        feature["properties"]["upper_geometry"] = {
            "type": "Polygon",
            "coordinates": [[
                [127.0001, 37.0001],
                [127.0004, 37.0001],
                [127.0004, 37.0003],
                [127.0001, 37.0003],
                [127.0001, 37.0001],
            ]],
        }

        export = mass_geojson_to_scad(feature, name="stepback")

        self.assertEqual(export.metadata["has_stepback"], True)
        self.assertIn("lower mass / podium", export.scad_text)
        self.assertIn("upper mass / stepback", export.scad_text)
        self.assertEqual(export.scad_text.count("linear_extrude(height=9.0000)"), 2)


class MaasScadExportEndpointTest(TestCase):
    def test_endpoint_requires_mass_geojson(self):
        response = self.client.post(
            "/design/maas/export-scad/",
            data={},
            content_type="application/json",
            HTTP_HOST="127.0.0.1",
        )

        self.assertEqual(response.status_code, 400)

    def test_endpoint_returns_scad_text(self):
        response = self.client.post(
            "/design/maas/export-scad/",
            data={
                "name": "candidate 01",
                "mass_geojson": {
                    "type": "Feature",
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [[
                            [127.0000, 37.0000],
                            [127.0004, 37.0000],
                            [127.0004, 37.0004],
                            [127.0000, 37.0004],
                            [127.0000, 37.0000],
                        ]],
                    },
                    "properties": {"height": 15.0, "far": 150.0, "bcr": 40.0},
                },
            },
            content_type="application/json",
            HTTP_HOST="127.0.0.1",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["name"], "candidate_01")
        self.assertIn("union() {", data["scad_text"])
        self.assertEqual(data["metadata"]["height"], 15.0)


class MaasEvidenceBundleEndpointTest(TestCase):
    def _feature(self):
        return {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [127.0000, 37.0000],
                    [127.0004, 37.0000],
                    [127.0004, 37.0004],
                    [127.0000, 37.0004],
                    [127.0000, 37.0000],
                ]],
            },
            "properties": {
                "algorithm": "maas_legal_envelope",
                "variant_id": "maas_01",
                "mass_shape": "legal_layered_max",
                "maas_concept": "legal capacity anchor",
                "height": 17.5,
                "num_floors": 5,
                "floor_height": 3.5,
                "footprint_area": 102.93,
                "floor_area": 361.28,
                "bcr": 38.97,
                "far": 136.78,
                "min_setback": 0.7,
                "open_pct": 61.03,
                "maas_score": 0.75,
                "floor_plates": [
                    {"floor": 1, "area_m2": 102.93},
                    {"floor": 5, "area_m2": 28.96},
                ],
                "mass_volumes": [],
            },
        }

    def _job(self):
        return OptimizationJob.objects.create(
            pnu="1168011800104170004",
            address="",
            site_polygon={
                "type": "Polygon",
                "coordinates": [[
                    [127.0000, 37.0000],
                    [127.0010, 37.0000],
                    [127.0010, 37.0010],
                    [127.0000, 37.0010],
                    [127.0000, 37.0000],
                ]],
            },
            site_area_m2=264.1,
            job_spec={"options": {"building_type": "공동주택", "algorithm": "maas_legal_envelope"}},
            constraints=[
                {"name": "bcr", "type": "Constraint", "Requirement": "Less than", "val": 60, "unit": "%"},
                {"name": "far", "type": "Constraint", "Requirement": "Less than", "val": 200, "unit": "%"},
                {"name": "height", "type": "Constraint", "Requirement": "Less than", "val": 35, "unit": "m"},
                {"name": "setback", "type": "Constraint", "Requirement": "Greater than", "val": 0.5, "unit": "m"},
            ],
            status="complete",
        )

    def test_endpoint_returns_canonical_evidence_bundle(self):
        job = self._job()
        DesignResult.objects.create(
            job=job,
            generation=0,
            design_id=900000,
            inputs=[],
            outputs={"objectives": [361.28, 61.03]},
            ranking=1.0,
            is_feasible=True,
            is_pareto_optimal=True,
            mass_geojson=self._feature(),
        )

        response = self.client.get(
            f"/design/jobs/{job.id}/results/900000/evidence/",
            HTTP_HOST="127.0.0.1",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["schema_version"], "arr.maas.evidence.v0")
        for key in (
            "project", "site", "candidate", "geometry", "legal", "program",
            "mobility", "life_safety", "environment", "checks", "issues",
            "validators", "assets", "provenance", "agent_reviews", "final_decision",
        ):
            self.assertIn(key, data)
        self.assertEqual(data["site"]["pnu"], "1168011800104170004")
        self.assertEqual(data["candidate"]["intended_use"]["building_type"], "공동주택")
        self.assertIn("parking_strategy", data["candidate"])
        self.assertIn("precheck", data["mobility"]["parking"])
        self.assertIn("small_attached_parking_relief", data["mobility"]["parking"]["precheck"])
        self.assertEqual(data["geometry"]["geometry_metrics"]["height_m"], 17.5)
        statuses = {check["key"]: check["status"] for check in data["checks"]}
        self.assertEqual(statuses["bulk_and_density.bcr"], "pass")
        self.assertEqual(statuses["bulk_and_density.far"], "pass")
        self.assertEqual(statuses["bulk_and_density.height"], "pass")
        self.assertEqual(statuses["parking_loading_and_mobility.parking_required_count"], "needs_evidence")
        self.assertEqual(data["final_decision"]["status"], "needs_evidence")
        self.assertIn("parking_loading_and_mobility.parking_required_count", data["final_decision"]["missing_evidence"])

    def test_evidence_preserves_zero_metrics_without_fallback(self):
        job = self._job()
        feature = self._feature()
        feature["properties"]["min_setback"] = 0.0
        feature["properties"]["maas_score"] = 0.0
        feature["properties"]["maas_model"] = {
            "legal_metrics": {
                "min_setback": 99.0,
            }
        }
        DesignResult.objects.create(
            job=job,
            generation=0,
            design_id=900001,
            inputs=[],
            outputs={},
            ranking=1.0,
            is_feasible=True,
            is_pareto_optimal=True,
            mass_geojson=feature,
        )

        response = self.client.get(
            f"/design/jobs/{job.id}/results/900001/evidence/",
            HTTP_HOST="127.0.0.1",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["candidate"]["score"], 0.0)
        self.assertEqual(data["geometry"]["geometry_metrics"]["min_setback_m"], 0.0)
        statuses = {check["key"]: check["status"] for check in data["checks"]}
        self.assertEqual(statuses["building_line_and_setbacks.adjacent_setback"], "fail")

    def test_missing_pnu_is_not_replaced_with_placeholder(self):
        job = self._job()
        job.pnu = ""
        job.save(update_fields=["pnu"])
        DesignResult.objects.create(
            job=job,
            generation=0,
            design_id=900002,
            inputs=[],
            outputs={},
            ranking=1.0,
            is_feasible=True,
            is_pareto_optimal=True,
            mass_geojson=self._feature(),
        )

        response = self.client.get(
            f"/design/jobs/{job.id}/results/900002/evidence/",
            HTTP_HOST="127.0.0.1",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsNone(data["site"]["pnu"])
        statuses = {check["key"]: check["status"] for check in data["checks"]}
        self.assertEqual(statuses["site_rights_and_cadastre.pnu_identity"], "needs_evidence")
        self.assertIn("site_rights_and_cadastre.pnu_identity", data["final_decision"]["missing_evidence"])
        self.assertIn("issue:site:missing-pnu", {issue["id"] for issue in data["issues"]})

    def test_evidence_merges_law_graph_projection_without_changing_status(self):
        job = self._job()
        DesignResult.objects.create(
            job=job,
            generation=0,
            design_id=900003,
            inputs=[],
            outputs={},
            ranking=1.0,
            is_feasible=True,
            is_pareto_optimal=True,
            mass_geojson=self._feature(),
        )

        projection = {
            "graph_status": {"available": True, "resolved_count": 1, "missing_count": 0},
            "articles": [
                {
                    "ref_id": "건축법_제60조",
                    "full_id": "건축법(법률)::제6장::제60조",
                    "law_name": "건축법",
                    "number": "60조",
                    "title": "건축물의 높이 제한",
                    "source": "neo4j",
                }
            ],
            "refs_by_check": {
                "bulk_and_density.height": ["law:건축법(법률)::제6장::제60조"],
            },
            "provenance_entities": [
                {
                    "id": "law:건축법(법률)::제6장::제60조",
                    "type": "LawArticle",
                    "title": "건축물의 높이 제한",
                }
            ],
            "provenance_relations": [
                {
                    "type": "wasDerivedFrom",
                    "entity": "law:건축법(법률)::제6장::제60조",
                    "source": "neo4j:law_graph",
                }
            ],
        }

        with patch("design.maas.evidence.build_law_provenance_projection", return_value=projection):
            response = self.client.get(
                f"/design/jobs/{job.id}/results/900003/evidence/",
                HTTP_HOST="127.0.0.1",
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["final_decision"]["status"], "needs_evidence")
        self.assertEqual(data["legal"]["graph_projection"]["available"], True)
        self.assertEqual(data["legal"]["law_articles"][0]["title"], "건축물의 높이 제한")
        checks = {check["key"]: check for check in data["checks"]}
        height_check = checks["bulk_and_density.height"]
        self.assertIn("law:건축법(법률)::제6장::제60조", height_check["basis"]["law_articles"])
        self.assertIn("law:건축법(법률)::제6장::제60조", height_check["evidence_refs"])
        self.assertIn(
            "law:건축법(법률)::제6장::제60조",
            {entity["id"] for entity in data["provenance"]["entities"]},
        )


class MaasLegalVariantsTest(TestCase):
    def _site(self):
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

    def _mass(self):
        return {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [127.0002, 37.0002],
                    [127.0008, 37.0002],
                    [127.0008, 37.0008],
                    [127.0002, 37.0008],
                    [127.0002, 37.0002],
                ]],
            },
            "properties": {"height": 28.0, "num_floors": 10, "floor_height": 2.8},
        }

    def _constraints(self):
        return [
            {"name": "bcr", "type": "Constraint", "Requirement": "Less than", "val": 50, "unit": "%"},
            {"name": "far", "type": "Constraint", "Requirement": "Less than", "val": 250, "unit": "%"},
            {"name": "height", "type": "Constraint", "Requirement": "Less than", "val": 35, "unit": "m"},
        ]

    def _sunlight_envelope(self, height=10.0):
        return {
            "slanted_polygons": [{
                "corners": [
                    [127.0000, 37.0000, height],
                    [127.0010, 37.0000, height],
                    [127.0010, 37.0010, height],
                    [127.0000, 37.0010, height],
                ],
            }],
        }

    def test_generates_repaired_legal_diverse_variants(self):
        result = generate_legal_mass_variants(
            mass_geojson=self._mass(),
            site_polygon_geojson=self._site(),
            constraints=self._constraints(),
            building_type="공동주택",
            max_variants=4,
        )

        self.assertEqual(result["mode"], "maas_legal_variants")
        self.assertEqual(result["algorithm"], "maas_legal_envelope")
        self.assertEqual(result["seed_library"]["legacy_algorithms"], "demoted_to_seed_sources")
        self.assertEqual(result["seed_library"]["capacity_source"], "legal_envelope")
        self.assertEqual(result["seed_library"]["grammar_sequences"], "enabled_as_composite_maas_seeds")
        self.assertGreater(result["count"], 0)
        self.assertLessEqual(result["count"], 4)
        for feature in result["feature_collection"]["features"]:
            props = feature["properties"]
            self.assertEqual(props["algorithm"], "maas_legal_envelope")
            self.assertLessEqual(props["bcr"], 50.1)
            self.assertLessEqual(props["far"], 250.1)
            self.assertLessEqual(props["height"], 35.1)
            self.assertIn("maas_score", props)
            self.assertIn("far_utilization", props)
            self.assertIn("bcr_utilization", props)
            self.assertIn(props["parking_strategy"], {
                "none",
                "ground_surface",
                "piloti_ground",
                "basement",
                "semi_basement",
                "mechanical",
                "mixed",
            })
            self.assertEqual(props["parking_precheck"]["schema_version"], "arr.maas.parking_strategy.v0")
            self.assertEqual(props["parking_precheck"]["status"], "has_layout_candidate")
            self.assertEqual(
                props["parking_precheck"]["layout_candidate"]["legal_count_status"],
                "unresolved_visual_layout_only",
            )
            self.assertIn("small_attached_parking_relief", props["parking_precheck"])
            self.assertEqual(props["maas_model"]["parking_strategy"], props["parking_strategy"])

    def test_small_attached_parking_relief_tracks_road_aisle_and_tandem_exceptions(self):
        relief = evaluate_small_attached_parking_relief(
            required_spaces=5,
            road_context={
                "road_width_m": 6.0,
                "has_sidewalk_separation": False,
                "is_dead_end_road": True,
            },
        )

        self.assertEqual(relief["status"], "evaluated")
        self.assertTrue(relief["road_as_aisle_options"][0]["available"])
        self.assertFalse(relief["road_as_aisle_options"][1]["available"])
        self.assertTrue(relief["tandem_parking"]["available"])
        self.assertEqual(relief["tandem_parking"]["max_depth_from_aisle"], 2)
        self.assertEqual(relief["entrance_width"]["min_width_m"], 3.0)
        self.assertEqual(relief["entrance_width"]["dead_end_road_approval_min_width_m"], 2.5)

    def test_small_attached_parking_relief_blocks_exceptions_when_space_count_is_too_high(self):
        relief = evaluate_small_attached_parking_relief(
            required_spaces=9,
            road_context={
                "road_width_m": 6.0,
                "has_sidewalk_separation": False,
            },
        )

        self.assertFalse(relief["road_as_aisle_options"][0]["available"])
        self.assertFalse(relief["tandem_parking"]["available"])

    def test_parking_layout_candidate_places_small_tandem_stalls_with_road_as_aisle(self):
        layout = generate_parking_layout_candidate(
            box(0, 0, 12.5, 10),
            required_spaces=5,
            accessible_spaces=1,
            road_context={
                "road_width_m": 6.0,
                "has_sidewalk_separation": False,
            },
        )

        self.assertEqual(layout["status"], "pass")
        self.assertEqual(layout["placement_mode"], "road_as_aisle_tandem")
        self.assertEqual(layout["provided_spaces"], 5)
        self.assertEqual(layout["provided_accessible_spaces"], 1)
        self.assertEqual(layout["stalls"][0]["type"], "accessible")
        self.assertIn("polygon", layout["stalls"][0])
        self.assertEqual(
            layout["authority_review_check"]["status"],
            "prechecked_needs_external_evidence",
        )
        self.assertTrue(layout["authority_review_check"]["checks"]["tandem_depth_count_ok"])
        self.assertIn(
            "authority_no_traffic_obstruction_confirmation",
            layout["authority_review_check"]["external_evidence_needed"],
        )

    def test_parking_layout_candidate_places_internal_double_loaded_stalls(self):
        layout = generate_parking_layout_candidate(
            box(0, 0, 16, 16),
            required_spaces=8,
            accessible_spaces=0,
            strategy="piloti_ground",
        )

        self.assertEqual(layout["status"], "pass")
        self.assertEqual(layout["placement_mode"], "internal_double_loaded_90")
        self.assertEqual(layout["provided_spaces"], 8)
        self.assertEqual(layout["unmet_spaces"], 0)

    def test_parking_layout_candidate_draws_small_single_row_review_stalls(self):
        layout = generate_parking_layout_candidate(
            box(0, 0, 14, 5.5),
            required_spaces=5,
            accessible_spaces=1,
            strategy="ground_surface",
        )

        self.assertEqual(layout["status"], "needs_aisle_review")
        self.assertEqual(layout["placement_mode"], "single_row_aisle_review")
        self.assertEqual(layout["provided_spaces"], 5)
        self.assertEqual(layout["provided_accessible_spaces"], 1)
        self.assertEqual(layout["unmet_spaces"], 0)

    def test_parking_layout_grid_solver_places_connected_drive_cells(self):
        layout = _solve_grid_parking_layout(
            box(0, 0, 14, 11.5),
            required_spaces=3,
            accessible_spaces=0,
            strategy="piloti_ground",
            road_context={"sharedEdge": [[0, 11.5], [14, 11.5]]},
        )

        self.assertEqual(layout["status"], "pass")
        self.assertEqual(layout["placement_mode"], "grid_connected_90")
        self.assertEqual(layout["provided_spaces"], 3)
        self.assertEqual(layout["unmet_spaces"], 0)
        self.assertEqual(layout["adjacency"]["status"], "row_contiguous")
        self.assertEqual(layout["adjacency"]["gap_pairs"], 0)
        self.assertEqual(layout["column_clearance"]["status"], "deferred_structural_review")
        self.assertEqual(layout["drive_aisle_clearance"]["status"], "pass")
        self.assertEqual(layout["turning_clearance"]["status"], "v1_pass")
        self.assertEqual(layout["turning_clearance"]["method"], "stall_frontage_and_entrance_connector_v1")
        self.assertEqual(layout["turning_clearance"]["frontage_connected_stalls"], 3)
        self.assertEqual(layout["turning_clearance"]["frontage_total_stalls"], 3)
        self.assertTrue(layout["turning_clearance"]["entrance_connected"])
        self.assertIn("grid_solver", layout)
        self.assertGreaterEqual(layout["grid_solver"]["candidate_stalls"], 3)
        self.assertEqual(len(layout["grid_solver"]["drive_cells"]), 3)
        self.assertTrue(layout["grid_solver"]["drive_components_connected"])
        self.assertTrue(layout["grid_solver"]["entrance_connected"])
        self.assertEqual(layout["grid_solver"]["entrance_connection_method"], "road_frontage_geometry")

    def test_parking_layout_grid_solver_flags_disconnected_entrance_edge(self):
        layout = _solve_grid_parking_layout(
            box(0, 0, 14, 11.5),
            required_spaces=3,
            accessible_spaces=0,
            strategy="piloti_ground",
            road_context={"sharedEdge": [[0, 20], [14, 20]]},
        )

        self.assertEqual(layout["status"], "needs_drive_connectivity_review")
        self.assertEqual(layout["provided_spaces"], 3)
        self.assertFalse(layout["grid_solver"]["entrance_connected"])
        self.assertEqual(layout["grid_solver"]["entrance_connection_method"], "road_frontage_geometry")
        self.assertGreater(layout["grid_solver"]["entrance_min_distance_m"], 0)
        self.assertEqual(layout["turning_clearance"]["status"], "needs_swept_path_review")
        self.assertEqual(layout["turning_clearance"]["frontage_connected_stalls"], 3)
        self.assertFalse(layout["turning_clearance"]["entrance_connected"])

    def test_parking_layout_grid_solver_records_site_connector_turning_v1(self):
        layout = _solve_grid_parking_layout(
            box(0, 0, 14, 11.5),
            drive_polygon=box(0, 0, 14, 17),
            required_spaces=3,
            accessible_spaces=0,
            strategy="piloti_ground",
            road_context={"sharedEdge": [[0, 17], [14, 17]]},
        )

        self.assertEqual(layout["status"], "pass")
        self.assertEqual(layout["grid_solver"]["entrance_connection_type"], "site_connector_v1")
        self.assertEqual(layout["grid_solver"]["entrance_connector_width_m"], 3.0)
        self.assertEqual(layout["turning_clearance"]["status"], "v1_pass")
        self.assertEqual(layout["turning_clearance"]["method"], "stall_frontage_and_entrance_connector_v1")
        self.assertEqual(layout["turning_clearance"]["frontage_connected_stalls"], 3)
        self.assertTrue(layout["turning_clearance"]["entrance_connected"])
        self.assertEqual(layout["turning_clearance"]["entrance_connection_type"], "site_connector_v1")

    def test_parking_drive_entrance_allows_site_connector_inside_drive_area(self):
        access = _drive_entrance_access(
            [box(2, 2, 4, 4)],
            box(0, 0, 10, 10),
            road_context={"sharedEdge": [[10, 2], [10, 4]]},
        )

        self.assertTrue(access["connected"])
        self.assertEqual(access["connection_type"], "site_connector_v1")
        self.assertEqual(access["connector_length_m"], 6.0)
        self.assertEqual(access["connector_width_m"], 3.0)

    def test_parking_drive_entrance_rejects_connector_without_min_width(self):
        access = _drive_entrance_access(
            [box(2, 2.8, 4, 3.2)],
            box(0, 2.6, 10, 3.4),
            road_context={"sharedEdge": [[10, 2.8], [10, 3.2]]},
        )

        self.assertFalse(access["connected"])
        self.assertEqual(access["connection_type"], "none")

    def test_parking_drive_entrance_rejects_connector_outside_drive_area(self):
        access = _drive_entrance_access(
            [box(2, 2, 4, 4)],
            box(0, 0, 10, 10),
            road_context={"sharedEdge": [[12, 2], [12, 4]]},
        )

        self.assertFalse(access["connected"])
        self.assertEqual(access["connection_type"], "none")

    def test_parking_layout_grid_solver_prefers_accessible_drive_edge(self):
        layout = _solve_grid_parking_layout(
            box(0, 0, 70, 11.5),
            required_spaces=2,
            accessible_spaces=0,
            strategy="ground_surface",
            road_context={"sharedEdge": [[0, 0], [70, 0]]},
        )

        self.assertEqual(layout["status"], "pass")
        self.assertEqual(layout["adjacency"]["status"], "row_contiguous")
        self.assertTrue(layout["grid_solver"]["entrance_connected"])
        self.assertEqual(layout["grid_solver"]["entrance_min_distance_m"], 0.0)

    def test_parking_layout_grid_solver_prefers_adjacent_small_stalls(self):
        layout = _solve_grid_parking_layout(
            box(0, 0, 70, 11.5),
            required_spaces=2,
            accessible_spaces=0,
            strategy="ground_surface",
            road_context={"sharedEdge": [[0, 11.5], [70, 11.5]]},
        )

        self.assertEqual(layout["provided_spaces"], 2)
        first = Polygon(layout["stalls"][0]["polygon"])
        second = Polygon(layout["stalls"][1]["polygon"])
        self.assertLessEqual(first.distance(second), 0.05)
        self.assertEqual(layout["adjacency"]["status"], "row_contiguous")
        self.assertTrue(layout["adjacency"]["contiguous_ok"])
        self.assertEqual(layout["layout_formula"]["schema_version"], "arr.maas.parking_formula.v1")
        self.assertEqual(layout["layout_formula"]["module"]["double_loaded_90_depth_m"], 16.0)
        self.assertEqual(layout["column_clearance"]["status"], "not_applicable")
        self.assertEqual(layout["drive_aisle_clearance"]["status"], "pass")
        self.assertEqual(layout["turning_clearance"]["status"], "v1_pass")

    def test_parking_layout_grid_solver_fails_when_accessible_stall_is_missing(self):
        layout = _solve_grid_parking_layout(
            box(0, 0, 2.6, 11.5),
            required_spaces=1,
            accessible_spaces=1,
            strategy="ground_surface",
            road_context={"sharedEdge": [[0, 11.5], [2.6, 11.5]]},
        )

        self.assertEqual(layout["status"], "fail")
        self.assertEqual(layout["provided_spaces"], 1)
        self.assertEqual(layout["provided_accessible_spaces"], 0)
        self.assertEqual(layout["unmet_spaces"], 0)
        self.assertEqual(layout["unmet_accessible_spaces"], 1)
        self.assertEqual(layout["reason"], "grid_solver_insufficient_accessible_stall_candidates")

    def test_parking_strategy_keeps_searching_after_aisle_review_candidate(self):
        strategy = infer_parking_strategy(
            {
                "footprint_area": 80.0,
                "floor_area": 160.0,
                "num_floors": 2,
                "bcr": 50.0,
                "required_parking_spaces": 2,
                "parking_road_context": {
                    "sharedEdge": [[0, 17], [14, 17]],
                },
            },
            site_area_m2=238.0,
            building_type="다가구주택",
            footprint_utm=box(0, 0, 14, 5.5),
            site_utm=box(0, 0, 14, 17),
        )

        self.assertEqual(strategy["selected_strategy"], "piloti_ground")
        self.assertEqual(strategy["layout_candidate"]["status"], "pass")
        self.assertEqual(strategy["layout_candidate"]["turning_clearance"]["frontage_connected_stalls"], 2)

    def test_parking_strategy_attaches_layout_candidate_when_required_count_exists(self):
        strategy = infer_parking_strategy(
            {
                "footprint_area": 125.0,
                "floor_area": 250.0,
                "num_floors": 2,
                "bcr": 50.0,
                "required_parking_spaces": 5,
                "required_accessible_parking_spaces": 1,
                "parking_road_context": {
                    "road_width_m": 6.0,
                    "has_sidewalk_separation": False,
                },
            },
            site_area_m2=250.0,
            building_type="다가구주택",
            footprint_utm=box(0, 0, 12.5, 10),
            site_utm=box(0, 0, 20, 12.5),
        )

        self.assertEqual(strategy["status"], "has_layout_candidate")
        self.assertEqual(strategy["layout_candidate"]["status"], "pass")
        self.assertEqual(strategy["layout_candidate"]["provided_spaces"], 5)
        self.assertIn("parking_envelope_wgs84", strategy)
        self.assertIn("polygon_wgs84", strategy["layout_candidate"]["stalls"][0])
        self.assertEqual(len(strategy["layout_candidate"]["stalls"][0]["polygon_wgs84"][0]), 2)

    def test_parking_requirement_local_seed_rules_compute_neighborhood_use(self):
        rules = {
            "national": {
                "parking_appendix1_row_03": {
                    "rule_id": "parking_appendix1_row_03",
                    "row_no": "3",
                    "spaces_per": 200.0,
                    "rounding_rule": "appendix_note_6_half_up_total_under_one_zero",
                }
            },
            "local": [
                {
                    "rule_id": "seoul_parking_appendix2_row_03",
                    "base_rule_id": "parking_appendix1_row_03",
                    "pnu_prefix": "11",
                    "row_no": "3",
                    "spaces_per": 134.0,
                    "rounding_rule": "ordinance_note_6_half_up_total_under_one_zero",
                }
            ],
        }
        requirement = resolve_candidate_parking_requirement(
            pnu="1168011800104170004",
            building_type="근린생활시설",
            facility_area_m2=264.0,
            rules=rules,
        )

        self.assertEqual(requirement["status"], "computed")
        self.assertEqual(requirement["selected_rule_id"], "seoul_parking_appendix2_row_03")
        self.assertEqual(requirement["required_spaces"], 2)
        self.assertEqual(requirement["accessible"]["accessible_min"], 0)

    def test_grammar_sequences_generate_composite_variants(self):
        variants = generate_grammar_variants(box(0, 0, 30, 20))

        self.assertGreaterEqual(len(variants), 6)
        operators = {variant.operator for variant in variants}
        self.assertIn("grammar_courtyard_lift_taper", operators)
        self.assertIn("grammar_podium_tower_offset", operators)
        self.assertIn("grammar_sunlight_multi_step", operators)
        self.assertIn("grammar_diagonal_step_connector", operators)
        self.assertIn("grammar_terrace_ribbon_stepback", operators)
        self.assertIn("grammar_sloped_roof_envelope", operators)
        for variant in variants:
            self.assertTrue(variant.operator.startswith("grammar_"))
            self.assertGreaterEqual(len(variant.verb_sequence), 2)
            self.assertEqual(variant.verb_sequence[0]["verb"], "base")

    def test_design_section_operators_create_upper_mass_hints(self):
        from design.maas.morphology_operators import generate_morphology_variants

        variants = generate_morphology_variants(box(0, 0, 30, 20))
        by_operator = {variant.operator: variant for variant in variants}

        for operator in (
            "diagonal_connect_step_x",
            "diagonal_connect_step_y",
            "terrace_link_north",
            "sloped_roof_mass",
        ):
            self.assertIn(operator, by_operator)
            variant = by_operator[operator]
            self.assertIsNotNone(variant.upper_footprint)
            self.assertLess(variant.upper_footprint.area, variant.footprint.area)
            self.assertGreaterEqual(len(variant.verb_sequence), 2)
            self.assertEqual(variant.verb_sequence[0]["verb"], "base")

    def test_maas_sequence_metrics_follow_reference_eval_contract(self):
        from design.maas.design_quality import ordered_lcs, sequence_metrics, token_f1, verb_set_jaccard

        pred = [
            {"verb": "base", "params": {}},
            {"verb": "courtyard", "params": {}},
            {"verb": "lift", "params": {}},
            {"verb": "taper", "params": {}},
        ]
        gold = [
            {"verb": "base", "params": {}},
            {"verb": "courtyard", "params": {}},
            {"verb": "taper", "params": {}},
        ]

        self.assertEqual(ordered_lcs(pred, gold), 2)
        self.assertAlmostEqual(verb_set_jaccard(pred, gold), 2 / 3, places=4)
        self.assertAlmostEqual(token_f1(pred, gold), 0.8, places=4)
        metrics = sequence_metrics(pred, gold)
        self.assertEqual(metrics["parsimony"], 3)
        self.assertTrue(metrics["has_plan_operation"])
        self.assertTrue(metrics["has_section_operation"])
        self.assertEqual(metrics["reference_comparison"]["ordered_lcs"], 2)

    def test_d4descent_clone_backend_is_connected_as_research_optimizer(self):
        from design.maas.research_backends import d4descent_design_evidence

        evidence = d4descent_design_evidence(enable_import=False)

        self.assertEqual(evidence["name"], "d4descent")
        self.assertEqual(evidence["source"], "clone/d4descent")
        self.assertTrue(evidence["backend"]["exists"])
        self.assertEqual(evidence["backend"]["interfaces"]["optimizer"], "d4descent.optimizer.optimize")
        self.assertEqual(evidence["absorbed_pattern"]["rewrite"], "ARR grammar/morphology operators")

    def test_generated_variants_include_design_quality_and_d4descent_evidence(self):
        result = generate_legal_mass_variants(
            mass_geojson=self._mass(),
            site_polygon_geojson=self._site(),
            constraints=[
                {"name": "bcr", "type": "Constraint", "Requirement": "Less than", "val": 60, "unit": "%"},
                {"name": "far", "type": "Constraint", "Requirement": "Less than", "val": 250, "unit": "%"},
                {"name": "height", "type": "Constraint", "Requirement": "Less than", "val": 50, "unit": "m"},
            ],
            building_type="공동주택",
            max_variants=4,
            preferred_operator="grammar_diagonal_step_connector",
        )

        top = result["feature_collection"]["features"][0]["properties"]
        quality = top["design_quality"]
        self.assertEqual(quality["source"], "arr.maas.design_quality.v1")
        self.assertIn("sequence_metrics", quality)
        self.assertGreaterEqual(quality["score"], 0.0)
        self.assertLessEqual(quality["score"], 1.0)
        self.assertEqual(quality["optimizer_backend"]["name"], "d4descent")
        self.assertIn(quality["optimizer_backend"]["status"], {"imported", "import_failed", "available_not_imported", "missing"})
        self.assertEqual(top["maas_model"]["design_quality"]["score"], quality["score"])

    def test_sunlight_cap_and_bcr_fill_are_prioritized(self):
        constraints = [
            {"name": "bcr", "type": "Constraint", "Requirement": "Less than", "val": 60, "unit": "%"},
            {"name": "far", "type": "Constraint", "Requirement": "Less than", "val": 250, "unit": "%"},
            {"name": "height", "type": "Constraint", "Requirement": "Less than", "val": 50, "unit": "m"},
        ]

        result = generate_legal_mass_variants(
            mass_geojson=self._mass(),
            site_polygon_geojson=self._site(),
            constraints=constraints,
            building_type="공동주택",
            max_variants=5,
            sunlight_envelope=self._sunlight_envelope(height=10.0),
        )

        self.assertGreater(result["count"], 0)
        features = result["feature_collection"]["features"]
        for feature in features:
            props = feature["properties"]
            self.assertLessEqual(props["height"], 10.1)
            self.assertLessEqual(props["bcr"], 60.1)
            self.assertLessEqual(props["far"], 250.1)
        top = features[0]["properties"]
        self.assertIn(top["mass_shape"], {"legal_layered_max", "legal_buildable_max", "bcr_fill_light", "bcr_fill_mid", "bcr_fill_strong"})
        self.assertGreaterEqual(top["bcr"], 45.0)

    def test_buildable_max_variant_can_outgrow_small_source_mass(self):
        mass = self._mass()
        mass["geometry"]["coordinates"] = [[
            [127.00045, 37.00045],
            [127.00055, 37.00045],
            [127.00055, 37.00055],
            [127.00045, 37.00055],
            [127.00045, 37.00045],
        ]]

        result = generate_legal_mass_variants(
            mass_geojson=mass,
            site_polygon_geojson=self._site(),
            constraints=[
                {"name": "bcr", "type": "Constraint", "Requirement": "Less than", "val": 60, "unit": "%"},
                {"name": "far", "type": "Constraint", "Requirement": "Less than", "val": 250, "unit": "%"},
                {"name": "height", "type": "Constraint", "Requirement": "Less than", "val": 50, "unit": "m"},
                {"name": "building_line_setback", "type": "Constraint", "Requirement": "Greater than", "val": 0.5, "unit": "m"},
            ],
            building_type="공동주택",
            max_variants=5,
        )

        top = result["feature_collection"]["features"][0]["properties"]
        self.assertEqual(top["mass_shape"], "legal_layered_max")
        self.assertIn("maas_model", top)
        self.assertEqual(top["maas_model"]["operator"], top["mass_shape"])
        self.assertGreater(len(top["maas_model"]["volumes"]), 0)
        self.assertIn("floor_plates", top)
        self.assertGreater(len(top["floor_plates"]), 0)
        min_plate_area = min(24.0, top["floor_plates"][0]["area"] * 0.25)
        for plate in top["floor_plates"]:
            self.assertGreaterEqual(plate["area"], min_plate_area)
        self.assertEqual(top["maas_model"]["floor_plates"], top["floor_plates"])
        self.assertIn("floor_groups", top["maas_model"])
        self.assertGreater(len(top["maas_model"]["floor_groups"]), 0)
        first_group = top["maas_model"]["floor_groups"][0]
        self.assertEqual(first_group["program_packing"]["constraint_source"], "maas_legal_envelope")
        self.assertEqual(first_group["program_packing"]["algorithm"], "circle_grid_packing")
        self.assertEqual(first_group["program_packing"]["best_floor_plan"]["type"], "FeatureCollection")
        self.assertGreater(first_group["program_packing"]["preview_summary"]["room_count"], 0)
        self.assertLessEqual(top["bcr"], 60.1)
        self.assertLessEqual(top["far"], 250.1)
        self.assertGreater(top["bcr"], 1.0)

    def test_variant_selection_preserves_capacity_and_shape_diversity(self):
        result = generate_legal_mass_variants(
            mass_geojson=self._mass(),
            site_polygon_geojson=self._site(),
            constraints=[
                {"name": "bcr", "type": "Constraint", "Requirement": "Less than", "val": 60, "unit": "%"},
                {"name": "far", "type": "Constraint", "Requirement": "Less than", "val": 250, "unit": "%"},
                {"name": "height", "type": "Constraint", "Requirement": "Less than", "val": 50, "unit": "m"},
            ],
            building_type="공동주택",
            max_variants=8,
            sunlight_envelope={
                "slanted_polygons": [{
                    "corners": [
                        [127.0000, 37.0000, 10.0],
                        [127.0010, 37.0000, 14.0],
                        [127.0010, 37.0010, 30.0],
                        [127.0000, 37.0010, 24.0],
                    ],
                }],
            },
        )

        features = result["feature_collection"]["features"]
        shapes = {f["properties"]["mass_shape"].replace("_layered", "") for f in features}
        self.assertGreaterEqual(len(features), 6)
        self.assertGreaterEqual(len(shapes), 5)
        for feature in features:
            props = feature["properties"]
            self.assertLessEqual(props["bcr"], 60.1)
            self.assertLessEqual(props["far"], 250.1)
            self.assertLessEqual(props["height"], 50.1)
            self.assertIn("shape_signature_3d", props)
            self.assertIn("candidate_diversity", props)
            self.assertIn(props["candidate_diversity"]["class"], {"plan_diverse", "section_diverse", "near_duplicate"})
        self.assertTrue(any("floor_plates" in f["properties"] for f in features))
        diversity_classes = {f["properties"]["candidate_diversity"]["class"] for f in features}
        self.assertTrue({"plan_diverse", "section_diverse"} & diversity_classes)

    def test_preferred_design_operator_survives_selection(self):
        result = generate_legal_mass_variants(
            mass_geojson=self._mass(),
            site_polygon_geojson=self._site(),
            constraints=[
                {"name": "bcr", "type": "Constraint", "Requirement": "Less than", "val": 60, "unit": "%"},
                {"name": "far", "type": "Constraint", "Requirement": "Less than", "val": 250, "unit": "%"},
                {"name": "height", "type": "Constraint", "Requirement": "Less than", "val": 50, "unit": "m"},
            ],
            building_type="공동주택",
            max_variants=4,
            preferred_operator="grammar_terrace_ribbon_stepback",
        )

        features = result["feature_collection"]["features"]
        self.assertGreater(len(features), 0)
        top = features[0]["properties"]
        self.assertEqual(top["mass_shape"], "grammar_terrace_ribbon_stepback")
        self.assertEqual(top["maas_concept"], "연속테라스 스텝백")
        self.assertIn("maas_model", top)
        self.assertGreaterEqual(len(top["maas_model"]["volumes"]), 2)
        self.assertIn("terrace_link", [item["verb"] for item in top["maas_verb_sequence"]])
        self.assertLessEqual(top["bcr"], 60.1)
        self.assertLessEqual(top["far"], 250.1)

    def test_layered_stack_uses_floor_by_floor_envelope(self):
        """층별 허용 footprint를 잘라 사선 높이 여유를 FAR로 활용한다."""
        envelope = {
            "slanted_polygons": [{
                "corners": [
                    [127.0000, 37.0000, 10.0],
                    [127.0010, 37.0000, 10.0],
                    [127.0010, 37.0010, 30.0],
                    [127.0000, 37.0010, 30.0],
                ],
            }],
        }
        result = generate_legal_mass_variants(
            mass_geojson=self._mass(),
            site_polygon_geojson=self._site(),
            constraints=[
                {"name": "bcr", "type": "Constraint", "Requirement": "Less than", "val": 60, "unit": "%"},
                {"name": "far", "type": "Constraint", "Requirement": "Less than", "val": 250, "unit": "%"},
                {"name": "height", "type": "Constraint", "Requirement": "Less than", "val": 50, "unit": "m"},
            ],
            building_type="공동주택",
            max_variants=5,
            sunlight_envelope=envelope,
        )

        top = result["feature_collection"]["features"][0]["properties"]
        self.assertEqual(top["mass_shape"], "legal_layered_max")
        self.assertTrue(result["constraints"]["has_floor_plate_stack"])
        self.assertGreater(top["height"], 10.0)
        self.assertLessEqual(top["far"], 250.1)
        self.assertLessEqual(top["bcr"], 60.1)
        self.assertGreater(len(top["floor_plates"]), 3)
        areas = [p["area"] for p in top["floor_plates"]]
        self.assertLess(areas[-1], areas[0])
        min_plate_area = min(24.0, areas[0] * 0.25)
        for area in areas:
            self.assertGreaterEqual(area, min_plate_area)

    def test_edge_specific_setback_geometry_avoids_global_road_buffer(self):
        """도로 setback은 도로 edge에만 적용하고 반대편 인접 edge 용량은 보존한다."""
        site = self._site()
        # bottom road edge만 8m 후퇴, 나머지는 buildable_area 0.5m 기반.
        setback_geometries = {
            "buildable_area": {
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[
                        [127.000005, 37.000005],
                        [127.000995, 37.000005],
                        [127.000995, 37.000995],
                        [127.000005, 37.000995],
                        [127.000005, 37.000005],
                    ]],
                },
                "distance_m": 0.5,
                "label": "edge-specific buildable",
            },
            "road_setback": {
                "geometry": {
                    "type": "LineString",
                    "coordinates": [
                        [127.0000, 37.000072],
                        [127.0010, 37.000072],
                    ],
                },
                "distance_m": 8.0,
                "label": "bottom road only",
            },
        }
        result = generate_legal_mass_variants(
            mass_geojson=self._mass(),
            site_polygon_geojson=site,
            constraints=[
                {"name": "bcr", "type": "Constraint", "Requirement": "Less than", "val": 80, "unit": "%"},
                {"name": "far", "type": "Constraint", "Requirement": "Less than", "val": 400, "unit": "%"},
                {"name": "height", "type": "Constraint", "Requirement": "Less than", "val": 50, "unit": "m"},
                {"name": "setback", "type": "Constraint", "Requirement": "Greater than", "val": 0.5, "unit": "m"},
            ],
            building_type="공동주택",
            max_variants=3,
            setback_geometries=setback_geometries,
        )

        top = result["feature_collection"]["features"][0]["properties"]
        self.assertEqual(top["mass_shape"], "legal_layered_max")
        self.assertGreater(top["bcr"], 50.0)
        self.assertLess(top["bcr"], 80.1)

    def test_interactive_operation_endpoint_returns_synced_metrics(self):
        response = self.client.post(
            "/design/interactive/operation/",
            data={
                "mass_geojson": self._mass(),
                "site_polygon": self._site(),
                "constraints": self._constraints(),
                "building_type": "공동주택",
                "operation": {"type": "push_pull_height", "delta_floors": 1},
            },
            content_type="application/json",
            HTTP_HOST="127.0.0.1",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["mode"], "interactive_operation")
        props = data["feature"]["properties"]
        self.assertLessEqual(props["bcr"], 50.1)
        self.assertLessEqual(props["far"], 250.1)
        self.assertLessEqual(props["height"], 35.1)
        self.assertEqual(data["normalized_operation"]["type"], "push_pull_face")
        self.assertIn("operation_history", props)
        self.assertGreaterEqual(len(data["agent_reviews"]), 4)
        self.assertEqual(data["a2ui_messages"][0]["version"], "v0.9")
        self.assertIn("createSurface", data["a2ui_messages"][0])

    def test_interactive_offset_edge_returns_agent_reviewed_legal_mass(self):
        response = self.client.post(
            "/design/interactive/operation/",
            data={
                "mass_geojson": self._mass(),
                "site_polygon": self._site(),
                "constraints": self._constraints(),
                "building_type": "공동주택",
                "operation": {
                    "type": "offset_edge",
                    "target": {"kind": "side", "edge_index": 1},
                    "delta_m": 2.0,
                },
            },
            content_type="application/json",
            HTTP_HOST="127.0.0.1",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        props = data["feature"]["properties"]
        self.assertEqual(data["normalized_operation"]["type"], "offset_edge")
        self.assertEqual(data["normalized_operation"]["target"]["edge_index"], 1)
        self.assertEqual(props["mass_shape"], "interactive_seed_repaired")
        self.assertLessEqual(props["bcr"], 50.1)
        self.assertLessEqual(props["far"], 250.1)
        self.assertIn("operation_history", props)
        self.assertTrue(any(r["agent"] == "law_agent" for r in data["agent_reviews"]))
        self.assertEqual(data["a2ui_messages"][1]["updateComponents"]["surfaceId"], "maas-agent-review")

    def test_overheight_source_does_not_inflate_legal_seed_floors(self):
        mass = self._mass()
        mass["properties"] = {"height": 280.0, "num_floors": 100, "floor_height": 2.8}

        result = generate_legal_mass_variants(
            mass_geojson=mass,
            site_polygon_geojson=self._site(),
            constraints=self._constraints(),
            building_type="공동주택",
            max_variants=3,
        )

        # 35m / 2.8m = 12 floors. The source may be illegal, but the seed budget
        # reported by MAAS must remain the legal height-derived seed.
        self.assertEqual(result["constraints"]["max_seed_floors"], 12)
        for feature in result["feature_collection"]["features"]:
            self.assertLessEqual(feature["properties"]["height"], 35.1)

    def test_endpoint_returns_feature_collection(self):
        response = self.client.post(
            "/design/maas/legal-variants/",
            data={
                "mass_geojson": self._mass(),
                "site_polygon": self._site(),
                "constraints": self._constraints(),
                "building_type": "공동주택",
                "max_variants": 3,
            },
            content_type="application/json",
            HTTP_HOST="127.0.0.1",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["mode"], "maas_legal_variants")
        self.assertEqual(data["feature_collection"]["type"], "FeatureCollection")
        self.assertLessEqual(data["count"], 3)


class MaasIntentTrainingContractTest(TestCase):
    def _job(self, *, algorithm="maas_legal_envelope"):
        return OptimizationJob.objects.create(
            pnu="1168011800104170004",
            address="",
            site_polygon={
                "type": "Polygon",
                "coordinates": [[
                    [127.0000, 37.0000],
                    [127.0010, 37.0000],
                    [127.0010, 37.0010],
                    [127.0000, 37.0010],
                    [127.0000, 37.0000],
                ]],
            },
            site_area_m2=264.1,
            job_spec={"options": {"building_type": "공동주택", "algorithm": algorithm}},
            constraints=[],
            status="complete",
        )

    def _design(self, job, design_id, *, algorithm="maas_legal_envelope"):
        return DesignResult.objects.create(
            job=job,
            generation=0,
            design_id=design_id,
            inputs=[],
            outputs={},
            ranking=1.0,
            is_feasible=True,
            is_pareto_optimal=True,
            mass_geojson={
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[
                        [127.0000, 37.0000],
                        [127.0004, 37.0000],
                        [127.0004, 37.0004],
                        [127.0000, 37.0004],
                        [127.0000, 37.0000],
                    ]],
                },
                "properties": {"algorithm": algorithm, "height": 15.0},
            },
        )

    def test_korean_architectural_intent_resolves_to_maas_sequence_not_geometry(self):
        result = resolve_intent_to_sequence("북측 일조 때문에 상부를 계단식으로 후퇴시켜줘")

        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["policy"]["llm_must_not_emit_raw_geometry"])
        self.assertEqual(result["policy"]["geometry_source_of_truth"], "ARR/backend/design/maas")
        top = result["proposals"][0]
        self.assertEqual(top["sequence"], "grammar_sunlight_multi_step")
        self.assertEqual(top["maas_sequence"][0]["verb"], "base")
        self.assertNotIn("coordinates", json.dumps(top, ensure_ascii=False))
        self.assertIn("sunlight", top["constraints"]["must_validate"])

    def test_term_ontology_contains_architecture_terms_for_sequence_mapping(self):
        ontology = load_term_ontology()
        terms = {term["id"]: term for term in ontology["terms"]}

        self.assertIn("sunlight_step", terms)
        self.assertIn("podium_tower", terms)
        self.assertIn("split_bridge", terms)
        self.assertIn("diagonal_connect", terms)
        self.assertIn("terrace_link", terms)
        self.assertIn("sloped_roof_mass", terms)
        self.assertIn("step_envelope", terms["sunlight_step"]["verbs"])
        self.assertIn("split", terms["split_bridge"]["verbs"])
        self.assertIn("diagonal_connect", terms["diagonal_connect"]["verbs"])

    def test_seed_sft_examples_train_intent_to_sequence_contract(self):
        examples = build_sft_examples()
        sunlight_examples = [
            example for example in examples
            if example["sequence"] == "grammar_sunlight_multi_step"
        ]

        self.assertGreaterEqual(len(sunlight_examples), 2)
        assistant = json.loads(sunlight_examples[0]["messages"][2]["content"])
        self.assertEqual(assistant["maas_sequence"][0]["verb"], "base")
        self.assertEqual(
            assistant["constraints"]["geometry_source_of_truth"],
            "ARR/backend/design/maas",
        )
        self.assertIn("sunlight", assistant["constraints"]["must_validate"])

    def test_sft_seed_export_writes_jsonl(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = export_sft_seed(os.path.join(tmp, "maas_intent_sft_seed.jsonl"))
            lines = path.read_text(encoding="utf-8").splitlines()

        self.assertGreater(len(lines), 10)
        first = json.loads(lines[0])
        self.assertEqual(first["source"], "arr.maas.sequence_library.v0")
        self.assertEqual(first["messages"][0]["role"], "system")

    def test_evidence_review_training_keeps_missing_evidence_visible(self):
        evidence = {
            "schema_version": "arr.maas.evidence.v0",
            "bundle_id": "maas-evidence:test-job:maas_01",
            "candidate": {
                "candidate_id": "maas_01",
                "mass_shape": "legal_layered_max",
                "maas_concept": "legal capacity anchor",
            },
            "geometry": {
                "geometry_metrics": {"height_m": 17.5, "far": 136.78},
                "verb_sequence": [{"verb": "base", "params": {"source": "legal_buildable"}}],
            },
            "checks": [
                {"key": "bulk_and_density.height", "status": "pass"},
                {"key": "parking_loading_and_mobility.parking_required_count", "status": "needs_evidence"},
            ],
            "final_decision": {
                "status": "needs_evidence",
                "missing_evidence": ["parking_loading_and_mobility.parking_required_count"],
            },
        }

        example = evidence_to_review_example(evidence)
        answer = json.loads(example["messages"][2]["content"])

        self.assertEqual(answer["review_status"], "needs_evidence")
        self.assertTrue(answer["must_not_claim_legal_pass"])
        self.assertIn("maas_review", answer["recommended_tools"])

    def test_management_command_exports_seed_without_database(self):
        with tempfile.TemporaryDirectory() as tmp:
            call_command("export_maas_training_data", out_dir=tmp, skip_db=True, verbosity=0)
            path = os.path.join(tmp, "maas_intent_sft_seed.jsonl")

            self.assertTrue(os.path.exists(path))
            with open(path, "r", encoding="utf-8") as f:
                row = json.loads(f.readline())

        self.assertEqual(row["source"], "arr.maas.sequence_library.v0")

    def test_evidence_review_export_filters_non_maas_design_results(self):
        non_maas_job = self._job(algorithm="additive")
        self._design(non_maas_job, 910001, algorithm="additive")
        maas_job = self._job(algorithm="maas_legal_envelope")
        self._design(maas_job, 910002, algorithm="maas_legal_envelope")

        examples = build_examples_from_design_results(limit=10)

        self.assertEqual(len(examples), 1)
        prompt = json.loads(examples[0]["messages"][1]["content"])
        self.assertEqual(prompt["candidate"]["candidate_id"], "910002")

    def test_evidence_review_export_allows_zero_limit(self):
        maas_job = self._job(algorithm="maas_legal_envelope")
        self._design(maas_job, 910003, algorithm="maas_legal_envelope")

        self.assertEqual(build_examples_from_design_results(limit=0), [])


class MaasAestheticImageJobTest(TestCase):
    def _evidence(self):
        return {
            "schema_version": "arr.maas.evidence.v0",
            "bundle_id": "maas-evidence:test-job:maas_01",
            "candidate": {
                "candidate_id": "maas_01",
                "mass_shape": "legal_layered_max",
                "intended_use": {"building_type": "공동주택"},
            },
            "geometry": {
                "mass_geojson": {
                    "type": "Feature",
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [[
                            [127.0000, 37.0000],
                            [127.0004, 37.0000],
                            [127.0004, 37.0003],
                            [127.0000, 37.0003],
                            [127.0000, 37.0000],
                        ]],
                    },
                    "properties": {},
                },
                "floor_plates": [{"floor": 1, "area_m2": 120.0}],
                "mass_volumes": [{
                    "name": "main",
                    "bottom_height": 0.0,
                    "top_height": 21.0,
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [[
                            [127.0000, 37.0000],
                            [127.0004, 37.0000],
                            [127.0004, 37.0003],
                            [127.0000, 37.0003],
                            [127.0000, 37.0000],
                        ]],
                    },
                }],
                "geometry_metrics": {
                    "height_m": 21.0,
                    "num_floors": 7,
                    "shape_signature_3d": {
                        "volume_count": 1,
                        "floor_plate_count": 7,
                        "height_bands": [21.0],
                    },
                },
            },
            "program": {"building_type": "공동주택"},
        }

    def test_aesthetic_image_job_locks_legal_mass_geometry(self):
        job = build_aesthetic_image_job(self._evidence(), provider="gpt-image", style="brick residential facade")

        self.assertEqual(job["schema_version"], "arr.maas.aesthetic_image_job.v0")
        self.assertEqual(job["source_bundle_id"], "maas-evidence:test-job:maas_01")
        self.assertEqual(job["candidate_id"], "maas_01")
        self.assertEqual(job["mode"], "reference_image_to_image")
        self.assertEqual(job["evidence_policy"]["legal_status_effect"], "none")
        self.assertIn("mass_geojson", job["evidence_policy"]["must_not_change"])
        self.assertTrue(job["prompt"]["constraints"]["lock_silhouette"])
        self.assertEqual(job["prompt"]["constraints"]["lock_height_m"], 21.0)
        self.assertEqual(job["prompt"]["constraints"]["lock_num_floors"], 7)
        self.assertIn("brick residential facade", job["prompt"]["prompt"])
        self.assertEqual(job["reference_render"]["geometry_lock"]["mass_geojson_ref"], "geometry.mass_geojson")
        self.assertEqual(job["reference_render"]["geometry_lock"]["shape_signature_3d"]["floor_plate_count"], 7)
        self.assertEqual(job["locked_geometry"]["geometry_metrics"]["height_m"], 21.0)
        self.assertEqual(job["locked_geometry"]["mass_geojson"]["geometry"]["type"], "Polygon")

        validation = validate_aesthetic_job(job)
        self.assertEqual(validation["status"], "pass")
        self.assertEqual(validation["issues"], [])

    def test_aesthetic_validator_rejects_unanchored_jobs(self):
        job = build_aesthetic_image_job(self._evidence())
        job["source_bundle_id"] = None
        job["prompt"]["constraints"]["lock_silhouette"] = False
        job["evidence_policy"]["legal_status_effect"] = "changes_geometry"

        validation = validate_aesthetic_job(job)

        self.assertEqual(validation["status"], "fail")
        codes = {issue["code"] for issue in validation["issues"]}
        self.assertIn("missing_source_bundle", codes)
        self.assertIn("silhouette_not_locked", codes)
        self.assertIn("legal_status_mutation", codes)

    def test_aesthetic_pipeline_renders_reference_png_and_preserves_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = build_aesthetic_pipeline_result(
                self._evidence(),
                provider="placeholder",
                renderer=ReferencePngRenderer(tmp),
                attach_to_evidence=True,
            )

            self.assertEqual(result["status"], "needs_provider")
            self.assertEqual(result["job_validation"]["status"], "pass")
            self.assertEqual(result["provider_validation"]["status"], "pass")
            self.assertEqual(result["provider_result"]["status"], "needs_provider")
            self.assertTrue(result["reference"]["uri"].endswith(".png"))
            self.assertIn("sha256", result["reference"]["metadata"])
            self.assertEqual(result["evidence"]["assets"]["aesthetic"][0]["legal_status_effect"], "none")

    def test_multi_view_reference_pack_carries_scene_graph(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = build_aesthetic_pipeline_result(
                self._evidence(),
                provider="placeholder",
                renderer=MultiViewReferencePackRenderer(tmp),
                attach_to_evidence=True,
            )

            self.assertEqual(result["status"], "needs_provider")
            self.assertTrue(result["reference"]["uri"].endswith(".multi-view.png"))
            metadata = result["reference"]["metadata"]
            self.assertEqual(metadata["reference_type"], "multi_view_pack")
            self.assertEqual(metadata["views"], ["front", "right", "back", "left", "axon", "top"])
            self.assertEqual(metadata["scene_graph"]["schema_version"], "arr.maas.scene_graph.v0")
            self.assertEqual(metadata["condition_pack"]["schema_version"], "arr.maas.condition_pack.v0")
            self.assertTrue(os.path.exists(metadata["condition_pack"]["scene_graph"]["uri"]))
            self.assertTrue(os.path.exists(metadata["condition_pack"]["camera_poses"]["uri"]))
            self.assertTrue(os.path.exists(metadata["condition_pack"]["facade_planes"]["uri"]))
            self.assertTrue(os.path.exists(metadata["condition_pack"]["projection_manifest"]["uri"]))
            self.assertTrue(os.path.exists(metadata["condition_pack"]["views"]["front"]["silhouette"]["uri"]))
            self.assertTrue(os.path.exists(metadata["condition_pack"]["views"]["front"]["depth"]["uri"]))
            self.assertTrue(os.path.exists(metadata["condition_pack"]["views"]["front"]["floor_guides"]["uri"]))
            with open(metadata["condition_pack"]["projection_manifest"]["uri"], encoding="utf-8") as f:
                projection = json.load(f)
            self.assertEqual(projection["schema_version"], "arr.maas.projection_manifest.v0")
            self.assertGreaterEqual(len(projection["surfaces"]), 4)
            first_surface = projection["surfaces"][0]
            self.assertEqual(len(first_surface["vertices_m"]), 4)
            self.assertEqual(len(first_surface["uv"]), 4)
            for uv in first_surface["uv"]:
                self.assertGreaterEqual(uv[0], 0)
                self.assertLessEqual(uv[0], 1)
                self.assertGreaterEqual(uv[1], 0)
                self.assertLessEqual(uv[1], 1)
            self.assertGreater(first_surface["uv"][1][0], first_surface["uv"][0][0])
            self.assertLess(first_surface["uv"][2][1], first_surface["uv"][1][1])
            self.assertIn(first_surface["view"], {"front", "right", "back", "left"})
            node_types = {node["type"] for node in metadata["scene_graph"]["nodes"]}
            self.assertIn("BuildingMass", node_types)
            self.assertIn("Facade", node_types)

    def test_projection_assets_crop_panels_and_bake_texture_atlas(self):
        with tempfile.TemporaryDirectory() as tmp:
            renderer = MultiViewReferencePackRenderer(tmp)
            reference = renderer.render(build_aesthetic_image_job(self._evidence()))
            generated = os.path.join(tmp, "generated.png")
            from PIL import Image, ImageDraw
            image = Image.new("RGB", (1536, 1536), "#f8fafc")
            draw = ImageDraw.Draw(image)
            for color, box in [
                ("#b45309", (19, 19, 505, 758)),
                ("#8a6f55", (524, 19, 1010, 758)),
                ("#4b5563", (1029, 19, 1515, 758)),
                ("#6b5b45", (19, 777, 505, 1516)),
            ]:
                draw.rectangle(box, fill=color)
            image.save(generated)
            provider = ProviderResult(
                provider="test",
                status="complete",
                assets=[{
                    "asset_id": "asset:test:generated",
                    "uri": generated,
                    "media_type": "image/png",
                    "source_bundle_id": "maas-evidence:test-job:maas_01",
                    "candidate_id": "maas_01",
                    "legal_status_effect": "none",
                    "role": "generated_facade_image",
                }],
            )

            with_panels = attach_facade_panel_assets(provider, reference.metadata)
            baked = attach_baked_projection_assets(with_panels, reference.metadata, atlas_size=768)
            textured = attach_textured_mesh_assets(baked)

            roles = [asset["role"] for asset in textured.assets]
            self.assertIn("facade_panel_image", roles)
            self.assertIn("baked_texture_atlas", roles)
            self.assertIn("texture_bake_manifest", roles)
            self.assertIn("textured_mesh_manifest", roles)
            self.assertIn("textured_gltf", roles)
            self.assertEqual(textured.metadata["texture_bake"]["mode"], "deterministic_panel_atlas_bake")
            self.assertEqual(textured.metadata["textured_mesh"]["mode"], "baked_texture_mesh")
            atlas = next(asset for asset in textured.assets if asset["role"] == "baked_texture_atlas")
            manifest = next(asset for asset in textured.assets if asset["role"] == "texture_bake_manifest")
            mesh_manifest = next(asset for asset in textured.assets if asset["role"] == "textured_mesh_manifest")
            gltf_asset = next(asset for asset in textured.assets if asset["role"] == "textured_gltf")
            self.assertTrue(os.path.exists(atlas["uri"]))
            self.assertTrue(os.path.exists(manifest["uri"]))
            self.assertTrue(os.path.exists(mesh_manifest["uri"]))
            self.assertTrue(os.path.exists(gltf_asset["uri"]))
            with open(manifest["uri"], encoding="utf-8") as f:
                bake = json.load(f)
            self.assertEqual(bake["schema_version"], "arr.maas.texture_bake.v0")
            self.assertGreater(bake["surface_count"], 0)
            self.assertEqual(bake["legal_status_effect"], "none")
            with open(mesh_manifest["uri"], encoding="utf-8") as f:
                mesh = json.load(f)
            self.assertEqual(mesh["schema_version"], "arr.maas.textured_mesh.v0")
            self.assertEqual(mesh["legal_status_effect"], "none")
            self.assertGreater(len(mesh["mesh"]["positions_m"]), 0)
            self.assertGreater(len(mesh["mesh"]["indices"]), 0)
            self.assertGreater(len(mesh["mesh"]["surface_ranges"]), 0)
            with open(gltf_asset["uri"], encoding="utf-8") as f:
                gltf = json.load(f)
            self.assertEqual(gltf["asset"]["version"], "2.0")
            self.assertEqual(gltf["images"][0]["uri"], "baked_texture_atlas.png")
            self.assertGreater(gltf["accessors"][2]["count"], 0)

    def test_openai_and_nano_banana_adapters_are_safe_without_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            renderer = ReferencePngRenderer(tmp)
            env = {
                key: value
                for key, value in os.environ.items()
                if key not in {
                    "OPENAI_API_KEY",
                    "GEMINI_API_KEY",
                    "GOOGLE_API_KEY",
                    "NANO_BANANA_ENDPOINT",
                    "NANO_BANANA_API_KEY",
                }
            }
            with patch.dict(os.environ, env, clear=True):
                for provider in ("gpt-image", "nano-banana"):
                    result = build_aesthetic_pipeline_result(
                        self._evidence(),
                        provider=provider,
                        renderer=renderer,
                    )
                    self.assertEqual(result["status"], "needs_provider")
                    self.assertIn(result["provider_result"]["status"], {"not_configured", "needs_provider"})
                    self.assertEqual(result["provider_validation"]["status"], "pass")

    def test_aesthetic_endpoint_builds_reference_png_from_evidence(self):
        job = OptimizationJob.objects.create(
            pnu="1168011800104170004",
            address="",
            site_polygon={
                "type": "Polygon",
                "coordinates": [[
                    [127.0000, 37.0000],
                    [127.0010, 37.0000],
                    [127.0010, 37.0010],
                    [127.0000, 37.0010],
                    [127.0000, 37.0000],
                ]],
            },
            site_area_m2=264.1,
            job_spec={"options": {"building_type": "공동주택", "algorithm": "maas_legal_envelope"}},
            constraints=[],
            status="complete",
        )
        DesignResult.objects.create(
            job=job,
            generation=0,
            design_id=900010,
            inputs=[],
            outputs={},
            ranking=1.0,
            is_feasible=True,
            is_pareto_optimal=True,
            mass_geojson={
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[
                        [127.0000, 37.0000],
                        [127.0004, 37.0000],
                        [127.0004, 37.0003],
                        [127.0000, 37.0003],
                        [127.0000, 37.0000],
                    ]],
                },
                "properties": {
                    "algorithm": "maas_legal_envelope",
                    "variant_id": "maas_01",
                    "mass_shape": "legal_layered_max",
                    "height": 16.8,
                    "num_floors": 6,
                    "bcr": 39.0,
                    "far": 175.5,
                    "floor_area": 463.0,
                },
            },
        )

        response = self.client.post(
            f"/design/jobs/{job.id}/results/900010/aesthetic/",
            data={"provider": "placeholder", "style": "brick residential facade"},
            content_type="application/json",
            HTTP_HOST="127.0.0.1",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "needs_provider")
        self.assertEqual(data["job"]["evidence_policy"]["legal_status_effect"], "none")
        self.assertEqual(data["reference"]["media_type"], "image/png")
        self.assertTrue(data["reference"]["url"].startswith("/design/maas/aesthetic-assets/references/"))
        self.assertEqual(data["reference"]["metadata"]["reference_type"], "multi_view_pack")
        self.assertEqual(data["reference"]["metadata"]["scene_graph"]["schema_version"], "arr.maas.scene_graph.v0")
        pack = data["reference"]["metadata"]["condition_pack"]
        self.assertEqual(pack["schema_version"], "arr.maas.condition_pack.v0")
        self.assertTrue(pack["scene_graph"]["url"].startswith("/design/maas/aesthetic-assets/references/"))
        self.assertTrue(pack["projection_manifest"]["url"].startswith("/design/maas/aesthetic-assets/references/"))
        self.assertTrue(pack["views"]["front"]["silhouette"]["url"].endswith("/silhouette/front.png"))
        self.assertTrue(pack["views"]["front"]["depth"]["url"].endswith("/depth/front.png"))
        self.assertTrue(pack["views"]["front"]["floor_guides"]["url"].endswith("/floor_guides/front.png"))
        self.assertEqual(data["provider_result"]["provider"], "placeholder")
        self.assertEqual(data["evidence"]["assets"]["aesthetic"][0]["legal_status_effect"], "none")
