"""CON-ARCH-006 variant-specific seats, clear screw pockets and filled interiors."""
import unittest
from shapely.geometry import box,Point
from tools.kc2_filled_plate_profiles import PROFILES,plate_layers


class ProfileContractTests(unittest.TestCase):
    def test_all_requested_variants_exist(self):
        self.assertEqual(set(PROFILES),{'mx','choc_v1','deep_sea'})

    def test_v1_includes_existing_ring_flange_without_using_mx_height(self):
        p=PROFILES['choc_v1']
        self.assertAlmostEqual(p.plate_top,4.1+.2+2.2)
        self.assertAlmostEqual(p.plate_top-p.plate_bottom,1.2)
        self.assertEqual(p.aperture,14.2)

    def test_deep_sea_has_own_no_ring_family_datum(self):
        p=PROFILES['deep_sea']
        self.assertAlmostEqual(p.plate_top,4.1+1.35+.8)
        self.assertAlmostEqual(p.plate_top-p.plate_bottom,1.2)
        self.assertFalse(p.exact_received_part_verified)

    def test_each_low_plate_retains_bearing_floor_and_screw_tip_reserve(self):
        for name in ['choc_v1','deep_sea']:
            p=PROFILES[name]
            with self.subTest(name=name):
                self.assertGreaterEqual(p.bearing-4.1,1-1e-8)
                self.assertAlmostEqual(p.boss_top-(p.bearing+1.2),.3)
                self.assertAlmostEqual(p.bearing-p.screw_length-(-.3),.4)

    def test_mx_original_datums_remain(self):
        p=PROFILES['mx']
        self.assertEqual((p.plate_bottom,p.plate_top,p.bearing,p.screw_length),(7.8,9.3,7.8,7.5))

    def test_complete_fill_and_open_screws_for_every_variant(self):
        domain=box(0,0,40,30);body=box(12,10,28,26);opening=box(13,11,27,25)
        bore=Point(5,5).buffer(.8);pocket=Point(5,5).buffer(1.7)
        boss=Point(5,5).buffer(2.3);land=Point(5,5).buffer(1.5)
        service=box(35,0,40,8)
        for name,profile in PROFILES.items():
            with self.subTest(name=name):
                rows=plate_layers(profile,domain,body,opening,service,bore,pocket,boss,land)
                self.assertTrue(all(r.geometry.intersection(bore).area<1e-9 for r in rows))
                for r in rows:
                    if r.z0>=4.4 and r.z1<=profile.plate_bottom:
                        self.assertTrue(r.geometry.covers(box(2,15,8,22)))
                        self.assertLess(r.geometry.intersection(body).area,1e-9)
                    if r.z0>=profile.bearing:
                        self.assertLess(r.geometry.intersection(pocket).area,1e-9)
                self.assertAlmostEqual(min(r.z0 for r in rows),4.1)
                self.assertAlmostEqual(max(r.z1 for r in rows),profile.boss_top)


if __name__=='__main__':unittest.main()
