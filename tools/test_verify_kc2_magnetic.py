"""CON-ARCH-006: reject stale or incomplete magnetic release evidence."""
import copy
import unittest
import subprocess
from tools import verify_kc2_magnetic as v


class EvidenceContract(unittest.TestCase):
    def test_baseline_regression_evidence_is_complete(self):
        records=[{'baseline_suite':n,'exit_code':0} for n in
                 ['tests.json','report-tests.json','audit-budget-test.json']]
        self.assertEqual(v.baseline_errors(records),[])
        self.assertTrue(v.baseline_errors(records[:2]))
        records[0]['exit_code']=1
        self.assertTrue(v.baseline_errors(records))

    def test_canonical_release_bytes_not_normalized_by_git(self):
        paths=['hardware/PCB/kc2_left/kc2_left.kicad_pcb',
               'hardware/GERBER/manifest.json', 'hardware/MODELS/kc2_left_lower_housing_magnetic.step',
               'docs/reports/magnetic-20260908/cad-delta.json',
               'tools/generate_kc2_magnetic_housings.py']
        output=subprocess.check_output(['git','check-attr','text','--',*paths],text=True)
        self.assertTrue(all(line.endswith(': unset') for line in output.splitlines()),output)

    def fixture(self):
        return {'diameter_mm':2.4, 'depth_mm':1.2, 'center_z_mm':.75,
                'minimum_back_wall_mm':.6, 'web_top_bottom_rim_mm':.55,
                'physical_qualified':False, 'digital_delta_status':'pass',
                'pairs':[{'y':103., 'gap':4.}, {'y':111., 'gap':4.}],
                'magnet_face_gap_mm':[4.4,4.4], 'fallback_reason':None,
                'sides':{s:{'pockets':[{'x':x,'y':y,'sign':sign} for y in [103.,111.]],
                            'delta':{'errors':[], 'added_mm3':0, 'off_pocket_removed_mm3':0,
                                     'obstructed_bore_mm3':0, 'actual_removed_mm3':10.857344,
                                     'solids':count}, 'protected_primary_supports':supports,
                            'protected_mounting_lands':mounts}
                         for s,x,sign,count,supports,mounts in [('left',.1,1,1,31,8),('right',149.3,-1,2,39,9)]},
                'meshes':{n:{'watertight':True,'winding_consistent':True,'shells':1}
                          for n in v.EXPECTED_MESH_NAMES}}

    def test_complete_fixture(self):
        self.assertEqual(v.contract_errors(self.fixture()), [])

    def test_reject_contract_mutations(self):
        for field, value in [('diameter_mm',2.),('depth_mm',1.),('center_z_mm',1.5),
                             ('minimum_back_wall_mm',0),('web_top_bottom_rim_mm',0),
                             ('physical_qualified',True),('digital_delta_status','failed'),
                             ('pairs',[]),('magnet_face_gap_mm',[0,0]),('meshes',{})]:
            r=self.fixture();r[field]=value
            with self.subTest(field=field):self.assertTrue(v.contract_errors(r))

    def test_reject_added_plastic_missing_support_wrong_axis(self):
        for path,value in [(('delta','added_mm3'),1), (('delta','off_pocket_removed_mm3'),1),
                           (('delta','obstructed_bore_mm3'),1),(('delta','actual_removed_mm3'),0),
                           (('delta','solids'),2),(('delta','errors'),['failure'])]:
            r=self.fixture();r['sides']['left'][path[0]][path[1]]=value
            self.assertTrue(v.contract_errors(r))
        for field,value in [('protected_primary_supports',30),('protected_mounting_lands',7)]:
            r=self.fixture();r['sides']['left'][field]=value
            self.assertTrue(v.contract_errors(r))
        r=self.fixture();r['sides']['left']['pockets'][0]['sign']=-1
        self.assertTrue(v.contract_errors(r))


if __name__=='__main__':unittest.main(verbosity=2)
