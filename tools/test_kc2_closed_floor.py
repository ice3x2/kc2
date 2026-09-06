"""CON-ARCH-006: continuous integrated floor and independent silicone-foot pads."""
import tempfile
import unittest
from pathlib import Path
from tools import generate_kc2_x3_v2_housings as g


class ClosedFloorTests(unittest.TestCase):
    def test_floor_datums_preserve_receiver_and_projection_reserve(self):
        f=g.closed_floor_parameters()
        self.assertEqual(f['top_z_mm'],-1.)
        self.assertEqual(f['bottom_z_mm'],-2.2)
        self.assertEqual(f['thickness_mm'],1.2)
        self.assertEqual(f['maximum_component_projection_mm'],2.9)
        self.assertAlmostEqual(g.PCB_BOTTOM_Z_MM-2.9-f['top_z_mm'],.6)
        self.assertEqual(g.MOUNTING_PILOT_BOTTOM_Z_MM,-.3)
        self.assertFalse(f['physical_qualification'])

    def test_actual_right_floor_masks_do_not_inherit_component_holes(self):
        from tools.generate_kc2_mx_upper_housings import snapshot_board_geometry
        shp=g.legacy_geometry.require_shapely()
        with tempfile.TemporaryDirectory(dir=g.ROOT/'.codex-tmp') as d:
            data,_=snapshot_board_geometry(Path(d),Path('C:/Program Files/KiCad/10.0/bin/python.exe'))
        plan=g.build_plan_geometry(shp,'right',data['boards']['right'])
        split=g.build_right_split_plan(shp,plan)
        masks=[split['floor_part_a_mask'],split['floor_part_b_mask']]
        self.assertAlmostEqual(masks[0].intersection(masks[1]).area,0)
        for mask in masks:
            self.assertEqual(mask.geom_type,'Polygon')
            self.assertEqual(len(mask.interiors),0)
            self.assertGreater(mask.intersection(plan['all_component_cutouts']).area,1)
            pads=g.silicone_foot_layout(shp,mask,[mask.centroid.x,mask.centroid.y])
            self.assertEqual(len(pads['centers_xy_mm']),4)
            self.assertTrue(pads['centroid_inside_support_polygon'])

    def test_actual_cad_floor_and_missing_material_mutation(self):
        import cadquery as cq
        shp=g.legacy_geometry.require_shapely()
        outline=shp['box'](-20,-20,20,20)
        web=cq.Workplane('XY').rect(40,40).circle(5).extrude(2.5)
        column=cq.Workplane('XY').workplane(offset=-1).center(10,10).circle(2).extrude(1)
        old=web.union(column)
        closed,record=g.attach_closed_floor(cq,shp,old,outline,'whole')
        self.assertEqual(len(closed.solids().vals()),1)
        self.assertAlmostEqual(closed.val().BoundingBox().zmin,-2.2)
        self.assertEqual(record['geometry_errors'],[])
        cut=cq.Workplane('XY').workplane(offset=-2.3).circle(1).extrude(1.4)
        bad=closed.cut(cut)
        self.assertTrue(g.inspect_closed_floor(cq,bad,outline)['geometry_errors'])
        shallow=cq.Workplane('XY').workplane(offset=-2.21).circle(1).extrude(.1)
        self.assertTrue(g.inspect_closed_floor(cq,closed.cut(shallow),outline)['geometry_errors'])
        with self.assertRaises(ValueError):
            g.silicone_foot_layout(shp,shp['box'](0,0,5,5),[2.5,2.5])


if __name__=='__main__': unittest.main()
