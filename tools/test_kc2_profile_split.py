"""CON-ARCH-006 actual profile clip rings survive enlarged A/B slot."""
import json
from pathlib import Path
import unittest
from shapely import wkt
from tools.kc2_profile_split import profile_split


class ProfileSplitTest(unittest.TestCase):
    def test_actual_family_apertures_keep_point_six_ring(self):
        from shapely import affinity
        for kind in ['mx','choc_v1','deep_sea']:
            with self.subTest(kind=kind):
                r=json.loads(Path(f'docs/reports/solid-filled-plates-20260913/right-{kind}.json').read_text())
                p={k:wkt.loads(v) for k,v in r['plan_wkt'].items()}
                a,b,report=profile_split(p['domain'],p['openings'],p['service'],r['mounting_centers'])
                self.assertGreaterEqual(a.distance(b),.39999)
                self.assertEqual(report['capture_count'],2)
                self.assertEqual(len(report['capture_features']),2)
                self.assertGreaterEqual(min(report['clamp_counts']),2)
                zones=[]
                for feature in report['capture_features']:
                    donor,receiver=(a,b) if feature['donor']=='a' else (b,a)
                    key=wkt.loads(feature['key_wkt']);slot=wkt.loads(feature['slot_wkt'])
                    collar=wkt.loads(feature['receiver_wkt']).difference(slot)
                    self.assertTrue(donor.buffer(1e-6).covers(key))
                    self.assertTrue(receiver.buffer(1e-6).covers(collar))
                    self.assertLess(receiver.intersection(slot).area,1e-8)
                    zones.append(wkt.loads(feature['zone_wkt']))
                self.assertLess(zones[0].intersection(zones[1]).area,1e-8)
                for opening in p['openings'].geoms:
                    ring=opening.buffer(.6).difference(opening)
                    self.assertTrue(any(mask.buffer(1e-6).covers(ring) for mask in (a,b)))
                for dx,dy in [(1,0),(-1,0),(0,1),(0,-1)]:
                    self.assertGreater(affinity.translate(a,xoff=dx,yoff=dy).intersection(b).area,1e-6)


if __name__=='__main__':unittest.main()
