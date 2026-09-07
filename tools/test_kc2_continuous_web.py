"""CON-ARCH-006: bottom-up support continuity, not just connected solids."""
import unittest
from tools import generate_kc2_x3_v2_housings as g

class ContinuousWebTests(unittest.TestCase):
    def test_full_depth_pilot_uses_true_circular_bore(self):
        import cadquery as cq
        from tools.verify_kc2_x3_v2_housing import inspect_web_continuity
        shp=g.legacy_geometry.require_shapely()
        web=shp['box'](-10,-10,10,10)
        model=g._extrude_geometry(cq,web,3.5,-1).cut(
            cq.Workplane('XY',origin=(0,0,-.3)).circle(.55).extrude(2.8))
        pilot=shp['Point'](0,0).buffer(.55,quad_segs=64)
        self.assertLess(inspect_web_continuity(cq,model,web,pilot)['missing_volume_mm3'],1e-7)

    def test_clipped_outline_sub_kernel_edge_can_be_extruded(self):
        import cadquery as cq
        from shapely.geometry import Polygon
        polygon=Polygon([(0,0),(1e-10,0),(10,0),(10,10),(0,10)])
        solid=g._extrude_geometry(cq,polygon,3.5,-1)
        self.assertAlmostEqual(solid.val().Volume(),350,places=5)

    def test_full_depth_check_rejects_gap_above_old_probe(self):
        import cadquery as cq
        from tools.verify_kc2_x3_v2_housing import inspect_web_continuity
        shp=g.legacy_geometry.require_shapely()
        web=shp['box'](-10,-10,10,10)
        broken=g._extrude_geometry(cq,web,.8,-1).union(g._extrude_geometry(cq,web,2, .5))
        self.assertFalse(inspect_web_continuity(cq,broken,web)['continuous'])

    def test_printability_check_rejects_a_connected_but_suspended_web(self):
        import cadquery as cq
        from tools.verify_kc2_x3_v2_housing import inspect_web_continuity
        shp=g.legacy_geometry.require_shapely()
        web=shp['box'](-10,-10,10,10)
        old=g._extrude_geometry(cq,web,2.5,0).union(cq.Workplane('XY',origin=(0,0,-1)).circle(1).extrude(1))
        good=g._extrude_geometry(cq,web,3.5,-1)
        self.assertGreater(inspect_web_continuity(cq,old,web)['missing_volume_mm3'],1)
        self.assertLess(inspect_web_continuity(cq,good,web)['missing_volume_mm3'],.001)

    def test_support_web_reaches_floor_without_filling_component_cavity(self):
        import cadquery as cq
        shp=g.legacy_geometry.require_shapely()
        outline=shp['box'](-20,-20,20,20)
        hole=shp['Point'](0,0).buffer(4,quad_segs=24)
        web=outline.difference(hole)
        plan={'support_surface':web,'desk_contact_geometry':shp['Point'](15,15).buffer(1.2),
              'mounting_holes':[{'housing_center_mm':[15,15]}]}
        model=g.build_cad(cq,shp,plan)
        slab=g._extrude_geometry(cq,web,.5,-.9)
        missing=slab.cut(model).val().Volume()
        self.assertLess(abs(missing),.001,'Unsupported underside web: old1mmgap remains')
        cavity=g._extrude_geometry(cq,hole,3.4,-.95)
        self.assertLess(abs(model.intersect(cavity).val().Volume()),.001,'Filled component relief')
        # The blind pilot still ends at-.30; do not fill its screw clearance.
        pilot=cq.Workplane('XY',origin=(15,15,-.2)).circle(.5).extrude(2.6)
        self.assertLess(abs(model.intersect(pilot).val().Volume()),.001)

if __name__=='__main__':unittest.main()
