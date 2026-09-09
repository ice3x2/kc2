"""CON-ARCH-006: local concealment, never replace PCB-on-base assembly."""
import unittest
from shapely.geometry import box
from tools import kc2_local_covers as covers


class LocalCoverPlanTests(unittest.TestCase):
    def test_only_exterior_open_cutout_gets_a_cover(self):
        outline=box(0,0,20,20)
        cuts=box(7,-1,13,4).union(box(4,8,8,12))
        plan=covers.lower_cover_plan(outline,cuts)
        self.assertEqual(plan['opening_count'],1)
        self.assertLess(plan['wall'].intersection(cuts).area,1e-9)
        self.assertLess(plan['outer'].boundary.intersection(cuts).length,1e-9)
        self.assertGreater(plan['wall'].intersection(outline.difference(cuts)).area,0.1)
        self.assertGreater(plan['floor_patch'].intersection(outline).area,0.1)
        self.assertTrue(plan['floor_patch'].covers(plan['wall']))
        self.assertTrue(plan['outer'].covers(outline))
        self.assertEqual(plan['outer'].bounds[2:],(20.,20.))
        self.assertLess(plan['wall'].intersection(box(0,5,20,20)).area,1e-9)

    def test_closed_cavities_do_not_create_perimeter_walls(self):
        plan=covers.lower_cover_plan(box(0,0,20,20),box(5,5,10,10))
        self.assertEqual(plan['opening_count'],0)
        self.assertTrue(plan['wall'].is_empty)
        self.assertTrue(plan['floor_patch'].is_empty)

    def test_zero_or_unprintably_thin_wall_is_rejected(self):
        for thickness in [0,-1,.1,float('nan')]:
            with self.assertRaises(ValueError):
                covers.lower_cover_plan(box(0,0,20,20),box(7,-1,13,4),thickness)

    def test_part_assignment_preserves_split_and_rejects_crossing_cover(self):
        masks=[box(0,0,10,20),box(10.2,0,20,20)]
        patches=[box(3,-1,6,.3),box(13,-1,16,.3)]
        assigned=covers.assign_local_patches(patches,masks)
        self.assertAlmostEqual(assigned[0].area,patches[0].area)
        with self.assertRaises(ValueError):
            covers.assign_local_patches([box(9,-1,12,.3)],masks)

    def test_crossing_cover_keeps_the_existing_print_seam_open(self):
        patch=box(9,-1,12,.3)
        masks=[box(-2,-2,10,22),box(10.2,-2,22,22)]
        parts=covers.clip_patches_to_split(patch,masks)
        self.assertAlmostEqual(parts[0].distance(parts[1]),.2)
        self.assertLess(parts[0].intersection(parts[1]).area,1e-9)
        self.assertAlmostEqual(sum(p.area for p in parts),patch.area-.2*1.3)


class LocalCoverSolidTests(unittest.TestCase):
    def test_step_export_has_no_trailing_whitespace(self):
        import cadquery as cq
        import tempfile
        from pathlib import Path
        from tools.generate_kc2_local_covers import export_step
        with tempfile.TemporaryDirectory(prefix='kc2-local-step-test-') as directory:
            path=Path(directory)/'cube.step'
            export_step(cq.Solid.makeBox(1,1,1),path)
            self.assertTrue(all(line==line.rstrip() for line in path.read_text().splitlines()))

    def test_cover_is_additive_and_supported_to_floor_without_raising_pcb(self):
        import cadquery as cq
        from tools.generate_kc2_local_covers import attach_lower_cover
        floor=cq.Solid.makeBox(20,20,1.2,cq.Vector(0,0,-2.2))
        web=cq.Solid.makeBox(20,20,3.5,cq.Vector(0,0,-1))
        cutter=cq.Solid.makeBox(6,5,3.6,cq.Vector(7,-1,-1))
        before=floor.fuse(web.cut(cutter))
        plan=covers.lower_cover_plan(box(0,0,20,20),box(7,-1,13,4))
        after=attach_lower_cover(before,plan['wall'],plan['floor_patch'])
        self.assertTrue(after.isValid())
        self.assertEqual(len(after.Solids()),1)
        self.assertLess(before.cut(after).Volume(),1e-7)
        self.assertGreater(after.Volume(),before.Volume())
        self.assertAlmostEqual(after.BoundingBox().zmax,2.5)
        self.assertLess(after.intersect(cutter).Volume(),1e-7)


if __name__=='__main__':unittest.main()
