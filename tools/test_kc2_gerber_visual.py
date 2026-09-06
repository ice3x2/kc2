"""CON-ARCH-004 AC-8: actual output rendering, not PCB-source previews."""
import tempfile
import unittest
from pathlib import Path

from tools.render_kc2_gerber_visual import input_paths, rasterize, render_layer


class GerberVisualTests(unittest.TestCase):
    def test_explicit_input_mapping_excludes_drill_maps(self):
        paths = input_paths(Path('review'), 'left', require=False)
        self.assertEqual(len(paths), 11)
        self.assertEqual(paths['PTH'].name, 'kc2_left-PTH.drl')
        self.assertEqual(paths['NPTH'].name, 'kc2_left-NPTH.drl')
        self.assertFalse(any('map' in str(p) for p in paths.values()))
        with self.assertRaises(FileNotFoundError):
            input_paths(Path('nonexistent'), 'left')

    def test_real_gerber_clear_polarity_survives_raster(self):
        # Entirely synthetic geometry: dark disk with a clear disk cutout.
        text = '%FSLAX46Y46*%\n%MOMM*%\n%ADD10C,4.0*%\n%ADD11C,2.0*%\n%LPD*%\nD10*\nX0Y0D03*\n%LPC*%\nD11*\nX0Y0D03*\nM02*\n'
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)/'synthetic.gbr'
            p.write_text(text, encoding='ascii')
            svg = render_layer(p, ((-3,-3),(3,3)))
            from PIL import Image
            import io
            im = Image.open(io.BytesIO(rasterize(svg, 600))).convert('RGB')
            self.assertEqual(im.getpixel((300,300)), (255,255,255))
            self.assertEqual(im.getpixel((450,300)), (0,0,0))
            self.assertEqual(im.getpixel((580,300)), (255,255,255))

    def test_unknown_side_rejected(self):
        with self.assertRaises(ValueError):
            input_paths(Path('review'), 'other', require=False)


if __name__ == '__main__':
    unittest.main()
