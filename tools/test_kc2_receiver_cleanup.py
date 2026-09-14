"""CON-ARCH-006 bounded receiver cleanup, floor engagement retained."""
import unittest
from shapely.geometry import box
from tools.kc2_receiver_cleanup import plan_cutters, clean_receiver


class CleanupTests(unittest.TestCase):
    def test_production_requires_both_actual_prisms_and_all_roles(self):
        from tools.kc2_receiver_cleanup import validate_evidence, REQUIRED_ROLES
        good = {'rows': [{'y_mm': y, 'floor': {'eligible': True, 'errors': [], 'required_ring_missing_mm3': 0,
                          'levels_mm': [-2.2, -1], 'stratified_section_volume_error_mm3': 0},
                          'above_floor': {'constant_prism_eligible': True, 'errors': [], 'levels_mm': [-1, 2.5],
                          'volume_vs_z0_extrusion_error_mm3': 0, 'z0_candidate_source_difference_mm2': 0,
                          'cut_outside_roi_mm2': 0}}
                         for y in (73.25, 86.25)]}
        validate_evidence(good, {name: box(0, 0, 1, 1) for name in REQUIRED_ROLES})
        with self.assertRaises(ValueError):
            validate_evidence(good, {})
        good['rows'][1]['above_floor']['constant_prism_eligible'] = False
        with self.assertRaises(ValueError):
            validate_evidence(good, {name: box(0, 0, 1, 1) for name in REQUIRED_ROLES})

    def test_expansion_is_fixed_and_not_clamped(self):
        cut = box(0, 0, 1, 1)
        result = plan_cutters([cut], {'post': box(2, 0, 3, 1)})
        self.assertTrue(result.contains(cut))
        self.assertAlmostEqual(result.bounds[0], -.002)
        with self.assertRaisesRegex(ValueError, 'post'):
            plan_cutters([cut], {'post': box(1.001, 0, 2, 1)})

    def test_missing_or_empty_candidate_rejected(self):
        for cuts in ([], [box(0, 0, 0, 0)]):
            with self.assertRaises(ValueError):
                plan_cutters(cuts, {})

    def test_floor_untouched_and_only_abovefloor_cuts(self):
        from tools.kc2_central_flexure import prism
        body = prism(box(0, 0, 5, 5), -2.2, 2.5)
        footprint = plan_cutters([box(0, 0, 1, 1)], {})
        result = clean_receiver(body, footprint)
        floor = prism(box(0, 0, 5, 5), -2.2, -1)
        self.assertLess(floor.cut(result).Volume(), 1e-8)
        self.assertLess(result.cut(body).Volume(), 1e-8)
        self.assertLess(result.intersect(prism(footprint, -1, 2.5)).Volume(), 1e-8)
        self.assertEqual(len(result.Solids()), 1)

    def test_snapshot_remaps_only_exact_verified_bytes(self):
        import tempfile
        from pathlib import Path
        from tools.stage_kc2_receiver_cleanup import snapshot_sources, digest
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'live').mkdir()
            (root / 'live/a').write_text('old')
            (root / 'fixed').write_text('fixed')
            old = {'live/a': digest(root / 'live/a'), 'fixed': digest(root / 'fixed')}
            mapped = snapshot_sources(root, old, {'live': 'snapshot'})
            (root / 'live/a').write_text('new')
            self.assertEqual(mapped, {'snapshot/a': old['live/a'], 'fixed': old['fixed']})
            self.assertEqual((root / 'snapshot/a').read_text(), 'old')
            with self.assertRaises(ValueError):
                snapshot_sources(root, old, {'live': 'snapshot'})

    def test_conflicting_historical_bindings_rejected(self):
        from tools.stage_kc2_receiver_cleanup import merge_sources
        sources = {'same': 'old'}
        with self.assertRaises(ValueError):
            merge_sources(sources, {'same': 'new'})
        self.assertEqual(sources, {'same': 'old'})


if __name__ == '__main__':
    unittest.main()
