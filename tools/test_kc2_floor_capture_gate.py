"""CON-ARCH-006 floor-only capture release/native dispatch."""
import copy
import unittest
import json
from tools import publish_kc2_registered_housings as gate
from tools import kc2_lower_native_transfer as native


def fixture():
    captures=[]
    for y in (73.25,86.25):
        captures.append(dict(y_mm=y,ring_width_mm=1.2,ring_area_mm2=19.649146609453318,
            ring_missing_mm3=0.,root_missing_mm3=0.,head_missing_mm3=0.,
            throats=[dict(x_mm=81.84375+x,width_mm=2.80008,shoulder_mm=(4.5-2.80008)/2) for x in (.35,.5)],
            motions=[dict(dx_mm=x,dy_mm=z,collision_mm3=.1,method='actual cropped floor BRep translation/intersection') for x,z in ((1,0),(-1,0),(0,1),(0,-1))],
            motion_roi_xy_mm=[78.84375,y-6,90.84375,y+6],motion_z_mm=[-2.2,-1]))
    return dict(schema='right-floor-receiver-v1',status='pass',errors=[],side='right',magnetic=False,native_readback=False,
        physical_qualified=False,body_count=2,gap_mm=.4000314,overlap_mm3=0.,floor_z_mm=[-2.2,-1],captures=captures,
        floor=[dict(part=i,connected=True,constant_prism_missing_mm3=0.,constant_prism_extra_mm3=0.,errors=[]) for i in range(2)])


class GateTests(unittest.TestCase):
    def test_source_semantics_require_current_actual_and_executed_checker(self):
        r=fixture();folder=gate.STAGE+'/lower/right-normal';name='kc2_right_lower_housing'
        files={folder+'/'+name+'.step':b'step',folder+'/generation.json':b'{}'}
        for n in ('review_kc2_floor_receiver','test_review_kc2_floor_receiver','kc2_floor_capture',
                  'test_kc2_floor_capture','review_kc2_local_covers','review_kc2_filled_plates'):
            files['tools/'+n+'.py']=n.encode()
        r['source_sha256']={n:gate.sha_bytes(b) for n,b in files.items()}
        gate.check_transfer_source(r,native.recipe('floor-capture','right','normal'),files.__getitem__)
        for path in files:
            bad=copy.deepcopy(r);del bad['source_sha256'][path]
            with self.assertRaises(ValueError):gate.check_transfer_source(bad,native.recipe('floor-capture','right','normal'),files.__getitem__)

    def test_complete_actual_capture(self):
        gate.check_floor_capture(fixture(),False,False)

    def test_missing_stock_motions_throats_or_identity(self):
        changes=[lambda r:r['captures'].pop(),lambda r:r['captures'][0]['motions'].pop(),
            lambda r:r['captures'][0]['throats'].pop(),lambda r:r['captures'][0].update(ring_width_mm=.6),
            lambda r:r['captures'][0].update(ring_missing_mm3=.0001),lambda r:r['captures'][0].update(root_missing_mm3=.0001),
            lambda r:r['captures'][0]['motions'][0].update(collision_mm3=0.),lambda r:r.update(native_readback=True),
            lambda r:r.update(magnetic=True),lambda r:r['floor'][0].update(part=True)]
        for change in changes:
            r=fixture();change(r)
            with self.assertRaises(ValueError):gate.check_floor_capture(r,False,False)

    def test_only_lower_right_paths_changed_and_native_recipe(self):
        paths=gate.report_paths()
        self.assertIn('lower:right:normal:floor-capture-review',paths)
        self.assertNotIn('lower:right:normal:split-review',paths)
        self.assertIn('upper:right:mx:split-review',paths)
        spec=native.recipe('floor-capture','right','normal')
        self.assertTrue(spec['source'].endswith('/floor-capture-review.json'))
        self.assertTrue(spec['output'].endswith('/floor-capture-native-review.json'))
        with self.assertRaises(ValueError):native.recipe('floor-capture','left','normal')


if __name__=='__main__':unittest.main()
