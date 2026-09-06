"""OPS-ARCH-007 AC-5: actual-coordinate, millimetre overlay contract."""
import unittest
import xml.etree.ElementTree as ET
from tools import generate_kc2_first_order_overlay as target


class OverlayTests(unittest.TestCase):
    def test_exact_scale_and_centers(self):
        data = dict(edges=[[0, 0, 30, 0], [30, 0, 30, 25]],
                    switches=[dict(ref='SW1', center=[12, 13], rotation=0)],
                    pads=[dict(ref='U1', number='1', center=[3, 4], drill=.95),
                          dict(ref='SW1', number='1', center=[9, 10], drill=1.6),
                          dict(ref='MH1', number='', center=[20, 21], drill=1.6)])
        root = ET.fromstring(target.render_svg(data, 'left', 'a'*64))
        self.assertEqual(root.attrib['width'], '70mm')
        self.assertEqual(root.attrib['viewBox'], '-5 -5 70 45')
        ns = {'s': 'http://www.w3.org/2000/svg'}
        rect = root.find(".//s:rect[@data-ref='SW1']", ns)
        self.assertEqual((rect.attrib['x'], rect.attrib['y'], rect.attrib['width']), ('5', '6', '14'))
        pad = root.find(".//s:circle[@data-ref='U1:1']", ns)
        self.assertEqual((pad.attrib['cx'], pad.attrib['cy'], pad.attrib['r']), ('3', '4', '0.475'))
        self.assertIn('not a full-travel fit approval', ''.join(root.itertext()))
        self.assertIn('50 mm', ''.join(root.itertext()))
        self.assertIn('100%', ''.join(root.itertext()))

    def test_refuses_empty_outline(self):
        with self.assertRaises(ValueError):
            target.render_svg(dict(edges=[], switches=[], pads=[]), 'left', 'a'*64)


if __name__ == '__main__':
    unittest.main()
