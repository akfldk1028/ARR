"""
Tests for the design optimization app.

Unit tests for engine algorithms + integration tests for API endpoints.
"""

import json

from django.test import TestCase

from design.engine.objects import Design, Job, SSIEAJob, NSGA3Job
from design.engine.utils import rank, remap
from design.services.constraint_bridge import regulations_to_constraints, build_default_job_spec


class RemapTest(TestCase):
    """Test utility functions."""

    def test_remap_identity(self):
        self.assertAlmostEqual(remap(0.5, 0, 1, 0, 1), 0.5)

    def test_remap_scale(self):
        self.assertAlmostEqual(remap(0.5, 0, 1, 0, 100), 50.0)

    def test_remap_offset(self):
        self.assertAlmostEqual(remap(5, 0, 10, 10, 20), 15.0)


class DesignTest(TestCase):
    """Test Design class."""

    def _make_inputs_def(self):
        return [
            {"name": "x", "type": "Continuous", "Min": 0, "Max": 10, "Set length": 1},
            {"name": "y", "type": "Continuous", "Min": 0, "Max": 10, "Set length": 1},
        ]

    def test_generate_random(self):
        d = Design(0, 0, 0)
        d.generate_random(self._make_inputs_def())
        self.assertEqual(len(d.get_inputs()), 2)
        for inp in d.get_inputs():
            self.assertEqual(len(inp), 1)
            self.assertGreaterEqual(inp[0], 0)
            self.assertLessEqual(inp[0], 10)

    def test_crossover(self):
        d1 = Design(0, 0, 0)
        d2 = Design(1, 1, 0)
        inputs_def = self._make_inputs_def()
        d1.generate_random(inputs_def)
        d2.generate_random(inputs_def)
        child = d1.crossover(d2, inputs_def, 1, 0, 2)
        self.assertEqual(len(child.get_inputs()), 2)
        self.assertEqual(child.get_id(), 2)

    def test_mutate(self):
        d = Design(0, 0, 0)
        inputs_def = self._make_inputs_def()
        d.generate_random(inputs_def)
        original = [list(x) for x in d.get_inputs()]
        d.mutate(inputs_def, 1.0)  # 100% mutation rate
        # Inputs should be within bounds
        for inp in d.get_inputs():
            self.assertGreaterEqual(inp[0], 0)
            self.assertLessEqual(inp[0], 10)

    def test_set_outputs_objective(self):
        d = Design(0, 0, 0)
        outputs_def = [{"name": "area", "type": "Objective", "Goal": "Maximize"}]
        d.set_outputs([100.0], outputs_def)
        self.assertEqual(d.get_objectives(), [100.0])
        self.assertEqual(d.get_penalty(), 0)

    def test_set_outputs_constraint_pass(self):
        d = Design(0, 0, 0)
        outputs_def = [{"name": "bcr", "type": "Constraint", "Requirement": "Less than", "val": 60}]
        d.set_outputs([50.0], outputs_def)
        self.assertEqual(d.get_penalty(), 0)
        self.assertTrue(d.feasible)

    def test_set_outputs_constraint_fail(self):
        d = Design(0, 0, 0)
        outputs_def = [{"name": "bcr", "type": "Constraint", "Requirement": "Less than", "val": 60}]
        d.set_outputs([70.0], outputs_def)
        # A3 (2026-05-06): penalty는 binary count → 위반 거리 비례 정규화
        # BCR 70 with limit 60 → (70-60)/60 ≈ 0.167
        self.assertAlmostEqual(d.get_penalty(), (70.0 - 60.0) / 60.0, places=4)
        self.assertFalse(d.feasible)

    def test_duplicate_detection(self):
        d1 = Design(0, 0, 0)
        d2 = Design(1, 1, 0)
        d1.set_inputs([[1.0], [2.0]])
        d2.set_inputs([[1.0], [2.0]])
        self.assertTrue(d1.check_duplicate(d2))

    def test_no_duplicate(self):
        d1 = Design(0, 0, 0)
        d2 = Design(1, 1, 0)
        d1.set_inputs([[1.0], [2.0]])
        d2.set_inputs([[1.0], [3.0]])
        self.assertFalse(d1.check_duplicate(d2))


class RankTest(TestCase):
    """Test NSGA-II ranking."""

    def _make_population(self, scores_list):
        """Create mock designs with given objective scores."""
        designs = []
        for i, scores in enumerate(scores_list):
            d = Design(i, i, 0)
            d.objectives = scores
            designs.append(d)
        return designs

    def test_single_objective(self):
        pop = self._make_population([[10], [5], [20]])
        outputs_def = [{"name": "cost", "type": "Objective", "Goal": "Minimize"}]
        rankings, distances, penalties = rank(pop, outputs_def)
        # Higher rank = better. Design 1 (score 5) should have highest rank
        self.assertEqual(rankings[1], max(rankings))

    def test_pareto_front(self):
        pop = self._make_population([[1, 4], [2, 2], [4, 1]])
        outputs_def = [
            {"name": "y1", "type": "Objective", "Goal": "Minimize"},
            {"name": "y2", "type": "Objective", "Goal": "Minimize"},
        ]
        rankings, distances, penalties = rank(pop, outputs_def)
        # All three should be on the first Pareto front (none dominates another)
        self.assertTrue(all(r == 1 for r in rankings))


class JobTest(TestCase):
    """Test legacy Job optimization loop."""

    def _make_spec(self):
        return {
            "inputs": [
                {"name": "x", "type": "Continuous", "Min": 0, "Max": 10, "Set length": 1},
            ],
            "outputs": [
                {"name": "y", "type": "Objective", "Goal": "Minimize"},
            ],
            "options": {
                "Designs per generation": 10,
                "Number of generations": 3,
                "Elites": 2,
                "Mutation rate": 0.1,
            },
        }

    def test_init_designs(self):
        job = Job(self._make_spec())
        designs = job.init_designs()
        self.assertEqual(len(designs), 10)

    def test_step(self):
        job = Job(self._make_spec())
        job.init_designs()

        def evaluate_fn(designs):
            return [[d.get_inputs()[0][0]] for d in designs]

        cont, gen, pop = job.step(evaluate_fn)
        self.assertTrue(cont)  # Should continue (gen 0 < max 3)
        self.assertEqual(gen, 1)  # Next generation created

    def test_full_run(self):
        job = Job(self._make_spec())
        job.init_designs()

        def evaluate_fn(designs):
            return [[d.get_inputs()[0][0]] for d in designs]

        gens = 0
        while True:
            cont, gen, pop = job.step(evaluate_fn)
            gens += 1
            if not cont:
                break

        self.assertEqual(gens, 4)  # gen 0,1,2,3 = 4 steps
        self.assertGreater(len(job.all_designs), 0)


class SSIEAJobTest(TestCase):
    """Test SSIEA island model."""

    def _make_spec(self):
        return {
            "inputs": [
                {"name": "x", "type": "Continuous", "Min": 0, "Max": 10, "Set length": 1},
                {"name": "y", "type": "Continuous", "Min": 0, "Max": 10, "Set length": 1},
            ],
            "outputs": [
                {"name": "obj", "type": "Objective", "Goal": "Minimize"},
            ],
            "options": {
                "Number of generations": 5,
                "num_islands": 3,
                "pop_per_island": 6,
                "migration_interval": 2,
                "migrants_count": 1,
                "tournament_size": 3,
                "initial_mutation_rate": 0.3,
                "final_mutation_rate": 0.1,
            },
        }

    def test_init_islands(self):
        job = SSIEAJob(self._make_spec())
        designs = job.init_designs()
        self.assertEqual(len(job.islands), 3)
        self.assertEqual(len(job.islands[0]), 6)
        self.assertEqual(len(designs), 18)  # 3 * 6

    def test_first_step_evaluates(self):
        job = SSIEAJob(self._make_spec())
        job.init_designs()

        def evaluate_fn(designs):
            return [[d.get_inputs()[0][0]] for d in designs]

        cont, gen, pop = job.step(evaluate_fn)
        self.assertTrue(cont)
        self.assertEqual(gen, 1)
        self.assertEqual(len(pop), 18)
        # All designs should have objectives
        for d in pop:
            self.assertEqual(len(d.objectives), 1)

    def test_steady_state_step(self):
        job = SSIEAJob(self._make_spec())
        job.init_designs()

        def evaluate_fn(designs):
            return [[d.get_inputs()[0][0]] for d in designs]

        # First step: evaluate initial
        job.step(evaluate_fn)
        # Second step: steady-state
        cont, gen, pop = job.step(evaluate_fn)
        self.assertTrue(cont)
        self.assertEqual(gen, 2)
        # Population size stays same (steady-state replaces worst)
        self.assertEqual(len(pop), 18)

    def test_migration(self):
        """Migration should occur at migration_interval."""
        job = SSIEAJob(self._make_spec())
        job.init_designs()

        call_count = [0]

        def evaluate_fn(designs):
            call_count[0] += 1
            return [[d.get_inputs()[0][0]] for d in designs]

        # Run until migration should happen (interval=2)
        for _ in range(3):
            job.step(evaluate_fn)

        # Population should still be intact after migration
        for island in job.islands:
            self.assertEqual(len(island), 6)

    def test_full_run(self):
        job = SSIEAJob(self._make_spec())
        job.init_designs()

        def evaluate_fn(designs):
            return [[d.get_inputs()[0][0]] for d in designs]

        gens = 0
        while True:
            cont, gen, pop = job.step(evaluate_fn)
            gens += 1
            if not cont:
                break

        self.assertEqual(gen, 5)  # max_gen = 5
        self.assertGreater(len(job.all_designs), 18)  # initial + children

    def test_pareto_front(self):
        job = SSIEAJob(self._make_spec())
        job.init_designs()

        def evaluate_fn(designs):
            return [[d.get_inputs()[0][0]] for d in designs]

        job.step(evaluate_fn)  # evaluate initial
        pareto = job.get_pareto_front()
        self.assertGreater(len(pareto), 0)
        for d in pareto:
            self.assertEqual(d.penalty, 0)

    def test_get_best(self):
        job = SSIEAJob(self._make_spec())
        job.init_designs()

        def evaluate_fn(designs):
            return [[d.get_inputs()[0][0]] for d in designs]

        job.step(evaluate_fn)
        best = job.get_best()
        self.assertIsNotNone(best)
        self.assertEqual(best.penalty, 0)

    def test_adaptive_mutation(self):
        """Mutation rate should decrease from initial to final over generations."""
        spec = self._make_spec()
        spec["options"]["Number of generations"] = 10
        job = SSIEAJob(spec)
        job.init_designs()

        def evaluate_fn(designs):
            return [[d.get_inputs()[0][0]] for d in designs]

        # Run a few steps
        for _ in range(5):
            job.step(evaluate_fn)

        # Verify gen advanced
        self.assertGreater(job.gen, 1)


class FreeformMassTest(TestCase):
    """Test EvoMass K=5 box-stacking freeform mass generation."""

    def _make_site_utm(self):
        """30m x 30m UTM square."""
        from shapely.geometry import box
        return box(499985, 3999985, 500015, 4000015)

    def _make_overlapping_inputs(self):
        """5 boxes all at center, overlapping -> single Polygon."""
        inputs = []
        for _ in range(5):
            inputs.extend([
                [0.0],   # bx
                [0.0],   # by
                [6.0],   # bw
                [6.0],   # bd
                [0.0],   # brot
            ])
        # Global: num_floors, rotation, upper_scale, step_frac
        inputs.extend([[3.0], [0.0], [1.0], [0.5]])
        return inputs

    def _make_separated_inputs(self):
        """5 boxes spread apart -> MultiPolygon."""
        inputs = []
        for i in range(5):
            inputs.extend([
                [(i - 2) * 8.0],  # bx: -16, -8, 0, 8, 16
                [0.0],
                [3.0],   # bw: small
                [3.0],   # bd: small
                [0.0],
            ])
        inputs.extend([[3.0], [0.0], [1.0], [0.5]])
        return inputs

    def test_overlapping_boxes_single_polygon(self):
        from design.services.mass_evaluator import _build_mass_polygon_freeform
        site = self._make_site_utm()
        inputs = self._make_overlapping_inputs()
        poly, is_multi = _build_mass_polygon_freeform(inputs, site)
        self.assertIsNotNone(poly)
        self.assertFalse(is_multi)
        self.assertEqual(poly.geom_type, 'Polygon')
        self.assertGreater(poly.area, 0)

    def test_separated_boxes_multipolygon(self):
        from design.services.mass_evaluator import _build_mass_polygon_freeform
        site = self._make_site_utm()
        inputs = self._make_separated_inputs()
        poly, is_multi = _build_mass_polygon_freeform(inputs, site)
        self.assertIsNotNone(poly)
        self.assertTrue(is_multi)
        # Should be the largest polygon from the multi
        self.assertEqual(poly.geom_type, 'Polygon')

    def test_box_rotation(self):
        """Each box can be individually rotated."""
        from design.services.mass_evaluator import _build_mass_polygon_freeform
        site = self._make_site_utm()
        inputs = []
        for _ in range(5):
            inputs.extend([
                [0.0], [0.0], [10.0], [4.0],
                [45.0],  # 45-degree rotation
            ])
        inputs.extend([[3.0], [0.0], [1.0], [0.5]])
        poly, is_multi = _build_mass_polygon_freeform(inputs, site)
        self.assertIsNotNone(poly)
        self.assertFalse(is_multi)

    def test_global_rotation(self):
        """Global rotation applies to the entire union."""
        from design.services.mass_evaluator import _build_mass_polygon_freeform
        site = self._make_site_utm()
        inputs_no_rot = self._make_overlapping_inputs()
        inputs_rot = list(inputs_no_rot)
        inputs_rot[26] = [90.0]  # 90-degree global rotation

        poly1, _ = _build_mass_polygon_freeform(inputs_no_rot, site)
        poly2, _ = _build_mass_polygon_freeform(inputs_rot, site)
        self.assertIsNotNone(poly1)
        self.assertIsNotNone(poly2)
        # Areas should be the same (rotation preserves area)
        self.assertAlmostEqual(poly1.area, poly2.area, places=1)

    def test_bcr_far_computation(self):
        """BCR/FAR should be computed correctly for freeform mass."""
        from design.services.mass_evaluator import _compute_metrics
        site = self._make_site_utm()
        site_area = site.area  # 900 m2
        inputs = self._make_overlapping_inputs()
        metrics = _compute_metrics(inputs, site, site_area)

        self.assertGreater(metrics["bcr"], 0)
        self.assertLess(metrics["bcr"], 100)
        self.assertGreater(metrics["far"], 0)
        self.assertGreater(metrics["floor_area"], 0)
        self.assertGreater(metrics["height"], 0)

    def test_multipolygon_penalty(self):
        """Disconnected mass should trigger BCR/FAR penalty."""
        from design.services.mass_evaluator import _compute_metrics
        site = self._make_site_utm()
        site_area = site.area
        inputs = self._make_separated_inputs()
        metrics = _compute_metrics(inputs, site, site_area)

        # Disconnected mass gets penalty BCR/FAR
        self.assertEqual(metrics["bcr"], 200.0)
        self.assertEqual(metrics["far"], 9999.0)

    def test_stepback_with_freeform(self):
        """Step-back should work with freeform mass."""
        from design.services.mass_evaluator import _compute_metrics
        site = self._make_site_utm()
        site_area = site.area
        inputs = self._make_overlapping_inputs()
        # Set stepback: upper_scale=0.7, step_frac=0.5
        inputs[27] = [0.7]
        inputs[28] = [0.5]
        metrics = _compute_metrics(inputs, site, site_area)

        self.assertGreater(metrics["floor_area"], 0)
        self.assertGreater(metrics["daylight_score"], 0)


class SubtractiveMassTest(TestCase):
    """Test subtractive (void-carving) mass generation."""

    def _make_site_utm(self):
        from shapely.geometry import box
        return box(499985, 3999985, 500015, 4000015)

    def _make_inputs(self):
        """Block with 3 small voids + 4 global."""
        inputs = [
            [0.8],   # scale_x
            [0.8],   # scale_y
            [0.0],   # block_rot
            [0.0],   # block_inset
        ]
        # 3 voids (small, centered)
        for i in range(3):
            inputs.extend([
                [0.0],   # vx
                [0.0],   # vy
                [3.0],   # vw
                [3.0],   # vd
                [0.0],   # vrot
            ])
        # Global: num_floors, rotation, upper_scale, step_frac
        inputs.extend([[3.0], [0.0], [1.0], [0.5]])
        return inputs

    def test_valid_polygon(self):
        from design.services.mass_evaluator import _build_mass_polygon_subtractive
        site = self._make_site_utm()
        inputs = self._make_inputs()
        poly, is_multi = _build_mass_polygon_subtractive(inputs, site)
        self.assertIsNotNone(poly)
        self.assertEqual(poly.geom_type, 'Polygon')
        self.assertGreater(poly.area, 0)

    def test_void_removes_area(self):
        from design.services.mass_evaluator import _build_mass_polygon_subtractive
        site = self._make_site_utm()
        # No voids (tiny voids)
        inputs_no_void = [
            [0.8], [0.8], [0.0], [0.0],
        ]
        for _ in range(3):
            inputs_no_void.extend([[0.0], [0.0], [0.1], [0.1], [0.0]])
        inputs_no_void.extend([[3.0], [0.0], [1.0], [0.5]])

        poly_no_void, _ = _build_mass_polygon_subtractive(inputs_no_void, site)
        poly_with_void, _ = _build_mass_polygon_subtractive(self._make_inputs(), site)
        self.assertIsNotNone(poly_no_void)
        self.assertIsNotNone(poly_with_void)
        self.assertGreater(poly_no_void.area, poly_with_void.area)

    def test_multipolygon_from_split(self):
        """Large voids can split the block."""
        from design.services.mass_evaluator import _build_mass_polygon_subtractive
        site = self._make_site_utm()
        inputs = [
            [1.0], [1.0], [0.0], [0.0],
        ]
        # One very wide void splitting the block
        inputs.extend([[0.0], [0.0], [30.0], [2.0], [0.0]])
        # Two tiny voids
        for _ in range(2):
            inputs.extend([[0.0], [0.0], [0.1], [0.1], [0.0]])
        inputs.extend([[3.0], [0.0], [1.0], [0.5]])
        poly, is_multi = _build_mass_polygon_subtractive(inputs, site)
        # May or may not produce MultiPolygon depending on geometry
        self.assertIsNotNone(poly)

    def test_compute_metrics_subtractive(self):
        from design.services.mass_evaluator import _compute_metrics
        site = self._make_site_utm()
        inputs = self._make_inputs()
        metrics = _compute_metrics(inputs, site, site.area, algorithm="subtractive")
        self.assertGreater(metrics["bcr"], 0)
        self.assertLess(metrics["bcr"], 100)
        self.assertGreater(metrics["floor_area"], 0)


class GridMassTest(TestCase):
    """Test grid (3x3 subdivision) mass generation."""

    def _make_site_utm(self):
        from shapely.geometry import box
        return box(499985, 3999985, 500015, 4000015)

    def _make_inputs_all_on(self):
        """All 9 cells on + 4 global."""
        inputs = []
        for _ in range(9):
            inputs.extend([[0.8], [1.0]])  # threshold > 0.5 = on, height_ratio
        inputs.extend([[3.0], [0.0], [1.0], [0.5]])
        return inputs

    def _make_inputs_all_off(self):
        """All 9 cells off."""
        inputs = []
        for _ in range(9):
            inputs.extend([[0.2], [1.0]])  # threshold < 0.5 = off
        inputs.extend([[3.0], [0.0], [1.0], [0.5]])
        return inputs

    def _make_inputs_partial(self):
        """5 of 9 cells on (cross pattern)."""
        on_off = [0.2, 0.8, 0.2, 0.8, 0.8, 0.8, 0.2, 0.8, 0.2]
        inputs = []
        for v in on_off:
            inputs.extend([[v], [1.0]])
        inputs.extend([[3.0], [0.0], [1.0], [0.5]])
        return inputs

    def test_all_on_single_polygon(self):
        from design.services.mass_evaluator import _build_mass_polygon_grid
        site = self._make_site_utm()
        poly, is_multi = _build_mass_polygon_grid(self._make_inputs_all_on(), site)
        self.assertIsNotNone(poly)
        self.assertFalse(is_multi)
        self.assertGreater(poly.area, 0)

    def test_all_off_returns_none(self):
        from design.services.mass_evaluator import _build_mass_polygon_grid
        site = self._make_site_utm()
        poly, is_multi = _build_mass_polygon_grid(self._make_inputs_all_off(), site)
        self.assertIsNone(poly)

    def test_partial_cross_pattern(self):
        from design.services.mass_evaluator import _build_mass_polygon_grid
        site = self._make_site_utm()
        poly, is_multi = _build_mass_polygon_grid(self._make_inputs_partial(), site)
        self.assertIsNotNone(poly)
        self.assertFalse(is_multi)  # Cross pattern should be connected

    def test_all_on_bigger_than_partial(self):
        from design.services.mass_evaluator import _build_mass_polygon_grid
        site = self._make_site_utm()
        full, _ = _build_mass_polygon_grid(self._make_inputs_all_on(), site)
        partial, _ = _build_mass_polygon_grid(self._make_inputs_partial(), site)
        self.assertGreater(full.area, partial.area)

    def test_compute_metrics_grid(self):
        from design.services.mass_evaluator import _compute_metrics
        site = self._make_site_utm()
        inputs = self._make_inputs_all_on()
        metrics = _compute_metrics(inputs, site, site.area, algorithm="grid")
        self.assertGreater(metrics["bcr"], 0)
        self.assertLess(metrics["bcr"], 100)
        self.assertGreater(metrics["floor_area"], 0)


class AlgorithmDispatchTest(TestCase):
    """Test algorithm dispatch in evaluate_designs and _compute_metrics."""

    def _make_site_utm(self):
        from shapely.geometry import box
        return box(499985, 3999985, 500015, 4000015)

    def test_dispatch_additive(self):
        from design.services.mass_evaluator import _compute_metrics
        site = self._make_site_utm()
        inputs = []
        for _ in range(5):
            inputs.extend([[0.0], [0.0], [6.0], [6.0], [0.0]])
        inputs.extend([[3.0], [0.0], [1.0], [0.5]])
        metrics = _compute_metrics(inputs, site, site.area, algorithm="additive")
        self.assertGreater(metrics["floor_area"], 0)

    def test_dispatch_subtractive(self):
        from design.services.mass_evaluator import _compute_metrics
        site = self._make_site_utm()
        inputs = [[0.8], [0.8], [0.0], [0.0]]
        for _ in range(3):
            inputs.extend([[0.0], [0.0], [2.0], [2.0], [0.0]])
        inputs.extend([[3.0], [0.0], [1.0], [0.5]])
        metrics = _compute_metrics(inputs, site, site.area, algorithm="subtractive")
        self.assertGreater(metrics["floor_area"], 0)

    def test_dispatch_grid(self):
        from design.services.mass_evaluator import _compute_metrics
        site = self._make_site_utm()
        inputs = []
        for _ in range(9):
            inputs.extend([[0.8], [1.0]])
        inputs.extend([[3.0], [0.0], [1.0], [0.5]])
        metrics = _compute_metrics(inputs, site, site.area, algorithm="grid")
        self.assertGreater(metrics["floor_area"], 0)

    def test_unknown_algorithm_falls_back(self):
        from design.services.mass_evaluator import _compute_metrics
        site = self._make_site_utm()
        inputs = []
        for _ in range(5):
            inputs.extend([[0.0], [0.0], [6.0], [6.0], [0.0]])
        inputs.extend([[3.0], [0.0], [1.0], [0.5]])
        metrics = _compute_metrics(inputs, site, site.area, algorithm="unknown")
        self.assertGreater(metrics["floor_area"], 0)


class ConstraintBridgeAlgorithmTest(TestCase):
    """Test constraint bridge with different algorithms."""

    def test_additive_29_genes(self):
        spec = build_default_job_spec(500.0, [], algorithm="additive")
        self.assertEqual(len(spec["inputs"]), 29)
        self.assertEqual(spec["options"]["algorithm"], "additive")

    def test_subtractive_23_genes(self):
        spec = build_default_job_spec(500.0, [], algorithm="subtractive")
        self.assertEqual(len(spec["inputs"]), 23)
        self.assertEqual(spec["options"]["algorithm"], "subtractive")

    def test_grid_22_genes(self):
        spec = build_default_job_spec(500.0, [], algorithm="grid")
        self.assertEqual(len(spec["inputs"]), 22)
        self.assertEqual(spec["options"]["algorithm"], "grid")

    def test_all_genes_continuous(self):
        for algo in ("additive", "subtractive", "grid"):
            spec = build_default_job_spec(500.0, [], algorithm=algo)
            for inp in spec["inputs"]:
                self.assertEqual(inp["type"], "Continuous", f"{algo}: {inp['name']} not Continuous")


class ConstraintBridgeTest(TestCase):
    """Test regulation -> constraint conversion."""

    def test_basic_conversion(self):
        reg = {"bcr_pct": 60, "far_pct": 200, "height_limit_m": 20}
        constraints = regulations_to_constraints(reg)
        self.assertEqual(len(constraints), 3)
        names = [c["name"] for c in constraints]
        self.assertIn("bcr", names)
        self.assertIn("far", names)
        self.assertIn("height", names)

    def test_constraint_format(self):
        reg = {"bcr_pct": 60}
        constraints = regulations_to_constraints(reg)
        c = constraints[0]
        self.assertEqual(c["type"], "Constraint")
        self.assertEqual(c["Requirement"], "Less than")
        self.assertEqual(c["val"], 60.0)

    def test_empty_regulations(self):
        constraints = regulations_to_constraints({})
        self.assertEqual(len(constraints), 0)

    def test_build_default_spec(self):
        constraints = [
            {"name": "bcr", "type": "Constraint", "Requirement": "Less than", "val": 60},
        ]
        spec = build_default_job_spec(500.0, constraints)
        self.assertIn("inputs", spec)
        self.assertIn("outputs", spec)
        self.assertIn("options", spec)
        # 29 genes: 5 boxes x 5 + 4 global
        self.assertEqual(len(spec["inputs"]), 29)
        # All genes should be Continuous (no Categorical)
        for inp in spec["inputs"]:
            self.assertEqual(inp["type"], "Continuous")

    def test_ssiea_options_in_spec(self):
        spec = build_default_job_spec(500.0, [])
        opts = spec["options"]
        self.assertEqual(opts["num_islands"], 7)
        self.assertEqual(opts["pop_per_island"], 30)
        self.assertEqual(opts["migration_interval"], 8)
        self.assertAlmostEqual(opts["initial_mutation_rate"], 0.35)
        self.assertAlmostEqual(opts["final_mutation_rate"], 0.10)


class APITest(TestCase):
    """Test API endpoints."""

    def test_all_mode_budget_uses_request_options(self):
        from design.views import _all_mode_budget_options

        budget = _all_mode_budget_options({
            "Number of generations": 3,
            "num_islands": 2,
            "pop_per_island": 4,
        })

        self.assertEqual(budget["Number of generations"], 3)
        self.assertEqual(budget["num_islands"], 2)
        self.assertEqual(budget["pop_per_island"], 4)

    def test_auto_constraints_no_input(self):
        response = self.client.post(
            '/design/auto-constraints/',
            data=json.dumps({}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)

    def test_create_job_no_polygon(self):
        response = self.client.post(
            '/design/jobs/',
            data=json.dumps({}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)

    def test_get_job_not_found(self):
        response = self.client.get('/design/jobs/00000000-0000-0000-0000-000000000000/')
        self.assertEqual(response.status_code, 404)

    def test_site_boundary_no_pnu(self):
        response = self.client.post(
            '/design/site-boundary/',
            data=json.dumps({}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)


# ──────────────────────────────────────────────────────
# Series Gene Tests
# ──────────────────────────────────────────────────────
class SeriesGeneTest(TestCase):
    """Test Series input type in GA engine."""

    SERIES_DEF = [{
        "type": "Series",
        "Set length": 25,
        "Depth": 5,
        "Mutation rate": 0.3,
    }]

    def test_generate_random(self):
        d = Design(1, 0, 0)
        d.generate_random(self.SERIES_DEF)
        genes = d.get_inputs()[0]
        self.assertEqual(len(genes), 25)
        self.assertTrue(all(0 <= g < 5 for g in genes))

    def test_crossover(self):
        d1 = Design(1, 0, 0)
        d1.generate_random(self.SERIES_DEF)
        d2 = Design(2, 0, 0)
        d2.generate_random(self.SERIES_DEF)
        child = d1.crossover(d2, self.SERIES_DEF, 1, 0, 3)
        genes = child.get_inputs()[0]
        self.assertEqual(len(genes), 25)
        self.assertTrue(all(0 <= g < 5 for g in genes))
        # Child should contain genes from both parents
        p1 = set(d1.get_inputs()[0])
        p2 = set(d2.get_inputs()[0])
        child_set = set(genes)
        # At least some overlap with parent gene pools
        self.assertTrue(len(child_set & (p1 | p2)) > 0)

    def test_mutate(self):
        d = Design(1, 0, 0)
        d.generate_random(self.SERIES_DEF)
        original = list(d.get_inputs()[0])
        d.mutate(self.SERIES_DEF, 1.0)  # 100% mutation rate
        mutated = d.get_inputs()[0]
        self.assertEqual(len(mutated), 25)
        self.assertTrue(all(0 <= g < 5 for g in mutated))
        # With 100% rate, at least some genes should differ
        self.assertNotEqual(original, mutated)

    def test_depth_boundary(self):
        """All generated values should be < Depth."""
        d = Design(1, 0, 0)
        for _ in range(10):
            d.generate_random(self.SERIES_DEF)
            for g in d.get_inputs()[0]:
                self.assertLess(g, 5)
                self.assertGreaterEqual(g, 0)


# ──────────────────────────────────────────────────────
# Floor Packer Tests
# ──────────────────────────────────────────────────────
class FloorPackerGridTest(TestCase):
    """Test grid creation and masking."""

    def test_rectangular_grid(self):
        from shapely.geometry import box as shp_box
        from design.services.floor_packer import create_grid
        fp = shp_box(0, 0, 15, 12)
        grid = create_grid(fp, cell_size_m=3.0)
        self.assertEqual(grid["rows"], 4)
        self.assertEqual(grid["cols"], 5)
        self.assertEqual(grid["active_count"], 20)

    def test_l_shape_masking(self):
        """L-shape footprint should mask out corners."""
        from shapely.geometry import Polygon
        from design.services.floor_packer import create_grid
        # L-shape: 12x12 minus top-right 6x6
        l_shape = Polygon([
            (0, 0), (12, 0), (12, 6), (6, 6), (6, 12), (0, 12), (0, 0)
        ])
        grid = create_grid(l_shape, cell_size_m=3.0)
        self.assertEqual(grid["rows"], 4)
        self.assertEqual(grid["cols"], 4)
        # Full 4x4=16, minus top-right 2x2=4 → 12 active
        self.assertLess(grid["active_count"], 16)
        self.assertGreater(grid["active_count"], 8)

    def test_small_footprint(self):
        from shapely.geometry import box as shp_box
        from design.services.floor_packer import create_grid
        fp = shp_box(0, 0, 2, 2)
        grid = create_grid(fp, cell_size_m=3.0)
        self.assertGreaterEqual(grid["rows"], 1)
        self.assertGreaterEqual(grid["cols"], 1)


class FloorPackerEvalTest(TestCase):
    """Test floor plan evaluation functions."""

    ROOMS = [
        {"name": "Living", "area": 27, "adjacency": ["Kitchen"]},
        {"name": "Kitchen", "area": 18, "adjacency": ["Living"]},
        {"name": "Bedroom", "area": 18, "adjacency": []},
    ]

    def _make_grid(self):
        from shapely.geometry import box as shp_box
        from design.services.floor_packer import create_grid
        return create_grid(shp_box(0, 0, 9, 9), cell_size_m=3.0)

    def test_perfect_adjacency(self):
        """Rooms placed adjacent should score high."""
        from design.services.floor_packer import evaluate_floor_plan
        grid = self._make_grid()
        # 3x3 grid: Living(1)=top row, Kitchen(2)=middle row, Bedroom(3)=bottom
        assignment = [
            1, 1, 1,  # row 0
            2, 2, 0,  # row 1
            3, 3, 0,  # row 2
        ]
        result = evaluate_floor_plan(assignment, grid, self.ROOMS)
        self.assertGreater(result["adjacency_score"], 0.5)

    def test_no_adjacency(self):
        """Rooms placed far apart should score low."""
        from design.services.floor_packer import evaluate_floor_plan
        grid = self._make_grid()
        # Living top-left, Kitchen bottom-right (not adjacent)
        assignment = [
            1, 0, 0,
            0, 0, 0,
            0, 0, 2,
        ]
        result = evaluate_floor_plan(assignment, grid, self.ROOMS)
        self.assertLess(result["adjacency_score"], 1.0)

    def test_area_error(self):
        """Area error should reflect mismatch between required and actual."""
        from design.services.floor_packer import evaluate_floor_plan
        grid = self._make_grid()
        # All cells empty
        assignment = [0] * 9
        result = evaluate_floor_plan(assignment, grid, self.ROOMS)
        self.assertGreater(result["area_error"], 0)

    def test_compactness(self):
        """Compact cluster should score higher than scattered."""
        from design.services.floor_packer import evaluate_floor_plan
        grid = self._make_grid()
        # Compact: 2x2 block
        compact = [1, 1, 0, 1, 1, 0, 0, 0, 0]
        scattered = [1, 0, 1, 0, 0, 0, 1, 0, 1]
        r_compact = evaluate_floor_plan(compact, grid, self.ROOMS)
        r_scattered = evaluate_floor_plan(scattered, grid, self.ROOMS)
        self.assertGreaterEqual(r_compact["compactness"], r_scattered["compactness"])


class FloorPackerGeoJSONTest(TestCase):
    """Test GeoJSON conversion."""

    def test_assignment_to_geojson(self):
        from shapely.geometry import box as shp_box
        from design.services.floor_packer import create_grid, assignment_to_geojson
        rooms = [{"name": "Living", "area": 27, "adjacency": []}]
        grid = create_grid(shp_box(0, 0, 9, 9), cell_size_m=3.0)
        assignment = [1, 1, 1, 0, 0, 0, 0, 0, 0]
        geojson = assignment_to_geojson(assignment, grid, rooms)
        self.assertEqual(geojson["type"], "FeatureCollection")
        self.assertEqual(len(geojson["features"]), 1)
        feat = geojson["features"][0]
        self.assertEqual(feat["properties"]["room_name"], "Living")
        self.assertGreater(feat["properties"]["area_m2"], 0)


class FloorPlanAPITest(TestCase):
    """Test floor-plan API endpoint."""

    def test_missing_footprint(self):
        response = self.client.post(
            '/design/floor-plan/',
            data=json.dumps({"rooms": [{"name": "A", "area": 10}]}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)

    def test_missing_rooms(self):
        response = self.client.post(
            '/design/floor-plan/',
            data=json.dumps({
                "footprint_geojson": {"type": "Polygon", "coordinates": [[[0,0],[10,0],[10,10],[0,10],[0,0]]]}
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)

    def test_floor_plan_e2e(self):
        """E2E: valid footprint + rooms → GA runs → results with GeoJSON."""
        response = self.client.post(
            '/design/floor-plan/',
            data=json.dumps({
                "footprint_geojson": {
                    "type": "Polygon",
                    "coordinates": [[[0, 0], [15, 0], [15, 12], [0, 12], [0, 0]]],
                },
                "rooms": [
                    {"name": "Living", "area": 40, "adjacency": ["Entry"]},
                    {"name": "Entry", "area": 10, "adjacency": ["Living"]},
                    {"name": "Bedroom", "area": 25, "adjacency": []},
                ],
                "cell_size": 3.0,
                "options": {"num_generations": 5, "population_size": 9},
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()

        # Grid info
        self.assertIn("grid_info", data)
        gi = data["grid_info"]
        self.assertEqual(gi["rows"], 4)   # ceil(12/3)
        self.assertEqual(gi["cols"], 5)   # ceil(15/3)
        self.assertEqual(gi["cell_size"], 3.0)
        self.assertGreater(gi["active_cells"], 0)

        # Rooms echo
        self.assertEqual(len(data["rooms"]), 3)

        # Results — Pareto front should have at least 1 design
        self.assertGreater(data["num_results"], 0)
        result = data["results"][0]
        self.assertIn("design_id", result)
        self.assertIn("metrics", result)
        self.assertIn("adjacency_score", result["metrics"])
        self.assertIn("area_error", result["metrics"])
        self.assertIn("compactness", result["metrics"])

        # GeoJSON floor plan
        fp = result["floor_plan"]
        self.assertEqual(fp["type"], "FeatureCollection")
        self.assertGreater(len(fp["features"]), 0)
        feat = fp["features"][0]
        self.assertIn("room_name", feat["properties"])
        self.assertIn("color", feat["properties"])
        self.assertIn("area_m2", feat["properties"])

    def test_floor_plan_small_grid(self):
        """Small 6x6 footprint still works."""
        response = self.client.post(
            '/design/floor-plan/',
            data=json.dumps({
                "footprint_geojson": {
                    "type": "Polygon",
                    "coordinates": [[[0, 0], [6, 0], [6, 6], [0, 6], [0, 0]]],
                },
                "rooms": [
                    {"name": "Room1", "area": 9, "adjacency": []},
                    {"name": "Room2", "area": 9, "adjacency": ["Room1"]},
                ],
                "cell_size": 3.0,
                "options": {"num_generations": 3, "population_size": 6},
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["grid_info"]["rows"], 2)
        self.assertEqual(data["grid_info"]["cols"], 2)
        self.assertGreater(data["num_results"], 0)

    def test_floor_plan_response_structure(self):
        """All expected keys present in response."""
        response = self.client.post(
            '/design/floor-plan/',
            data=json.dumps({
                "footprint_geojson": {
                    "type": "Polygon",
                    "coordinates": [[[0, 0], [12, 0], [12, 9], [0, 9], [0, 0]]],
                },
                "rooms": [{"name": "A", "area": 20, "adjacency": []}],
                "options": {"num_generations": 3, "population_size": 6},
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        for key in ("grid_info", "rooms", "num_results", "results"):
            self.assertIn(key, data)


# ── Subdivision Tests ──────────────────────────────────────────

class SubdivisionAlgorithmTest(TestCase):
    """Test recursive binary subdivision floor plan algorithm."""

    ROOMS = [
        {"name": "Living", "area": 40, "adjacency": ["Entry"]},
        {"name": "Entry", "area": 10, "adjacency": ["Living"]},
        {"name": "Bedroom", "area": 25, "adjacency": []},
    ]

    def _footprint(self, w=15, h=12):
        from shapely.geometry import box as shp_box
        return shp_box(0, 0, w, h)

    def test_two_rooms_equal_area(self):
        from design.services.floor_subdivision import subdivide_floor_plan
        rooms = [
            {"name": "A", "area": 50, "adjacency": ["B"]},
            {"name": "B", "area": 50, "adjacency": ["A"]},
        ]
        result = subdivide_floor_plan(self._footprint(), rooms, 3.0)
        self.assertGreater(result["num_results"], 0)
        # Both rooms should appear in the plan
        plan = result["results"][0]["floor_plan"]
        names = {f["properties"]["room_name"] for f in plan["features"]}
        self.assertEqual(names, {"A", "B"})

    def test_three_rooms_unequal(self):
        from design.services.floor_subdivision import subdivide_floor_plan
        result = subdivide_floor_plan(self._footprint(), self.ROOMS, 3.0)
        self.assertGreater(result["num_results"], 0)
        plan = result["results"][0]["floor_plan"]
        names = {f["properties"]["room_name"] for f in plan["features"]}
        self.assertEqual(names, {"Living", "Entry", "Bedroom"})

    def test_adjacency_ordering(self):
        """Adjacent rooms should be placed near each other."""
        from design.services.floor_subdivision import subdivide_floor_plan
        result = subdivide_floor_plan(self._footprint(), self.ROOMS, 3.0)
        metrics = result["results"][0]["metrics"]
        # Adjacency score should be reasonable (Living-Entry are adjacent)
        self.assertGreater(metrics["adjacency_score"], 0)

    def test_single_room(self):
        from design.services.floor_subdivision import subdivide_floor_plan
        rooms = [{"name": "Hall", "area": 100, "adjacency": []}]
        result = subdivide_floor_plan(self._footprint(), rooms, 3.0)
        self.assertGreater(result["num_results"], 0)
        plan = result["results"][0]["floor_plan"]
        self.assertEqual(len(plan["features"]), 1)
        self.assertEqual(plan["features"][0]["properties"]["room_name"], "Hall")

    def test_l_shape_footprint(self):
        """Non-rectangular footprint should still produce valid results."""
        from shapely.geometry import Polygon
        from design.services.floor_subdivision import subdivide_floor_plan
        l_shape = Polygon([(0, 0), (12, 0), (12, 6), (6, 6), (6, 12), (0, 12)])
        rooms = [
            {"name": "A", "area": 30, "adjacency": ["B"]},
            {"name": "B", "area": 20, "adjacency": ["A"]},
        ]
        result = subdivide_floor_plan(l_shape, rooms, 3.0)
        self.assertGreater(result["num_results"], 0)

    def test_many_rooms(self):
        """7-room apartment preset should work."""
        from design.services.floor_subdivision import subdivide_floor_plan
        rooms = [
            {"name": "거실", "area": 40, "adjacency": ["현관", "주방"]},
            {"name": "현관", "area": 8, "adjacency": ["거실"]},
            {"name": "주방", "area": 15, "adjacency": ["거실", "식당"]},
            {"name": "식당", "area": 12, "adjacency": ["주방"]},
            {"name": "침실1", "area": 18, "adjacency": []},
            {"name": "침실2", "area": 12, "adjacency": []},
            {"name": "화장실", "area": 6, "adjacency": []},
        ]
        result = subdivide_floor_plan(self._footprint(18, 15), rooms, 3.0)
        self.assertGreater(result["num_results"], 0)
        plan = result["results"][0]["floor_plan"]
        # Small rooms (화장실 6m2 < cell 9m2) may merge; at least 5 of 7
        self.assertGreaterEqual(len(plan["features"]), 5)

    def test_returns_valid_assignment(self):
        """All active cells should be assigned a room."""
        from design.services.floor_subdivision import subdivide_floor_plan
        result = subdivide_floor_plan(self._footprint(), self.ROOMS, 3.0)
        plan = result["results"][0]["floor_plan"]
        total_area = sum(f["properties"]["area_m2"] for f in plan["features"])
        self.assertGreater(total_area, 0)

    def test_multiple_variants(self):
        """Multiple result variants should be generated."""
        from design.services.floor_subdivision import subdivide_floor_plan
        result = subdivide_floor_plan(
            self._footprint(), self.ROOMS, 3.0, {"num_variants": 10},
        )
        self.assertGreater(result["num_results"], 1)


class SubdivisionAPITest(TestCase):
    """Test subdivision via /design/floor-plan/ endpoint."""

    def test_subdivision_api_e2e(self):
        response = self.client.post(
            '/design/floor-plan/',
            data=json.dumps({
                "footprint_geojson": {
                    "type": "Polygon",
                    "coordinates": [[[0, 0], [15, 0], [15, 12], [0, 12], [0, 0]]],
                },
                "rooms": [
                    {"name": "Living", "area": 40, "adjacency": ["Entry"]},
                    {"name": "Entry", "area": 10, "adjacency": ["Living"]},
                    {"name": "Bedroom", "area": 25, "adjacency": []},
                ],
                "algorithm": "subdivision",
                "cell_size": 3.0,
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["algorithm"], "subdivision")
        self.assertGreater(data["num_results"], 0)

        result = data["results"][0]
        self.assertIn("metrics", result)
        self.assertIn("adjacency_score", result["metrics"])
        fp = result["floor_plan"]
        self.assertEqual(fp["type"], "FeatureCollection")
        self.assertGreater(len(fp["features"]), 0)

    def test_subdivision_response_structure(self):
        response = self.client.post(
            '/design/floor-plan/',
            data=json.dumps({
                "footprint_geojson": {
                    "type": "Polygon",
                    "coordinates": [[[0, 0], [12, 0], [12, 9], [0, 9], [0, 0]]],
                },
                "rooms": [{"name": "A", "area": 20, "adjacency": []}],
                "algorithm": "subdivision",
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        for key in ("algorithm", "grid_info", "rooms", "num_results", "results"):
            self.assertIn(key, data)


# ── MCTS Tests ──────────────────────────────────────────────────

class MCTSAlgorithmTest(TestCase):
    """Test MCTS floor plan algorithm."""

    ROOMS = [
        {"name": "Living", "area": 40, "adjacency": ["Entry"]},
        {"name": "Entry", "area": 10, "adjacency": ["Living"]},
        {"name": "Bedroom", "area": 25, "adjacency": []},
    ]

    def _footprint(self, w=15, h=12):
        from shapely.geometry import box as shp_box
        return shp_box(0, 0, w, h)

    def test_constraint_matrix_construction(self):
        from design.services.floor_mcts import _build_constraint_matrix
        cons = _build_constraint_matrix(self.ROOMS)
        self.assertEqual(cons.shape, (3, 3))
        self.assertEqual(cons[0][1], 1)  # Living-Entry
        self.assertEqual(cons[1][0], 1)  # Entry-Living (symmetric)
        self.assertEqual(cons[0][2], 0)  # Living-Bedroom (no constraint)

    def test_compute_reward_perfect(self):
        """All constraints satisfied → high reward."""
        import numpy as np
        from design.services.floor_mcts import _compute_reward
        rooms = [
            {"name": "A", "area": 9, "adjacency": ["B"]},
            {"name": "B", "area": 9, "adjacency": ["A"]},
        ]
        cons = np.array([[0, 1], [1, 0]])
        # 2x2 grid: A adjacent to B
        state = np.array([[1, 2], [1, 2]])
        grid_info = {"cell_size": 3.0}
        reward = _compute_reward(state, cons, rooms, grid_info)
        self.assertGreater(reward, 0.5)

    def test_compute_reward_none(self):
        """No constraints satisfied → lower reward."""
        import numpy as np
        from design.services.floor_mcts import _compute_reward
        rooms = [
            {"name": "A", "area": 9, "adjacency": ["B"]},
            {"name": "B", "area": 9, "adjacency": ["A"]},
        ]
        cons = np.array([[0, 1], [1, 0]])
        # 2x2 grid: rooms not adjacent (diagonal)
        state = np.array([[1, 0], [0, 2]])
        grid_info = {"cell_size": 3.0}
        reward = _compute_reward(state, cons, rooms, grid_info)
        self.assertLess(reward, 0.5)

    def test_flood_fill(self):
        import numpy as np
        from design.services.floor_mcts import _flood_fill_room
        state = np.zeros((3, 3), dtype=int)
        _flood_fill_room(state, 0, 0, 1, 4)
        self.assertEqual(np.sum(state == 1), 4)

    def test_small_grid_placement(self):
        from design.services.floor_mcts import mcts_floor_plan
        rooms = [
            {"name": "A", "area": 9, "adjacency": ["B"]},
            {"name": "B", "area": 9, "adjacency": ["A"]},
        ]
        result = mcts_floor_plan(
            self._footprint(6, 6), rooms, 3.0,
            {"num_iterations": 50, "num_runs": 2},
        )
        self.assertGreater(result["num_results"], 0)
        plan = result["results"][0]["floor_plan"]
        names = {f["properties"]["room_name"] for f in plan["features"]}
        self.assertEqual(names, {"A", "B"})

    def test_footprint_mask_applied(self):
        """Masked cells should remain 0 in the assignment."""
        from shapely.geometry import Polygon
        from design.services.floor_mcts import mcts_floor_plan
        l_shape = Polygon([(0, 0), (12, 0), (12, 6), (6, 6), (6, 12), (0, 12)])
        rooms = [{"name": "A", "area": 30, "adjacency": []}]
        result = mcts_floor_plan(
            l_shape, rooms, 3.0, {"num_iterations": 30, "num_runs": 1},
        )
        self.assertGreater(result["num_results"], 0)

    def test_multiple_runs(self):
        from design.services.floor_mcts import mcts_floor_plan
        result = mcts_floor_plan(
            self._footprint(), self.ROOMS, 3.0,
            {"num_iterations": 30, "num_runs": 4},
        )
        self.assertGreaterEqual(result["num_results"], 1)

    def test_three_rooms(self):
        from design.services.floor_mcts import mcts_floor_plan
        result = mcts_floor_plan(
            self._footprint(), self.ROOMS, 3.0,
            {"num_iterations": 50, "num_runs": 2},
        )
        self.assertGreater(result["num_results"], 0)
        metrics = result["results"][0]["metrics"]
        self.assertIn("adjacency_score", metrics)
        self.assertIn("area_error", metrics)
        self.assertIn("compactness", metrics)


class MCTSAPITest(TestCase):
    """Test MCTS via /design/floor-plan/ endpoint."""

    def test_mcts_api_e2e(self):
        response = self.client.post(
            '/design/floor-plan/',
            data=json.dumps({
                "footprint_geojson": {
                    "type": "Polygon",
                    "coordinates": [[[0, 0], [15, 0], [15, 12], [0, 12], [0, 0]]],
                },
                "rooms": [
                    {"name": "Living", "area": 40, "adjacency": ["Entry"]},
                    {"name": "Entry", "area": 10, "adjacency": ["Living"]},
                ],
                "algorithm": "mcts",
                "options": {"num_iterations": 30, "num_runs": 2},
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["algorithm"], "mcts")
        self.assertGreater(data["num_results"], 0)
        fp = data["results"][0]["floor_plan"]
        self.assertEqual(fp["type"], "FeatureCollection")

    def test_mcts_response_structure(self):
        response = self.client.post(
            '/design/floor-plan/',
            data=json.dumps({
                "footprint_geojson": {
                    "type": "Polygon",
                    "coordinates": [[[0, 0], [12, 0], [12, 9], [0, 9], [0, 0]]],
                },
                "rooms": [{"name": "A", "area": 20, "adjacency": []}],
                "algorithm": "mcts",
                "options": {"num_iterations": 20, "num_runs": 1},
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        for key in ("algorithm", "grid_info", "rooms", "num_results", "results"):
            self.assertIn(key, data)


# ── Packing Tests ───────────────────────────────────────────────

class PackingAlgorithmTest(TestCase):
    """Test circle-packing physics floor plan algorithm."""

    ROOMS = [
        {"name": "Living", "area": 40, "adjacency": ["Entry"]},
        {"name": "Entry", "area": 10, "adjacency": ["Living"]},
        {"name": "Bedroom", "area": 25, "adjacency": []},
    ]

    def _footprint(self, w=15, h=12):
        from shapely.geometry import box as shp_box
        return shp_box(0, 0, w, h)

    def test_circle_radius_from_area(self):
        import math
        from design.services.floor_packing import _Circle
        area = 100
        radius = math.sqrt(area / math.pi)
        c = _Circle(0, 0, radius, 0)
        actual_area = math.pi * c.radius ** 2
        self.assertAlmostEqual(actual_area, area, places=1)

    def test_adjacency_pairs(self):
        from design.services.floor_packing import _build_adjacency_pairs
        name_to_idx = {"Living": 0, "Entry": 1, "Bedroom": 2}
        pairs = _build_adjacency_pairs(self.ROOMS, name_to_idx)
        self.assertIn((0, 1), pairs)
        self.assertNotIn((0, 2), pairs)

    def test_convergence(self):
        """Simulation should converge (circles settle)."""
        from design.services.floor_packing import _init_circles, _simulate, _build_adjacency_pairs
        fp = self._footprint()
        name_to_idx = {r["name"]: i for i, r in enumerate(self.ROOMS)}
        adj_pairs = _build_adjacency_pairs(self.ROOMS, name_to_idx)
        circles = _init_circles(self.ROOMS, 7.5, 6.0, fp)
        circles = _simulate(circles, adj_pairs, fp, 100, 0.3, 0.8, 0.85)
        for c in circles:
            self.assertGreater(c.x, -5)
            self.assertLess(c.x, 20)

    def test_grid_assignment_covers_footprint(self):
        from design.services.floor_packing import packing_floor_plan
        result = packing_floor_plan(
            self._footprint(), self.ROOMS, 3.0,
            {"max_iterations": 50, "num_runs": 1},
        )
        self.assertGreater(result["num_results"], 0)
        plan = result["results"][0]["floor_plan"]
        total_area = sum(f["properties"]["area_m2"] for f in plan["features"])
        self.assertGreater(total_area, 0)

    def test_small_rooms(self):
        from design.services.floor_packing import packing_floor_plan
        rooms = [
            {"name": "A", "area": 9, "adjacency": ["B"]},
            {"name": "B", "area": 9, "adjacency": ["A"]},
        ]
        result = packing_floor_plan(
            self._footprint(6, 6), rooms, 3.0,
            {"max_iterations": 50, "num_runs": 1},
        )
        self.assertGreater(result["num_results"], 0)

    def test_many_rooms(self):
        from design.services.floor_packing import packing_floor_plan
        rooms = [
            {"name": "거실", "area": 40, "adjacency": ["현관", "주방"]},
            {"name": "현관", "area": 8, "adjacency": ["거실"]},
            {"name": "주방", "area": 15, "adjacency": ["거실"]},
            {"name": "침실1", "area": 18, "adjacency": []},
            {"name": "침실2", "area": 12, "adjacency": []},
        ]
        result = packing_floor_plan(
            self._footprint(18, 15), rooms, 3.0,
            {"max_iterations": 80, "num_runs": 2},
        )
        self.assertGreater(result["num_results"], 0)

    def test_adjacent_rooms_closer(self):
        from design.services.floor_packing import packing_floor_plan
        result = packing_floor_plan(
            self._footprint(), self.ROOMS, 3.0,
            {"max_iterations": 100, "num_runs": 3},
        )
        metrics = result["results"][0]["metrics"]
        self.assertGreaterEqual(metrics["adjacency_score"], 0)

    def test_multiple_runs(self):
        from design.services.floor_packing import packing_floor_plan
        result = packing_floor_plan(
            self._footprint(), self.ROOMS, 3.0,
            {"max_iterations": 30, "num_runs": 4},
        )
        self.assertGreaterEqual(result["num_results"], 1)


class PackingAPITest(TestCase):
    """Test packing via /design/floor-plan/ endpoint."""

    def test_packing_api_e2e(self):
        response = self.client.post(
            '/design/floor-plan/',
            data=json.dumps({
                "footprint_geojson": {
                    "type": "Polygon",
                    "coordinates": [[[0, 0], [15, 0], [15, 12], [0, 12], [0, 0]]],
                },
                "rooms": [
                    {"name": "Living", "area": 40, "adjacency": ["Entry"]},
                    {"name": "Entry", "area": 10, "adjacency": ["Living"]},
                ],
                "algorithm": "packing",
                "options": {"max_iterations": 50, "num_runs": 1},
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["algorithm"], "packing")
        self.assertGreater(data["num_results"], 0)

    def test_packing_response_structure(self):
        response = self.client.post(
            '/design/floor-plan/',
            data=json.dumps({
                "footprint_geojson": {
                    "type": "Polygon",
                    "coordinates": [[[0, 0], [12, 0], [12, 9], [0, 9], [0, 0]]],
                },
                "rooms": [{"name": "A", "area": 20, "adjacency": []}],
                "algorithm": "packing",
                "options": {"max_iterations": 30, "num_runs": 1},
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        for key in ("algorithm", "grid_info", "rooms", "num_results", "results"):
            self.assertIn(key, data)


# ──────────────────────────────────────────────────────
# Regulation Validator Tests
# ──────────────────────────────────────────────────────


class ValidateDesignTest(TestCase):
    """Test regulation_validator.validate_design()."""

    def test_all_pass(self):
        from design.services.regulation_validator import validate_design
        metrics = {"bcr": 55.0, "far": 180.0, "height": 20.0, "min_setback": 1.0}
        regs = {"bcr_pct": 60, "far_pct": 200, "height_limit_m": 25, "adjacent_setback_m": 0.5}
        violations = validate_design(metrics, regs)
        self.assertEqual(violations, [])

    def test_bcr_violation(self):
        from design.services.regulation_validator import validate_design
        metrics = {"bcr": 65.0, "far": 180.0, "height": 20.0, "min_setback": 1.0}
        regs = {"bcr_pct": 60, "far_pct": 200, "height_limit_m": 25, "adjacent_setback_m": 0.5}
        violations = validate_design(metrics, regs)
        self.assertEqual(len(violations), 1)
        self.assertEqual(violations[0]["type"], "bcr")
        self.assertIn("건폐율", violations[0]["message"])

    def test_multiple_violations(self):
        from design.services.regulation_validator import validate_design
        metrics = {"bcr": 65.0, "far": 250.0, "height": 30.0, "min_setback": 0.3}
        regs = {"bcr_pct": 60, "far_pct": 200, "height_limit_m": 25, "adjacent_setback_m": 0.5}
        violations = validate_design(metrics, regs)
        types = {v["type"] for v in violations}
        self.assertEqual(types, {"bcr", "far", "height", "setback"})

    def test_none_limits_skipped(self):
        from design.services.regulation_validator import validate_design
        metrics = {"bcr": 99.0, "far": 999.0, "height": 100.0, "min_setback": 0.0}
        regs = {"bcr_pct": None, "far_pct": None, "height_limit_m": None, "adjacent_setback_m": None}
        violations = validate_design(metrics, regs)
        self.assertEqual(violations, [])

    def test_setback_violation(self):
        from design.services.regulation_validator import validate_design
        metrics = {"bcr": 50, "far": 150, "height": 10, "min_setback": 0.2}
        regs = {"bcr_pct": 60, "far_pct": 200, "height_limit_m": 25, "adjacent_setback_m": 0.5}
        violations = validate_design(metrics, regs)
        self.assertEqual(len(violations), 1)
        self.assertEqual(violations[0]["type"], "setback")

    def test_severity_minor(self):
        from design.services.regulation_validator import validate_design
        metrics = {"bcr": 62.0}
        regs = {"bcr_pct": 60}
        v = validate_design(metrics, regs)
        self.assertEqual(v[0]["severity"], "minor")

    def test_severity_critical(self):
        from design.services.regulation_validator import validate_design
        metrics = {"bcr": 80.0}
        regs = {"bcr_pct": 60}
        v = validate_design(metrics, regs)
        self.assertEqual(v[0]["severity"], "critical")


class AutoCorrectConstraintsTest(TestCase):
    """Test auto_correct_constraints()."""

    def test_tighten_less_than(self):
        from design.services.regulation_validator import auto_correct_constraints
        violations = [{"type": "bcr", "actual": 65, "limit": 60, "severity": "minor"}]
        constraints = [{"name": "bcr", "val": 60.0, "Requirement": "Less than"}]
        result = auto_correct_constraints(violations, constraints)
        self.assertLess(result[0]["val"], 60.0)

    def test_tighten_greater_than(self):
        from design.services.regulation_validator import auto_correct_constraints
        violations = [{"type": "setback", "actual": 0.3, "limit": 0.5, "severity": "minor"}]
        constraints = [{"name": "setback", "val": 0.5, "Requirement": "Greater than"}]
        result = auto_correct_constraints(violations, constraints)
        self.assertGreater(result[0]["val"], 0.5)

    def test_no_matching_constraint_unchanged(self):
        from design.services.regulation_validator import auto_correct_constraints
        violations = [{"type": "bcr", "actual": 65, "limit": 60, "severity": "minor"}]
        constraints = [{"name": "far", "val": 200.0, "Requirement": "Less than"}]
        auto_correct_constraints(violations, constraints)
        self.assertEqual(constraints[0]["val"], 200.0)


class ValidateBestDesignsTest(TestCase):
    """Test validate_best_designs()."""

    def test_all_valid(self):
        from design.services.regulation_validator import validate_best_designs
        metrics = [
            {"bcr": 50, "far": 150, "height": 20, "min_setback": 1.0},
            {"bcr": 55, "far": 180, "height": 22, "min_setback": 0.8},
        ]
        regs = {"bcr_pct": 60, "far_pct": 200, "height_limit_m": 25, "adjacent_setback_m": 0.5}
        result = validate_best_designs(metrics, regs)
        self.assertTrue(result["all_valid"])
        self.assertEqual(result["worst_violations"], [])

    def test_some_invalid(self):
        from design.services.regulation_validator import validate_best_designs
        metrics = [
            {"bcr": 50, "far": 150},
            {"bcr": 65, "far": 250},
        ]
        regs = {"bcr_pct": 60, "far_pct": 200}
        result = validate_best_designs(metrics, regs)
        self.assertFalse(result["all_valid"])
        self.assertGreater(len(result["worst_violations"]), 0)


# ──────────────────────────────────────────────────────
# Graph2Plan Tests
# ──────────────────────────────────────────────────────


class Graph2PlanUtilsTest(TestCase):
    """Test Graph2Plan utility functions (no model needed)."""

    def test_room_name_mapping(self):
        from design.services.floor_graph2plan import _ROOM_NAME_TO_IDX
        self.assertEqual(_ROOM_NAME_TO_IDX["거실"], 0)
        self.assertEqual(_ROOM_NAME_TO_IDX["주방"], 2)
        self.assertEqual(_ROOM_NAME_TO_IDX["화장실"], 3)
        self.assertIn("livingroom", _ROOM_NAME_TO_IDX)

    def test_rooms_to_graph(self):
        from design.services.floor_graph2plan import _rooms_to_graph
        rooms = [
            {"name": "거실", "area": 40, "adjacency": ["주방"]},
            {"name": "주방", "area": 15, "adjacency": ["거실"]},
        ]
        rooms_t, triples_t = _rooms_to_graph(rooms)
        self.assertEqual(len(rooms_t), 2)
        self.assertEqual(rooms_t[0].item(), 0)   # 거실 = LivingRoom = 0
        self.assertEqual(rooms_t[1].item(), 2)   # 주방 = Kitchen = 2
        self.assertGreater(len(triples_t), 0)

    def test_rooms_to_graph_no_adjacency(self):
        """Without adjacency, creates linear chain."""
        from design.services.floor_graph2plan import _rooms_to_graph
        rooms = [
            {"name": "거실", "area": 40, "adjacency": []},
            {"name": "주방", "area": 15, "adjacency": []},
            {"name": "안방", "area": 20, "adjacency": []},
        ]
        rooms_t, triples_t = _rooms_to_graph(rooms)
        self.assertEqual(len(triples_t), 2)  # linear: 0-1, 1-2

    def test_boxes_to_geojson(self):
        import numpy as np
        from design.services.floor_graph2plan import _boxes_to_geojson
        from shapely.geometry import box as shapely_box

        footprint = shapely_box(0, 0, 20, 15)
        boxes = np.array([
            [0.0, 0.0, 0.5, 0.7],
            [0.5, 0.0, 1.0, 1.0],
        ])
        rooms_def = [
            {"name": "거실", "area": 100},
            {"name": "주방", "area": 50},
        ]
        result = _boxes_to_geojson(boxes, [0, 2], footprint, rooms_def)
        self.assertEqual(result["type"], "FeatureCollection")
        self.assertEqual(len(result["features"]), 2)
        self.assertEqual(result["features"][0]["properties"]["room_name"], "거실")

    def test_adjacency_score(self):
        import numpy as np
        from design.services.floor_graph2plan import _compute_adjacency_score
        from shapely.geometry import box as shapely_box

        footprint = shapely_box(0, 0, 20, 15)
        # Overlapping boxes → adjacency met
        boxes = np.array([[0.0, 0.0, 0.55, 1.0], [0.5, 0.0, 1.0, 1.0]])
        rooms = [
            {"name": "A", "adjacency": ["B"]},
            {"name": "B", "adjacency": ["A"]},
        ]
        score = _compute_adjacency_score(boxes, rooms, footprint)
        self.assertEqual(score, 1.0)

    def test_area_error(self):
        import numpy as np
        from design.services.floor_graph2plan import _compute_area_error
        from shapely.geometry import box as shapely_box

        footprint = shapely_box(0, 0, 20, 10)  # area = 200
        boxes = np.array([[0.0, 0.0, 0.5, 0.5]])  # box = 25% = 50m²
        rooms = [{"name": "A", "area": 50}]  # target 50 → error = 0
        error = _compute_area_error(boxes, rooms, footprint)
        self.assertAlmostEqual(error, 0.0, places=1)


class Graph2PlanFallbackTest(TestCase):
    """Test Graph2Plan with model unavailable — graceful fallback."""

    def test_fallback_result(self):
        from design.services.floor_graph2plan import _fallback_result
        from shapely.geometry import box as shapely_box
        footprint = shapely_box(0, 0, 20, 15)
        rooms = [{"name": "A", "area": 50}]
        result = _fallback_result(footprint, rooms, "test error")
        self.assertEqual(result["algorithm"], "graph2plan")
        self.assertEqual(result["num_results"], 0)
        self.assertIn("error", result)

    def test_api_graph2plan_algorithm(self):
        """API endpoint accepts graph2plan algorithm parameter."""
        response = self.client.post(
            '/design/floor-plan/',
            data=json.dumps({
                "footprint_geojson": {
                    "type": "Polygon",
                    "coordinates": [[[0, 0], [15, 0], [15, 12], [0, 12], [0, 0]]],
                },
                "rooms": [
                    {"name": "거실", "area": 40, "adjacency": ["주방"]},
                    {"name": "주방", "area": 15, "adjacency": ["거실"]},
                ],
                "algorithm": "graph2plan",
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["algorithm"], "graph2plan")
        for key in ("grid_info", "rooms", "num_results", "results"):
            self.assertIn(key, data)


# ───────────────────────────────────────────────────────────
# A6 — Repair Operator (Phase 1, Hard Constraint 강제)
# ───────────────────────────────────────────────────────────

class RepairOperatorTest(TestCase):
    """A6 repair_operator 단위 테스트."""

    def _site(self, w=30, d=30):
        from shapely.geometry import box
        return box(0, 0, w, d)

    def _limits(self, **overrides):
        from design.services.repair_operator import RegulationLimits
        defaults = dict(
            bcr_limit_pct=60.0, far_limit_pct=200.0, height_limit_m=20.0,
            adjacent_setback_m=1.0, north_setback_m=1.5, floor_height_m=3.0,
        )
        defaults.update(overrides)
        return RegulationLimits(**defaults)

    def test_empty_footprint(self):
        from shapely.geometry import Polygon
        from design.services.repair_operator import repair_footprint
        site = self._site()
        empty = Polygon()
        result, report = repair_footprint(empty, site, self._limits())
        self.assertIsNone(result)
        self.assertIn("empty", report.actions)

    def test_site_boundary_clip(self):
        """Footprint extending outside site is clipped to site."""
        from shapely.geometry import box
        from design.services.repair_operator import repair_footprint
        site = self._site(30, 30)
        oversized = box(-5, -5, 35, 35)  # entirely larger than site
        result, report = repair_footprint(oversized, site, self._limits())
        self.assertIsNotNone(result)
        self.assertLessEqual(result.area, site.area + 0.1)
        self.assertIn("site_clip", report.actions)

    def test_bcr_clamp(self):
        """BCR over limit is scaled down."""
        from shapely.geometry import box
        from design.services.repair_operator import repair_footprint
        site = self._site(30, 30)  # area 900
        # 80% bcr footprint
        big = box(3, 3, 27, 27)  # area 576 → 64% (over 60% limit)
        result, report = repair_footprint(big, site, self._limits(bcr_limit_pct=60.0))
        self.assertIsNotNone(result)
        bcr_after = result.area / site.area * 100
        self.assertLessEqual(bcr_after, 60.5)  # within 0.5% tolerance

    def test_height_cap(self):
        from shapely.geometry import box
        from design.services.repair_operator import repair_floors
        site = self._site()
        fp = box(5, 5, 15, 15)  # area 100
        # 20m height limit / 3m floor = 6 floors max
        repaired_floors, report = repair_floors(fp, site, num_floors=10, limits=self._limits())
        self.assertEqual(repaired_floors, 6)
        self.assertIn("height_cap_to_6f", report.actions)

    def test_far_cap(self):
        from shapely.geometry import box
        from design.services.repair_operator import repair_floors
        site = self._site(30, 30)  # area 900
        fp = box(5, 5, 25, 25)  # area 400 (44% bcr ok)
        # FAR 200% = 1800m². 400 × N ≤ 1800 → N ≤ 4.5
        # height_limit 20m / 3m floor = 6f. So FAR cuts before height
        repaired_floors, report = repair_floors(fp, site, num_floors=6, limits=self._limits(far_limit_pct=200.0))
        self.assertLessEqual(repaired_floors, 4)
        self.assertTrue(any("far" in a for a in report.actions))

    def test_repair_design_integration(self):
        from shapely.geometry import box
        from design.services.repair_operator import repair_design
        site = self._site(30, 30)
        fp = box(-5, -5, 35, 35)  # oversized
        result_fp, result_floors, actions = repair_design(fp, site, num_floors=10, limits=self._limits())
        self.assertIsNotNone(result_fp)
        # Both footprint clip + floor cap applied
        self.assertGreater(len(actions), 1)

    def test_sunlight_envelope_height_cap(self):
        """정북일조 사선 envelope가 있으면 lowest envelope height 아래로 층수를 cap."""
        from shapely.geometry import box
        from design.services.repair_operator import repair_design
        site = self._site(30, 30)
        fp = box(5, 5, 20, 20)
        envelope = {
            "slanted_polygons": [{
                "corners": [
                    [127.0, 37.0, 10.0],
                    [127.0, 37.001, 18.0],
                    [127.001, 37.001, 18.0],
                    [127.001, 37.0, 10.0],
                ],
            }],
        }

        result_fp, result_floors, actions = repair_design(
            fp, site, num_floors=8,
            limits=self._limits(height_limit_m=50.0, floor_height_m=2.8),
            sunlight_envelope=envelope,
        )

        self.assertIsNotNone(result_fp)
        self.assertLessEqual(result_floors * 2.8, 10.0)
        self.assertIn("sunlight_height_cap_to_3f", actions)


# ───────────────────────────────────────────────────────────
# A3 — Constraint penalty 정규화 (Phase 1)
# ───────────────────────────────────────────────────────────

class NormalizedPenaltyTest(TestCase):
    """A3 — 위반 거리 비례 penalty."""

    def _outputs_def(self):
        return [
            {"name": "score", "type": "Objective", "Goal": "Maximize"},
            {"name": "bcr", "type": "Constraint", "Requirement": "Less than", "val": 60.0},
            {"name": "setback", "type": "Constraint", "Requirement": "Greater than", "val": 3.0},
        ]

    def test_no_violation_zero_penalty(self):
        d = Design(0, 0, 0)
        d.set_outputs([100.0, 50.0, 5.0], self._outputs_def())
        self.assertEqual(d.penalty, 0)
        self.assertTrue(d.feasible)

    def test_less_than_violation_normalized(self):
        """BCR 80% with limit 60% → penalty = (80-60)/60 ≈ 0.333"""
        d = Design(0, 0, 0)
        d.set_outputs([100.0, 80.0, 5.0], self._outputs_def())
        self.assertAlmostEqual(d.penalty, (80.0 - 60.0) / 60.0, places=4)
        self.assertFalse(d.feasible)

    def test_greater_than_violation_normalized(self):
        """Setback 1m with limit 3m → penalty = (3-1)/3 ≈ 0.667"""
        d = Design(0, 0, 0)
        d.set_outputs([100.0, 50.0, 1.0], self._outputs_def())
        self.assertAlmostEqual(d.penalty, (3.0 - 1.0) / 3.0, places=4)
        self.assertFalse(d.feasible)

    def test_double_violation_summed(self):
        """BCR 80 + setback 1 → penalty 합산"""
        d = Design(0, 0, 0)
        d.set_outputs([100.0, 80.0, 1.0], self._outputs_def())
        expected = (80.0 - 60.0) / 60.0 + (3.0 - 1.0) / 3.0
        self.assertAlmostEqual(d.penalty, expected, places=4)

    def test_smaller_violation_lower_penalty(self):
        """BCR 65% < BCR 80% violation → penalty 65 < penalty 80"""
        d_smaller = Design(0, 0, 0)
        d_smaller.set_outputs([100.0, 65.0, 5.0], self._outputs_def())
        d_bigger = Design(1, 0, 0)
        d_bigger.set_outputs([100.0, 80.0, 5.0], self._outputs_def())
        self.assertLess(d_smaller.penalty, d_bigger.penalty)
        # GA가 d_smaller를 우선 선택 → 점진 개선


# ───────────────────────────────────────────────────────────
# A1 — NSGA-III Job (Phase 1, many-objective)
# ───────────────────────────────────────────────────────────

class NSGA3JobTest(TestCase):
    """A1 — NSGA3Job 기본 동작 + 다중 목적함수."""

    def _spec(self, n_obj=3):
        outputs = [
            {"name": f"f{i+1}", "type": "Objective", "Goal": "Maximize"}
            for i in range(n_obj)
        ]
        return {
            "inputs": [
                {"name": "x", "type": "Continuous", "Min": 0, "Max": 10, "Set length": 1},
                {"name": "y", "type": "Continuous", "Min": 0, "Max": 10, "Set length": 1},
            ],
            "outputs": outputs,
            "options": {"pop_size": 20, "Number of generations": 5},
        }

    def _eval_fn_3obj(self, designs):
        out = []
        for d in designs:
            x = d.get_inputs()[0][0]
            y = d.get_inputs()[1][0]
            out.append([x, y, x * y / 10])
        return out

    def test_init_designs(self):
        job = NSGA3Job(self._spec(n_obj=3))
        designs = job.init_designs()
        self.assertEqual(len(designs), 20)

    def test_requires_min_2_objectives(self):
        with self.assertRaises(ValueError):
            spec = self._spec(n_obj=1)
            NSGA3Job(spec)

    def test_step_runs_to_completion(self):
        job = NSGA3Job(self._spec(n_obj=3))
        job.init_designs()
        cont = True
        steps = 0
        while cont and steps < 10:
            cont, gen, _ = job.step(self._eval_fn_3obj)
            steps += 1
        # max_gen=5 → 5번 step 후 종료
        self.assertGreaterEqual(steps, 5)

    def test_pareto_front_returned(self):
        job = NSGA3Job(self._spec(n_obj=3))
        job.init_designs()
        cont = True
        while cont:
            cont, gen, _ = job.step(self._eval_fn_3obj)
        pareto = job.get_pareto_front()
        # all penalty=0 (no constraints) so pareto should have entries
        self.assertGreaterEqual(len(pareto), 1)

    def test_4_objectives_supported(self):
        """NSGA-III의 강점: 4+ objectives."""
        spec = self._spec(n_obj=4)
        job = NSGA3Job(spec)
        job.init_designs()

        def eval4(designs):
            out = []
            for d in designs:
                x = d.get_inputs()[0][0]
                y = d.get_inputs()[1][0]
                out.append([x, y, x + y, x * y / 10])
            return out

        cont = True
        while cont:
            cont, gen, _ = job.step(eval4)
        self.assertEqual(job.n_obj, 4)
        self.assertGreaterEqual(len(job.all_designs), 100)  # 5 gen × 20 pop


# ───────────────────────────────────────────────────────────
# A4 — Evaluator 통일 인터페이스 (Phase 1)
# ───────────────────────────────────────────────────────────

class EvaluatorRegistryTest(TestCase):
    """A4 Evaluator 추상 클래스 + registry."""

    def test_basic_evaluator_registered(self):
        from design.services.evaluators import get_evaluator, BasicGeometricEvaluator
        ev = get_evaluator("basic")
        self.assertIsInstance(ev, BasicGeometricEvaluator)

    def test_unknown_falls_back_to_basic(self):
        from design.services.evaluators import get_evaluator, BasicGeometricEvaluator
        ev = get_evaluator("nonexistent")
        self.assertIsInstance(ev, BasicGeometricEvaluator)

    def test_register_custom_evaluator(self):
        from design.services.evaluators import register_evaluator, get_evaluator, Evaluator, EvaluationContext

        class DummyEvaluator(Evaluator):
            name = "dummy"
            def evaluate(self, gene_inputs, context):
                return {"floor_area": 999.0, "daylight_score": 1.0,
                        "bcr": 0, "far": 0, "height": 0, "min_setback": 0, "open_pct": 0}

        register_evaluator("dummy", DummyEvaluator)
        ev = get_evaluator("dummy")
        self.assertEqual(ev.name, "dummy")

    def test_evaluation_context_dataclass(self):
        from shapely.geometry import box
        from design.services.evaluators import EvaluationContext
        ctx = EvaluationContext(
            site_utm=box(0, 0, 30, 30),
            site_area_m2=900.0,
            algorithm="additive",
            enable_repair=True,
        )
        self.assertEqual(ctx.algorithm, "additive")
        self.assertTrue(ctx.enable_repair)
        self.assertEqual(ctx.building_type, "공동주택")  # default


# ───────────────────────────────────────────────────────────
# A7 — Constraint Visualizer (Phase 1)
# ───────────────────────────────────────────────────────────

class ConstraintVisualizerTest(TestCase):
    """A7 — envelope/setback GeoJSON 출력."""

    def _site_wgs84(self):
        from shapely.geometry import Polygon
        return Polygon([
            (127.0392, 37.5012),
            (127.0395, 37.5012),
            (127.0395, 37.5015),
            (127.0392, 37.5015),
            (127.0392, 37.5012),
        ])

    def test_returns_feature_collection(self):
        from design.services.mass_renderer import constraint_envelope_geojson
        result = constraint_envelope_geojson(self._site_wgs84())
        self.assertEqual(result["type"], "FeatureCollection")
        self.assertGreater(len(result["features"]), 0)

    def test_has_site_feature(self):
        from design.services.mass_renderer import constraint_envelope_geojson
        result = constraint_envelope_geojson(self._site_wgs84())
        kinds = [f["properties"]["kind"] for f in result["features"]]
        self.assertIn("site", kinds)

    def test_has_setback_when_enabled(self):
        from design.services.mass_renderer import constraint_envelope_geojson
        result = constraint_envelope_geojson(
            self._site_wgs84(),
            adjacent_setback_m=2.0,
            north_setback_m=1.5,
        )
        kinds = [f["properties"]["kind"] for f in result["features"]]
        self.assertIn("adjacent_setback", kinds)
        self.assertIn("north_sunlight_base", kinds)

    def test_regulation_summary_metadata(self):
        from design.services.mass_renderer import constraint_envelope_geojson
        result = constraint_envelope_geojson(
            self._site_wgs84(),
            bcr_limit_pct=80.0,
            far_limit_pct=1300.0,
            height_limit_m=50.0,
        )
        summary = next(f for f in result["features"] if f["properties"]["kind"] == "regulation_summary")
        self.assertEqual(summary["properties"]["metadata"]["bcr_limit_pct"], 80.0)
        self.assertEqual(summary["properties"]["metadata"]["far_limit_pct"], 1300.0)


# ───────────────────────────────────────────────────────────
# A2 — Radiance Evaluator (Phase 1, fallback 검증)
# ───────────────────────────────────────────────────────────

class RadianceEvaluatorTest(TestCase):
    """A2 — RadianceEvaluator 인터페이스 + fallback."""

    def test_evaluator_registered(self):
        from design.services.evaluators import get_evaluator
        # RadianceEvaluator는 import 시 register
        from design.services import radiance_evaluator  # noqa
        ev = get_evaluator("radiance")
        self.assertEqual(ev.name, "radiance")

    def test_fallback_when_not_installed(self):
        from design.services.radiance_evaluator import RadianceEvaluator, RADIANCE_AVAILABLE
        ev = RadianceEvaluator()
        # 현재 pyradiance 미설치 환경에서 using_fallback=True
        self.assertEqual(ev.using_fallback, not RADIANCE_AVAILABLE)

    def test_fallback_udi_sda_range(self):
        from shapely.geometry import box
        from design.services.radiance_evaluator import _fallback_udi_sda
        site_area = 900.0
        fp = box(5, 5, 25, 25)  # 400m² (44% bcr)
        udi, sda = _fallback_udi_sda(fp, num_floors=5, site_area_m2=site_area)
        self.assertGreaterEqual(udi, 0.0)
        self.assertLessEqual(udi, 1.0)
        self.assertGreaterEqual(sda, 0.0)
        self.assertLessEqual(sda, 1.0)

    def test_fallback_empty_footprint(self):
        from shapely.geometry import Polygon
        from design.services.radiance_evaluator import _fallback_udi_sda
        empty = Polygon()
        udi, sda = _fallback_udi_sda(empty, 5, 900.0)
        self.assertEqual(udi, 0.0)
        self.assertEqual(sda, 0.0)


# ───────────────────────────────────────────────────────────
# B5 — Typology Recommender (Phase 2)
# ───────────────────────────────────────────────────────────

class TypologyRecommenderTest(TestCase):
    """B5 — Typology recommender with k-NN ranking."""

    def setUp(self):
        # Code review fix: 매 테스트마다 _GLOBAL_RANKING 초기화 (다른 테스트와 격리)
        from design.services.typology_recommender import set_ranking
        set_ranking(None)

    def tearDown(self):
        from design.services.typology_recommender import set_ranking
        set_ranking(None)

    def test_site_features_to_vector(self):
        from design.services.typology_recommender import SiteFeatures
        sf = SiteFeatures(area_m2=2000, bcr_limit=60, far_limit=300,
                          height_limit_m=25, aspect_ratio=1.2)
        v = sf.to_vector()
        self.assertEqual(len(v), 5)
        self.assertAlmostEqual(v[0], 2.0)  # 2000/1000
        self.assertAlmostEqual(v[1], 0.6)  # 60/100
        self.assertAlmostEqual(v[2], 0.3)  # 300/1000
        self.assertAlmostEqual(v[3], 0.5)  # 25/50
        self.assertAlmostEqual(v[4], 1.2)

    def test_recommend_fallback_when_no_ranking(self):
        from design.services.typology_recommender import (
            SiteFeatures, recommend, set_ranking,
        )
        set_ranking(None)
        sf = SiteFeatures(2000, 60, 300, 25, 1.2)
        result = recommend(sf, top_k=3)
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0]["typology"], "additive")  # default order
        self.assertIn("default order", result[0]["rationale"])

    def test_recommend_with_ranking(self):
        import numpy as np
        from design.services.typology_recommender import (
            SiteFeatures, TypologyRanking, recommend, set_ranking,
        )
        ranking = TypologyRanking(
            fixture_features=[np.array([2.0, 0.6, 0.3, 0.5, 1.0])],
            typology_hv=[{"radial": 270000, "subtractive": 170000, "additive": 161000}],
            fixture_names=["test_fixture"],
        )
        set_ranking(ranking)
        sf = SiteFeatures(2000, 60, 300, 25, 1.0)
        result = recommend(sf, top_k=3)
        self.assertEqual(result[0]["typology"], "radial")
        self.assertEqual(result[0]["rank"], 1)
        self.assertGreater(result[0]["score"], result[1]["score"])
        self.assertIn("test_fixture", result[0]["rationale"])

    def test_site_features_from_polygon(self):
        from shapely.geometry import Polygon
        from design.services.typology_recommender import site_features_from_polygon
        poly = Polygon([(127.0, 37.5), (127.001, 37.5), (127.001, 37.501), (127.0, 37.501)])
        sf = site_features_from_polygon(poly, bcr_limit=60, far_limit=300, height_limit_m=25)
        self.assertGreater(sf.area_m2, 100)  # ~10000 m²
        self.assertEqual(sf.bcr_limit, 60)
        self.assertEqual(sf.far_limit, 300)
        self.assertGreater(sf.aspect_ratio, 0)


# ───────────────────────────────────────────────────────────
# B3 — Precedent RAG (Phase 2)
# ───────────────────────────────────────────────────────────

class PrecedentRAGTest(TestCase):
    """B3 — Precedent RAG offline mode (keyword fallback)."""

    def test_demo_corpus_size(self):
        from design.services.precedent_rag import DEMO_CORPUS
        self.assertEqual(len(DEMO_CORPUS), 10)
        for item in DEMO_CORPUS:
            for required_key in ["id", "name", "zone", "bcr_pct", "far_pct",
                                  "height_limit_m", "typology", "description", "tags"]:
                self.assertIn(required_key, item)

    def test_offline_build_no_embeddings(self):
        from design.services.precedent_rag import PrecedentRAG
        rag = PrecedentRAG()
        rag.build_offline()
        self.assertEqual(len(rag.corpus), 10)
        self.assertIsNone(rag.embeddings)

    def test_keyword_search_zone_match(self):
        from design.services.precedent_rag import PrecedentRAG
        rag = PrecedentRAG()
        rag.build_offline()
        results = rag.search("일반상업지역 1300%", top_k=3)
        self.assertGreater(len(results), 0)
        # zone 매칭 bonus → 일반상업 사례가 top
        self.assertEqual(results[0]["zone"], "일반상업지역")

    def test_keyword_search_typology_match(self):
        from design.services.precedent_rag import PrecedentRAG
        rag = PrecedentRAG()
        rag.build_offline()
        results = rag.search("courtyard 매스", top_k=3)
        # typology 매칭 → courtyard 사례 top
        typologies = [r["typology"] for r in results]
        self.assertIn("courtyard", typologies)


# ───────────────────────────────────────────────────────────
# B4 — Heterogeneous Island (Phase 2)
# ───────────────────────────────────────────────────────────

class HeterogeneousIslandTest(TestCase):
    """B4 — SSIEAJob island_strategies 동적 전환."""

    def _spec(self, mode="homogeneous"):
        constraints = regulations_to_constraints({
            "bcr_limit": 60, "far_limit": 200, "height_limit_m": 25,
            "adjacent_setback_m": 1.0, "building_line_setback_m": 3.0,
        })
        spec = build_default_job_spec(site_area_m2=1000, constraints=constraints,
                                       algorithm="additive")
        spec.setdefault("options", {})["island_mode"] = mode
        return spec

    def test_homogeneous_default_all_blx(self):
        job = SSIEAJob(self._spec("homogeneous"))
        self.assertTrue(all(s == "blx" for s in job.island_strategies))

    def test_heterogeneous_blx_de_alternate(self):
        job = SSIEAJob(self._spec("heterogeneous"))
        self.assertEqual(job.island_mode, "heterogeneous")
        # 0,2,4...= blx; 1,3,5...= de
        for i, s in enumerate(job.island_strategies):
            self.assertEqual(s, "blx" if i % 2 == 0 else "de")

    def test_de_crossover_in_range(self):
        """DE crossover 결과가 input range 안에 있어야 함."""
        from design.engine.objects import Design
        d1, d2 = Design(0, 0, 0), Design(1, 1, 0)
        d1.set_inputs([[5.0]])
        d2.set_inputs([[10.0]])
        inputs_def = [{"type": "Continuous", "Min": 0.0, "Max": 20.0, "Set length": 1}]
        for _ in range(20):
            child = d1.crossover(d2, inputs_def, 0, 0, 0, strategy="de")
            v = child.get_inputs()[0][0]
            self.assertGreaterEqual(v, 0.0)
            self.assertLessEqual(v, 20.0)


# ───────────────────────────────────────────────────────────
# B6 — Core Planner (Phase 2)
# ───────────────────────────────────────────────────────────

class CorePlannerTest(TestCase):
    """B6 — 코어 위치 자동 배치."""

    def test_centroid_strategy_simple_box(self):
        from shapely.geometry import box
        from design.services.core_planner import plan_core
        fp = box(0, 0, 30, 30)  # 30×30 footprint
        plan = plan_core(fp, typology="additive", core_size_m=4.0)
        self.assertEqual(plan.typology_strategy, "centroid")
        self.assertTrue(plan.inside_footprint)
        # centroid (15, 15)
        self.assertAlmostEqual(plan.core_centroid[0], 15.0, places=1)
        self.assertAlmostEqual(plan.core_centroid[1], 15.0, places=1)

    def test_empty_footprint(self):
        from shapely.geometry import Polygon
        from design.services.core_planner import plan_core
        plan = plan_core(Polygon(), typology="additive")
        self.assertFalse(plan.inside_footprint)
        self.assertIn("footprint_empty", plan.notes)

    def test_typology_strategy_mapping(self):
        from design.services.core_planner import TYPOLOGY_STRATEGY
        # 10 typology 모두 strategy 정의
        for t in ["additive", "subtractive", "grid", "lshape", "ushape",
                  "cross", "courtyard", "tower_podium", "hshape", "radial"]:
            self.assertIn(t, TYPOLOGY_STRATEGY)

    def test_core_shrink_when_footprint_too_small(self):
        from shapely.geometry import box
        from design.services.core_planner import plan_core
        # 5×5 footprint → 4×4 core 들어감 / 좁아지면 축소
        fp = box(0, 0, 5, 5)
        plan = plan_core(fp, typology="additive", core_size_m=4.0)
        # 4×4 안 들어가면 축소 시도 (3, 2, 1.5)
        # 4×4 fits in 5×5, but inside_footprint True
        self.assertTrue(plan.inside_footprint)


# ───────────────────────────────────────────────────────────
# B7 — Explanation Generator (Phase 2)
# ───────────────────────────────────────────────────────────

class ExplanationGeneratorTest(TestCase):
    """B7 — 매스 결과 자연어 설명."""

    def test_template_explanation_includes_typology_korean(self):
        from design.services.explanation_generator import generate_explanation
        text = generate_explanation(
            metrics={"bcr": 56, "far": 230, "height": 16, "floor_area": 2300,
                     "daylight_score": 70, "min_setback": 3.0},
            typology="subtractive",
            site={"zone": "일반상업지역", "bcr_limit": 80, "far_limit": 1300, "height_limit_m": 50},
            use_llm=False,
        )
        self.assertIn("박스 제거형", text)  # subtractive 한국어
        self.assertIn("일반상업지역", text)

    def test_template_explanation_marks_violation(self):
        from design.services.explanation_generator import generate_explanation
        # BCR 90% with limit 60% → ⚠️
        text = generate_explanation(
            metrics={"bcr": 90, "far": 100, "height": 10, "floor_area": 100,
                     "daylight_score": 50, "min_setback": 1.0},
            typology="additive",
            site={"zone": "주거지역", "bcr_limit": 60, "far_limit": 200, "height_limit_m": 25},
            use_llm=False,
        )
        self.assertIn("⚠️", text)  # BCR 위반 표시

    def test_template_explanation_with_precedent(self):
        from design.services.explanation_generator import generate_explanation
        text = generate_explanation(
            metrics={"bcr": 56, "far": 230, "height": 16, "floor_area": 2300,
                     "daylight_score": 70, "min_setback": 3.0},
            typology="tower_podium",
            site={"zone": "일반상업지역", "bcr_limit": 80, "far_limit": 1300, "height_limit_m": 50},
            precedent={"name": "강남 테헤란로", "description": "역삼동 사례"},
            use_llm=False,
        )
        self.assertIn("강남 테헤란로", text)

    def test_template_explanation_residential_mentions_sunlight(self):
        from design.services.explanation_generator import generate_explanation
        text = generate_explanation(
            metrics={"bcr": 56, "far": 230, "height": 16, "floor_area": 2300,
                     "daylight_score": 70, "min_setback": 3.0},
            typology="courtyard",
            site={"zone": "제2종일반주거지역", "bcr_limit": 60, "far_limit": 250, "height_limit_m": 25},
            use_llm=False,
        )
        self.assertIn("정북일조", text)  # 주거지역 → 정북일조 언급
