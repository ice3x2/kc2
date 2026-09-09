"""CON-ARCH-006: actual wall and seated-contact construction fixtures."""
import unittest
import ast
import subprocess
from pathlib import Path
import cadquery as cq
from shapely.geometry import box, Point
from tools import generate_kc2_enclosed_housings as e


class WallCADTests(unittest.TestCase):
    def test_ops_arch_006_reviewed_sources_keep_raw_git_bytes(self):
        paths=['tools/generate_kc2_enclosed_housings.py','tools/audit_kc2_enclosure.py',
               'tools/review_kc2_enclosure_independent.py',
               'tools/fusion/KC2EnclosedToF3D/KC2EnclosedToF3D.py',
               'docs/reports/enclosed-housing-20260909/regressions.json']
        result=subprocess.run(['git','check-attr','text','--',*paths],capture_output=True,text=True,check=True)
        self.assertEqual(len(result.stdout.splitlines()),len(paths))
        self.assertTrue(all(line.endswith(': text: unset') for line in result.stdout.splitlines()),result.stdout)

    def test_con_arch_007_reset_probe_and_power_outward_approach(self):
        p={'feature_geometries':{'controller_socket':box(20,2.38,50,20.62)},
           'reset_actuator_geometry':box(42.7,23.55,45.4,24.85),
           'mounting_service_geometries':{'power_switch_actuator_sweep':box(47.7,22.95,60.9,25.45)}}
        ports=e.service_access_plans('left',p,box(0,0,62,40))
        self.assertTrue(ports['reset'].covers(Point(44.05,24.2).buffer(1.5)))
        self.assertGreaterEqual(ports['reset'].boundary.distance(Point(44.05,24.2)),1.799)
        self.assertTrue(ports['power'].buffer(1e-9).covers(box(60.9,22.2,63,26.2)))

    def test_usb_corridor_preserves_existing_mh1_receiver(self):
        p={'feature_geometries':{'controller_socket':box(106.0475,2.38,136.489405,20.62)}}
        corridor=e.usb_access_plan('right',p,box(-1,-1,165,124))
        receiver=Point(101.,4.).buffer(2.3)
        self.assertGreaterEqual(corridor.distance(receiver),.099999)

    def test_usb_corridor_is_top_open_without_removing_lower_wall(self):
        plan={'feature_geometries':{'controller_socket':box(20,2.38,50,20.62)}}
        outer=box(0,0,62,40)
        corridor=e.usb_access_plan('left',plan,outer)
        self.assertTrue(corridor.covers(box(50,6.4,63,16.6)))
        ring=outer.difference(outer.buffer(-.8))
        bottom=e.prism(ring,-1,4.1)
        top=e.prism(ring,4.1,9.3).cut(e.prism(corridor,4.1,9.4))
        self.assertGreater(bottom.intersect(e.prism(corridor,3.9,4.1)).Volume(),0)
        self.assertLess(top.intersect(e.prism(corridor,4.1,9.4)).Volume(),1e-7)
        mirrored={'feature_geometries':{'controller_socket':box(12,2.38,42,20.62)}}
        right=e.usb_access_plan('right',mirrored,outer)
        self.assertTrue(right.covers(box(-1,6.4,12,16.6)))

    def test_native_export_targets_all_six_staged_models(self):
        path=Path('tools/fusion/KC2EnclosedToF3D/KC2EnclosedToF3D.py')
        tree=ast.parse(path.read_text(encoding='utf8'))
        fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='export_jobs')
        env={}
        exec(compile(ast.Module(body=[fn],type_ignores=[]),str(path),'exec'),env)
        jobs=env['export_jobs'](Path('stage'))
        self.assertEqual(len(jobs),6)
        self.assertEqual(sum('_magnetic' in p.name for p in jobs.values()),2)
        self.assertTrue(all(p.parent==Path('stage') for p in jobs.values()))

    def test_closed_side_and_wall_seat(self):
        outer=box(-1,-1,11,11);inner=box(0,0,10,10)
        wall=outer.difference(inner)
        lower=e.prism(wall,-2.2,4.1).fuse(e.prism(outer,-2.2,-1))
        upper=e.prism(wall,4.1,9.3)
        self.assertTrue(lower.isValid());self.assertTrue(upper.isValid())
        self.assertEqual(len(lower.Solids()),1)
        self.assertAlmostEqual(lower.intersect(upper).Volume(),0,places=6)
        self.assertAlmostEqual(lower.intersect(e.prism(wall,4,4.1)).Volume(),wall.area*.1,places=5)
        self.assertAlmostEqual(upper.intersect(e.prism(wall,4.1,4.2)).Volume(),wall.area*.1,places=5)
        self.assertFalse(lower.isInside(cq.Vector(5,5,1)))

    def test_preserve_floor_and_no_floating_wall(self):
        wall=box(-1,-1,11,11).difference(box(0,0,10,10))
        solid=e.prism(wall,-1,4.1).fuse(e.prism(box(-1,-1,11,11),-2.2,-1))
        self.assertEqual(len(solid.Solids()),1)
        self.assertTrue(solid.isInside(cq.Vector(5,5,-1.5)))


if __name__=='__main__':unittest.main(verbosity=2)
