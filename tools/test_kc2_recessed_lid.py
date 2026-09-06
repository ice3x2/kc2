"""CON-ARCH-006: recessed heads stay below plate without widening PCB lands."""
import unittest
from tools import generate_kc2_mx_upper_housings as upper


class RecessedHeadTests(unittest.TestCase):
    def test_recess_has_supported_floor_and_head_reserve(self):
        s = upper.stack_parameters(plate_top_above_pcb_mm=5.2,
                                   clip_thickness_mm=1.5, aperture_mm=14)
        self.assertAlmostEqual(s['head_top_z_mm'], s['plate_top_z_mm']-.3)
        self.assertEqual(s['head_pocket_diameter_mm'], 3.4)
        self.assertEqual(s['upper_collar_diameter_mm'], 4.6)
        self.assertEqual(s['pcb_landing_diameter_mm'], 3.0)
        self.assertAlmostEqual(s['head_bearing_z_mm']-s['collar_bottom_z_mm'], 2.5)
        self.assertAlmostEqual(s['nominal_under_head_to_receiver_entry_mm'], 5.3)
        self.assertIsNone(s['qualified_long_screw_length_mm'])

    def test_invalid_recess_stack_is_rejected(self):
        with self.assertRaises(ValueError):
            upper.stack_parameters(plate_top_above_pcb_mm=2.0,
                                   clip_thickness_mm=1.5, aperture_mm=14)

    def test_actual_brep_sections_detect_lost_collar(self):
        import cadquery as cq
        shp=upper.lower.legacy_geometry.require_shapely()
        s=upper.stack_parameters(plate_top_above_pcb_mm=5.2,
                                 clip_thickness_mm=1.5,aperture_mm=14)
        pilot=shp['Point'](0,0).buffer(.8,quad_segs=24)
        part=shp['box'](-5,-5,5,5).difference(pilot)
        plan={'mounting_holes':[{'ref':'MH1','housing_center_mm':[0,0]}]}
        def annulus(outer,inner,z,height):
            return cq.Workplane('XY').workplane(offset=z).circle(outer).circle(inner).extrude(height)
        plate=cq.Workplane('XY').workplane(offset=7.8).rect(10,10).circle(1.7).extrude(1.5)
        good=plate.union(annulus(2.3,.8,5.3,2.5)).union(annulus(1.5,.8,4.1,1.2))
        rows=upper.inspect_recess_geometry(cq,shp,good,part,plan,{'pilots':pilot},s)
        self.assertEqual(len(rows),1)
        self.assertAlmostEqual(rows[0]['head_intersection_mm3'],0)
        bad=good.cut(annulus(2.3,1.7,8.,.5))
        with self.assertRaises(RuntimeError):
            upper.inspect_recess_geometry(cq,shp,bad,part,plan,{'pilots':pilot},s)


if __name__ == '__main__':
    unittest.main()
