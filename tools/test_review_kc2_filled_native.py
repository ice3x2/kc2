"""CON-ARCH-006 fail-closed native identity checks before expensive CAD reads."""
import copy,unittest
from tools.review_kc2_filled_native import identity_errors


class NativeIdentityTests(unittest.TestCase):
    def fixture(self):
        outputs={}
        for s in ['left','right']:
            for k in ['mx','choc_v1','deep_sea']:
                stem=f'kc2_{s}_{k}_upper_housing'
                outputs[s+'_'+k]=dict(source_step=stem+'.step',f3d=stem+'.f3d',
                    readback_step=stem+'.native-readback.step',generation_record=s+'-'+k+'.json',round_trip_verified=True)
        return dict(status='pass',physical_qualified=False,outputs=outputs)

    def test_complete_identity(self):self.assertEqual(identity_errors(self.fixture()),[])

    def test_missing_variant_and_wrong_file_identity_rejected(self):
        r=self.fixture();r['outputs'].pop('right_deep_sea')
        self.assertIn('incomplete native variants',identity_errors(r))
        r=self.fixture();r['outputs']['left_mx']['readback_step']='../unrelated.step'
        self.assertIn('left_mx readback_step identity',identity_errors(r))

    def test_unreopened_or_physical_claim_rejected(self):
        r=self.fixture();r['outputs']['left_choc_v1']['round_trip_verified']=False
        self.assertIn('left_choc_v1 not reopened',identity_errors(r))
        r=self.fixture();r['physical_qualified']=True
        self.assertIn('physical qualification not established',identity_errors(r))


if __name__=='__main__':unittest.main()
