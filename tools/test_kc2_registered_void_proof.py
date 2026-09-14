"""CON-ARCH-006 explicit right strata proof, not a fabricated V2 pass."""
import unittest
from unittest.mock import patch
from tools import publish_kc2_registered_housings as publish
from tools import kc2_receiver_bundle_transfer as transfer
from tools.kc2_lower_native_transfer import recipe


class VoidProofTests(unittest.TestCase):
    def test_right_source_and_native_recipe_use_explicit_transfer(self):
        wanted=transfer.output_path('strata_bundle')
        self.assertEqual(publish.report_paths()['right:void'],wanted)
        self.assertEqual(recipe('void','right',None)['source'],wanted)
        self.assertEqual(publish.report_paths()['left:void'],publish.STAGE+'/lower/left-void-review.json')

    def test_complete_validator_required_and_source_semantics_preserved(self):
        record={'schema':'right-receiver-strata-predicate-transfer-v1'}
        read=lambda name:b'fixture'
        with patch.object(transfer,'validate',return_value=True) as check:
            publish.check_void_proof(record,'right',False,read)
            check.assert_called_once_with(record,read,kind='strata_bundle')
            for side,native in [('left',False),('right',True)]:
                with self.assertRaises(ValueError):publish.check_void_proof(record,side,native,read)
            check.return_value=False
            with self.assertRaises(ValueError):publish.check_void_proof(record,'right',False,read)
        for schema in ('right-lower-strata-predicate-bundle-v1','lower-void-v2','unknown'):
            with self.assertRaises(ValueError):publish.check_void_proof({'schema':schema,'status':'fail'},'right',False,read)


if __name__=='__main__':unittest.main()
