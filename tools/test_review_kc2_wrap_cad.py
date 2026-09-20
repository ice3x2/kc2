"""CON-ARCH-006 full-volume checks must catch defects between mesh slices."""
import unittest
import cadquery as cq
from tools.review_kc2_wrap_cad import missing_volume, collision_volume, world_solids, magnet_voids, reusable_checkpoint


class FullVolumeTests(unittest.TestCase):
    def test_checkpoint_rejected_when_any_actual_input_changes(self):
        bindings = {'model.step':'a', 'generation.json':'b', 'auditor.py':'c'}
        row = dict(status='pass', source_sha256=bindings, row={'parts':[{}]})
        self.assertTrue(reusable_checkpoint(row, bindings, 1))
        self.assertFalse(reusable_checkpoint(row, {**bindings, 'model.step':'changed'}, 1))
        self.assertFalse(reusable_checkpoint(row, bindings, 2))
        self.assertFalse(reusable_checkpoint({**row, 'status':'failed'}, bindings, 1))

    def test_magnet_access_and_blind_pockets_are_both_checked(self):
        tools = magnet_voids('left')
        self.assertEqual(len(tools), 4)
        obstruction = cq.Workplane('XY').box(.1, .1, .1).val().translate((.5, 103, .75))
        self.assertGreater(collision_volume([obstruction], tools), .0009)
        obstruction = obstruction.translate((-1.5, 0, 0))
        self.assertGreater(collision_volume([obstruction], tools), .0009)

    def test_joined_frames_match_fixed_board_placement(self):
        shape = cq.Workplane('XY').box(2, 2, 2).val()
        left = world_solids([shape], 'left')[0]
        right = world_solids([shape.translate((153.2, 0, 0))], 'right')[0]
        self.assertAlmostEqual(left.Center().x, 170.1125)
        self.assertAlmostEqual(collision_volume([left], [right]), 8)

    def test_thin_missing_band_not_hidden_by_sampled_sections(self):
        expected = cq.Workplane('XY').box(2, 2, 5).val()
        missing = cq.Workplane('XY').box(2, 2, .01).val()
        actual = expected.cut(missing)
        self.assertAlmostEqual(missing_volume(actual, [expected]), .04, places=6)

    def test_touching_allowed_but_volume_collision_detected(self):
        a = cq.Workplane('XY').box(2, 2, 2).val()
        b = a.translate((2, 0, 0))
        self.assertAlmostEqual(collision_volume([a], [b]), 0)
        self.assertAlmostEqual(collision_volume([a], [b.translate((-.1, 0, 0))]), .4)


if __name__ == '__main__':
    unittest.main()
