"""CON-ARCH-006 lower A/B plan uses retained masks, not global scaling."""
import json
from pathlib import Path
import unittest
from tools.stage_kc2_ab_lower import lower_domains


class LowerDomainsTest(unittest.TestCase):
    def test_retained_report_domains_valid_and_separated(self):
        report=json.loads(Path('docs/reports/reinforced-covers-20260913/right-lower.json').read_text())
        a,b=lower_domains(report)
        self.assertTrue(a.is_valid and b.is_valid)
        self.assertEqual(a.geom_type,'Polygon')
        self.assertGreater(a.distance(b),.19)
        self.assertLess(a.distance(b),.21)


if __name__=='__main__':unittest.main()
