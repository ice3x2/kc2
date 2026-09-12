"""CON-ARCH-006: full interior fill, explicit 3D voids, never wall-only."""
import unittest
from shapely.geometry import box,Point
from tools.kc2_solid_plate import Void,fill_layers,coverage_errors,build_solid


class SolidPlateContractTests(unittest.TestCase):
    def test_fills_entire_structural_interior_not_only_perimeter(self):
        outline=box(0,0,40,30)
        layers=fill_layers(outline,4.4,9.3,[])
        self.assertEqual(len(layers),1)
        self.assertAlmostEqual(layers[0].geometry.area,1200)
        self.assertTrue(layers[0].geometry.covers(box(10,10,20,20)))

    def test_screw_through_hole_stays_open_at_every_height(self):
        hole=Point(5,5).buffer(.8)
        layers=fill_layers(box(0,0,20,20),4.4,9.3,[Void('screw',hole,4.1,10)])
        self.assertTrue(all(r.geometry.intersection(hole).area<1e-10 for r in layers))

    def test_head_pocket_removed_only_above_bearing_without_filling_bore(self):
        hole=Point(5,5).buffer(.8);head=Point(5,5).buffer(1.7)
        layers=fill_layers(box(0,0,20,20),4.4,9.3,[Void('screw',hole,4.1,10),Void('head',head,7.8,10)])
        self.assertEqual([(r.z0,r.z1) for r in layers],[(4.4,7.8),(7.8,9.3)])
        self.assertAlmostEqual(layers[0].geometry.intersection(head).area,head.difference(hole).area)
        self.assertAlmostEqual(layers[1].geometry.intersection(head).area,0)

    def test_body_clip_and_service_voids_are_unioned_not_filled(self):
        body=box(2,2,10,10);clip=box(1,4,11,8);service=box(15,0,20,10)
        cuts=[Void('body',body,0,5),Void('clip_motion',clip,0,5),Void('service',service,0,5)]
        layer=fill_layers(box(0,0,20,20),0,5,cuts)[0]
        self.assertAlmostEqual(layer.geometry.area,box(0,0,20,20).difference(body.union(clip).union(service)).area)

    def test_part_mask_does_not_bridge_retained_split(self):
        outline=box(0,0,20,20)
        a=fill_layers(outline,0,3,[],box(0,0,9.9,20))[0]
        b=fill_layers(outline,0,3,[],box(10.1,0,20,20))[0]
        self.assertAlmostEqual(a.geometry.distance(b.geometry),.2)

    def test_audit_rejects_wall_only_and_screw_fill_mutations(self):
        outline=box(0,0,20,20);hole=Point(5,5).buffer(.8)
        required=outline.difference(hole)
        wall=outline.difference(outline.buffer(-1.2))
        self.assertIn('unfilled structural interior',coverage_errors(required,wall))
        self.assertIn('material in reserved or exterior space',coverage_errors(required,outline))
        self.assertEqual(coverage_errors(required,required),[])

    def test_invalid_or_nonfinite_height_rejected(self):
        for z0,z1 in [(0,0),(2,1),(0,float('nan')),(float('-inf'),1)]:
            with self.subTest(z0=z0,z1=z1),self.assertRaises(ValueError):
                fill_layers(box(0,0,1,1),z0,z1,[])

    def test_voids_outside_height_do_not_remove_material(self):
        outline=box(0,0,20,20)
        rows=fill_layers(outline,4,6,[Void('outside',outline,0,3)])
        self.assertAlmostEqual(sum(r.geometry.area*(r.z1-r.z0) for r in rows),800)

    def test_actual_brep_is_full_solid_with_open_counterbore(self):
        domain=box(0,0,20,20);bore=Point(5,5).buffer(.8);head=Point(5,5).buffer(1.7)
        rows=fill_layers(domain,0,4,[Void('bore',bore,-1,5),Void('head',head,2,5)])
        shape=build_solid(rows)
        self.assertTrue(shape.isValid())
        self.assertEqual(len(shape.Solids()),1)
        expected=sum(r.geometry.area*(r.z1-r.z0) for r in rows)
        self.assertAlmostEqual(shape.Volume(),expected,places=5)


if __name__=='__main__':unittest.main()
