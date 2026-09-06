"""OPS-ARCH-007 revised release identity and actual selected assembly."""
import unittest
import math
import json
from tools import prepare_kc2_first_order as release

class RevisionContract(unittest.TestCase):
    def test_declared_via_mask_exceptions_match_fresh_actual_mask_audit(self):
        report=json.loads((release.ROOT/'docs/reports/v1-recess-20260906-r3/mask-via-support-replay-audit.json').read_text())
        measured=set()
        for side,record in report['sides'].items():
            for layer,check in record['mask_checks'].items():
                for via in check['overlaps']:
                    for hit in via['hits']:
                        self.assertTrue(hit['same_net'])
                        measured.add((side,tuple(via['center']),layer+'.Mask',hit['reference']+'/'+hit['pad_numbers'][0],via['net']))
        declared={(p['side'],tuple(p['xy_mm']),layer,p['pad'],p['net'])
                  for p in release.FABRICATION_PROFILE['via_mask_overlap_exceptions'] for layer in p['layers']}
        self.assertEqual(declared,measured)

    def test_capsule_end_order_is_not_a_physical_orientation_change(self):
        expected=[release.source_solder_land(dict(size=(2.5,3.2),rotation=180,number='1',center=(0,0)),'SW1')]
        actual=[dict(reference='SW1',pad='1',size=(2.5,3.2),center=(0,0),capsule={'diameter':2.5,'ends':[(0,-.35),(0,.35)]})]
        self.assertEqual(release.solder_land_errors(expected,actual,'test'),[])

    def test_rotated_oval_macro_is_checked_as_actual_capsule_not_bbox(self):
        payload=b'''%FSLAX46Y46*%
%MOMM*%
%AMHorizOval*
0 Comment*
20,1,$1,$2,$3,$4,$5,0*
1,1,$1,$2,$3*
1,1,$1,$4,$5*%
%ADD10HorizOval,2.500000X-0.247487X0.247487X0.247487X-0.247487X0*%
D10*
%TO.P,SW1,2*%
X10000000Y-20000000D03*
M02*
'''
        actual=release.inspect_solder_land_flashes(payload)
        self.assertEqual(len(actual),1)
        expected=[dict(reference='SW1',pad='2',center=(10,20),size=(2.5,3.2),
                       capsule={'diameter':2.5,'ends':[(-.247487,-.247487),(.247487,.247487)]})]
        self.assertEqual(release.solder_land_errors(expected,actual,'test'),[])
        wrong=payload.replace(b'X0.247487X0.247487X-0.247487X0',b'X-0.247487X0.247487X0.247487X0')
        self.assertTrue(release.solder_land_errors(expected,release.inspect_solder_land_flashes(wrong),'test'))
        # Same aperture name/parameters with a missing end circle is not equivalent.
        broken=payload.replace(b'1,1,$1,$4,$5*%',b'0 Missing second circle*%')
        self.assertTrue(release.solder_land_errors(expected,release.inspect_solder_land_flashes(broken),'test'))

    def test_new_release_cannot_reuse_old_raw_directory(self):
        self.assertEqual(release.RAW,'hardware/kicad/fabrication_review/v1-recess-20260906-r3')

    def test_selected_part_and_recess_fastener_contract(self):
        for side in ('left','right'):
            board=release.parse_board(release.ROOT/f'hardware/kicad/kc2_{side}/kc2_{side}.kicad_pcb')
            bom=release.manual_bom(board,side)
            self.assertIn('TTC Bluish White',bom['mx_switches']['specification'])
            self.assertIn('3-pin',bom['mx_switches']['specification'])
            self.assertEqual(bom['mx_switches']['supplier_trace'],'https://ko.aliexpress.com/item/1005012442816250.html')
            self.assertIn('7.5 mm',bom['fasteners'])
            self.assertTrue(bom['alternative_assemblies_mutually_exclusive'])
            self.assertIn('choc_v1_bottom_socket_with_ring',bom['alternative_assemblies'])

if __name__=='__main__': unittest.main()
