"""CON-ARCH-006 native acceptance must require actual geometry evidence."""
import unittest
from tools.review_kc2_registered_native import acceptance_errors,check_source_binding

class NativeEvidenceTests(unittest.TestCase):
    def test_mass_only_is_not_independent_geometry(self):
        self.assertTrue(acceptance_errors({'status':'pass','errors':[]}, []))
    def test_failed_part_and_incomplete_source_rejected(self):
        self.assertTrue(acceptance_errors({'status':'failed','errors':[]}, [{'status':'pass','errors':[]}]))
        self.assertTrue(acceptance_errors({'status':'pass','errors':[]}, [{'status':'failed','errors':['hole filled']}]))
    def test_actual_audits_can_pass(self):
        self.assertEqual(acceptance_errors({'status':'pass','errors':[]}, [{'status':'pass','errors':[]}]),[])
    def test_original_audit_must_bind_selected_step_and_generation(self):
        for bindings in ({},{'step':'a'},{'step':'a','generation':'wrong'}):
            with self.assertRaises(ValueError):check_source_binding({'source_sha256':bindings},{'step':'a','generation':'b'})
        check_source_binding({'source_sha256':{'step':'a','generation':'b'}},{'step':'a','generation':'b'})

if __name__=='__main__':unittest.main()
