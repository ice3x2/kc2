"""CON-ARCH-006 stale pre-height-change native records must fail closed."""
import unittest
from tools.kc2_lower_native_identity import native_output
class NativeIdentity(unittest.TestCase):
    def record(self):return dict(status='pass',selected_job='lower:left:normal',outputs={'lower:left:normal':dict(round_trip_verified=True,generation_sha256='g',source_sha256='s',expected_body_count=1,readback_step='x.step',readback_sha256='r',f3d='x.f3d',f3d_sha256='f')})
    def test_current_identity_accepted(self):self.assertEqual(native_output(self.record(),'left','normal','g','s')['readback_sha256'],'r')
    def test_stale_generation_rejected(self):
        with self.assertRaises(ValueError):native_output(self.record(),'left','normal','new-g','s')
    def test_wrong_variant_rejected(self):
        with self.assertRaises(ValueError):native_output(self.record(),'left','magnetic','g','s')
if __name__=='__main__':unittest.main()
