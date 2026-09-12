"""CON-ARCH-006 combined lower/upper clearance, not plate-only approval."""
import unittest
from shapely.geometry import box
from tools.review_kc2_filled_assembly import check_assembly


class FilledAssemblyTests(unittest.TestCase):
    def fixture(self):
        return {(s,k):box(0 if s=='left' else 11,0,10 if s=='left' else 21,10)
                for s in ['left','right'] for k in ['mx','choc_v1','deep_sea']}

    def test_complete_families_with_original_lower_clearance(self):
        upper=self.fixture();lower={s:upper[s,'mx'] for s in ['left','right']}
        self.assertEqual(check_assembly(upper,lower)['errors'],[])

    def test_lower_extension_collision_not_hidden_by_upper_only_gap(self):
        upper=self.fixture();lower=dict(left=box(0,0,12,10),right=box(11,0,21,10))
        self.assertTrue(check_assembly(upper,lower)['errors'])

    def test_missing_variant_rejected(self):
        upper=self.fixture();lower={s:upper[s,'mx'] for s in ['left','right']};upper.pop(('right','deep_sea'))
        with self.assertRaisesRegex(ValueError,'six'):check_assembly(upper,lower)


if __name__=='__main__':unittest.main()
