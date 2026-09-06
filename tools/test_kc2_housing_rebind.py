"""CON-ARCH-006 source refresh must never conceal changed geometry."""
import copy
import unittest

from tools.rebind_kc2_housing_source import geometry_signature


class HousingRebindTests(unittest.TestCase):
    def test_only_explicit_source_identity_is_ignored(self):
        old = {'path':'old', 'battery_above_carrier':{'source_board':'old','source_board_sha256':'old','center':[1,2]},
               'switches':[{'center':[3,4]}], 'routed_copper_exact':[{'radius_mm':.1}]}
        new = copy.deepcopy(old)
        new['path']='new'
        new['battery_above_carrier'].update(source_board='new',source_board_sha256='new')
        self.assertEqual(geometry_signature(old),geometry_signature(new))
        for mutate in (lambda d:d['switches'][0]['center'].__setitem__(0,4),
                       lambda d:d['routed_copper_exact'][0].__setitem__('radius_mm',.2),
                       lambda d:d['battery_above_carrier']['center'].__setitem__(0,2)):
            changed=copy.deepcopy(new)
            mutate(changed)
            self.assertNotEqual(geometry_signature(old),geometry_signature(changed))


if __name__=='__main__':
    unittest.main()
