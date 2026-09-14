"""OPS-ARCH-006 final guide is gated separately from the reviewed draft."""
import json
import unittest
from tools import publish_kc2_registered_housings as p

def guide():
    facts=dict(status='final_release_payload',physical_qualified=False,silicone_feet='deferred_by_user',
      bridge_mm=5.7,low_profile_plate_support_required=True,scale_percent=100,solid_print_infill_percent=100,
      pcb_bottom_z_mm=2.5,pcb_top_z_mm=4.1,magnet_diameter_mm=2,magnet_thickness_mm=1,
      magnet_original_pocket_depth_mm=1.2,magnet_external_seat_depth_mm=2.8)
    links='\n'.join('[STL]('+n.split('/')[-1]+')' for n in p.inventory() if n.endswith('.stl'))
    return '# Current housing print guide\n5.70 mm bridge; 100% scale and infill.\n'+p.VERIFY_COMMAND+'\n'+links+'\n<!-- kc2-release-guide '+json.dumps(facts)+' -->\n'

class GuideTests(unittest.TestCase):
    def test_final_guide_requires_links_disclosures_and_command(self):
        text=guide();p.check_guide(text)
        for old,new in [('5.70','5.00'),(p.VERIFY_COMMAND,'old verify'),('final_release_payload','draft')]:
            with self.assertRaises(ValueError):p.check_guide(text.replace(old,new))
    def test_new_guide_has_single_active_mapping(self):
        self.assertEqual(p.destination(p.STAGE+'/publication/PRINT-registered-housings.md'),p.NEW_GUIDE)
        self.assertEqual(p.destination(p.STAGE+'/publication/models-README.md'),'hardware/MODELS/README.md')

if __name__=='__main__':unittest.main()
