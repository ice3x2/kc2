"""CON-ARCH-006: remove the old guide cavities as well as protrusions."""
import unittest
import cadquery as cq
from tools.kc2_smooth_central_seam import patches, smooth, audit, box_solid


class SmoothSeamTests(unittest.TestCase):
    def test_old_notch_fails_continuity_then_is_filled(self):
        wall = box_solid(-1.5, -.3, 91, 99, -2.2, 4.1)
        old = wall.cut(box_solid(-1.6, -.2, 92.15, 97.85, -2.3, 1.8))
        expected = patches('left')[0]
        self.assertGreater(expected.cut(old).Volume(), 1)
        result = smooth(old, [expected])
        self.assertLess(expected.cut(result).Volume(), 1e-7)
        self.assertFalse(audit(old, result, [expected])['errors'])

    def test_unfilled_notch_rejected(self):
        stock = box_solid(-1.5, -.3, 91, 99, 1.8, 4.1)
        self.assertIn('unfilled_patch', audit(stock, stock, [patches('left')[0]])['errors'])

    def test_outside_bulge_and_removal_rejected(self):
        stock = box_solid(-1.5, 2, 91, 99, -2.2, 4.1)
        wanted = [patches('left')[0]]
        bulge = stock.fuse(box_solid(-2, -1.4, 94, 96, -1, 1))
        self.assertIn('off_patch_addition', audit(stock, bulge, wanted)['errors'])
        removed = stock.cut(box_solid(1, 2.1, 93, 94, 0, 1))
        self.assertIn('removed_material', audit(stock, removed, wanted)['errors'])

    def test_wall_floor_datums_and_magnet_separation(self):
        for side, face in [('left', -1.5), ('right', 150.9)]:
            for p in patches(side):
                b = p.BoundingBox()
                self.assertGreaterEqual(b.zmin, -2.200001)
                self.assertLessEqual(b.zmax, 4.100001)
                self.assertLess(b.ymax - b.ymin, 6.21)
                for y in (103, 111):
                    self.assertTrue(b.ymax < y-1.2 or b.ymin > y+1.2)
                self.assertAlmostEqual(b.xmin if side == 'left' else b.xmax, face)
        with self.assertRaises(ValueError): patches('wrong')

    def test_stl_cross_section_detects_remaining_hole(self):
        import trimesh
        from shapely.geometry import box
        from tools.review_kc2_smooth_central_seam import mesh_section
        solid = trimesh.creation.box(extents=[1.2,6.2,6.3])
        solid.apply_translation([-.9,95,.95])
        wanted=box(92.15,-2.2,97.85,4.1)
        self.assertLess(wanted.difference(mesh_section(solid,-.9)).area,1e-7)
        cap=trimesh.creation.box(extents=[1.2,6.2,2.3])
        cap.apply_translation([-.9,95,2.95])
        self.assertGreater(wanted.difference(mesh_section(cap,-.9)).area,10)


if __name__ == '__main__': unittest.main()
