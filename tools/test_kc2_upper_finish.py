"""CON-ARCH-006 regression tests for upper inner voids and a flat print face."""
import json
import unittest
from pathlib import Path

import trimesh
from shapely import wkt
from shapely.geometry import Point

from tools.kc2_pcb_seating import horizontal_section
from tools.kc2_upper_finish import (ROOT, enclosed_nonfunctional_voids,
                                    clip_to_print_datum)


class UpperFinishTests(unittest.TestCase):
    BASELINE=ROOT/'hardware/MODELS/STL_FROM_FUSION_20260921'
    def profile(self, side, kind):
        return json.loads((ROOT/'docs/reports/solid-filled-plates-20260913'/f'{side}-{kind}.json').read_text())

    def gap_part(self, side, kind, index=0):
        plan=json.loads((ROOT/'docs/reports/wall-gap-fix-20260921/evidence/plan.json').read_text())
        return plan['jobs'][f'{side}:{kind}']['parts'][index]

    def test_actual_left_inner_void_reproduced_for_all_three_families(self):
        for kind in ('mx','choc_v1','deep_sea'):
            with self.subTest(kind=kind):
                mesh=trimesh.load_mesh(self.BASELINE/f'kc2_left_{kind}_upper_housing.stl')
                section=horizontal_section(mesh,4.8)
                protected=wkt.loads(self.gap_part('left',kind)['protected_wkt'])
                voids=enclosed_nonfunctional_voids(section,protected)
                self.assertGreater(voids.area,1.0)
                self.assertLess(voids.area,2.0)

    def test_clip_removes_protrusion_without_changing_material_above_datum(self):
        import cadquery as cq
        main=cq.Workplane('XY').box(20,12,2.2,centered=(True,True,False)).translate((0,0,4.4)).val()
        protrusion=(cq.Workplane('XY').workplane(offset=4.1).circle(2.3).circle(.8)
                    .extrude(.3).val())
        body=main.fuse(protrusion)
        clipped,proof=clip_to_print_datum(body,4.4)
        self.assertAlmostEqual(clipped.BoundingBox().zmin,4.4,places=6)
        self.assertLessEqual(body.cut(clipped).cut(protrusion).Volume(),1e-7)
        self.assertLessEqual(clipped.cut(body).Volume(),1e-7)
        self.assertGreater(proof['removed_below_datum_mm3'],0)
        self.assertLessEqual(proof['removed_at_or_above_datum_mm3'],1e-7)

    def test_current_actual_upper_has_localized_material_below_common_datum(self):
        for side in ('left','right'):
            for kind in ('mx','choc_v1','deep_sea'):
                names=([f'kc2_left_{kind}_upper_housing.stl'] if side=='left' else
                    [f'kc2_right_{kind}_upper_housing_part_a.stl',f'kc2_right_{kind}_upper_housing_part_b.stl'])
                meshes=[trimesh.load_mesh(self.BASELINE/n) for n in names]
                self.assertTrue(any(m.bounds[0,2]<4.11 for m in meshes))
                self.assertTrue(all(m.bounds[0,2]>=4.099 for m in meshes))
                self.assertGreater(sum(horizontal_section(m,4.15).area for m in meshes),0)
                self.assertEqual(sum(horizontal_section(m,4.35).area>0 for m in meshes),len(meshes))

    def test_right_mount_has_exactly_one_owner(self):
        profile=self.profile('right','mx')
        names=['kc2_right_mx_upper_housing_part_a.stl','kc2_right_mx_upper_housing_part_b.stl']
        sections=[horizontal_section(trimesh.load_mesh(self.BASELINE/n),4.15) for n in names]
        for center in profile['mounting_centers']:
            owners=[i for i,s in enumerate(sections) if s.intersection(Point(*center).buffer(1.51)).area>4.9]
            self.assertEqual(len(owners),1)


if __name__=='__main__':unittest.main()
