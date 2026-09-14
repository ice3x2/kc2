"""CON-ARCH-006 no interpenetration at the unchanged PCB/plate stack."""
import unittest
import json
from unittest.mock import patch
from shapely.geometry import box
from tools.review_kc2_registered_assembly import overlap_errors
from tools import review_kc2_registered_assembly as assembly

class StackTests(unittest.TestCase):
    def test_explicit_void_path_and_semantics_not_pass_flag(self):
        self.assertTrue(assembly.void_path('right').endswith('right-receiver-strata-transfer.json'))
        self.assertTrue(assembly.void_path('left').endswith('left-void-review.json'))
        with self.assertRaises(ValueError):assembly.qualify_void('right',lambda p:json.dumps({'status':'pass','errors':[]}).encode())
        files={assembly.void_path('right'):json.dumps({'status':'pass','errors':[],'source_sha256':{'actual.step':'0'*64}}).encode(),'actual.step':b'new'}
        with patch('tools.publish_kc2_registered_housings.check_void_proof',return_value=None):
            with self.assertRaises(ValueError):assembly.qualify_void('right',files.__getitem__)
    def test_overlap_detected(self):
        self.assertTrue(overlap_errors(box(0,0,2,2),box(1,1,3,3)))
    def test_touching_support_is_not_penetration(self):
        self.assertEqual(overlap_errors(box(0,0,1,1),box(1,0,2,1)),[])
    def test_clear_rebate(self):
        wall=box(0,0,1.2,6)
        upper=box(-2,-2,4,8).difference(wall.buffer(.25,join_style=2))
        self.assertEqual(overlap_errors(wall,upper),[])

if __name__=='__main__':unittest.main()
