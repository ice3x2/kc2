"""CON-ARCH-006 backend selection must bind and restore both exact auditors."""
import unittest
from unittest.mock import Mock
from tools.review_kc2_registered_upper_faces import use_backend

class BackendTests(unittest.TestCase):
    def test_both_geometry_functions_replaced_and_restored(self):
        module=Mock();old=(module.section_geometry,module.audit_prismatic_solid)
        with use_backend(module):
            self.assertNotEqual(module.section_geometry,old[0])
            self.assertNotEqual(module.audit_prismatic_solid,old[1])
        self.assertEqual((module.section_geometry,module.audit_prismatic_solid),old)

if __name__=='__main__':unittest.main()
