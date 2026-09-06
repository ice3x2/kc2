"""CON-ARCH-004: user-approved single-layer flange ring geometry."""
import unittest
from collections import Counter
from tools.generate_kc2_ring_adapters import mesh, SPECS


class RingTests(unittest.TestCase):
    def test_dimensions_and_open_bore(self):
        for name, bore in [('v1', 3.50), ('mx', 4.10)]:
            vertices, faces = mesh(bore)
            self.assertEqual(SPECS[name], bore)
            self.assertAlmostEqual(min(v[2] for v in vertices), 0)
            self.assertAlmostEqual(max(v[2] for v in vertices), 1.4)
            self.assertEqual(sorted(set(round(v[2], 6) for v in vertices)), [0, .2, 1.4])
            self.assertAlmostEqual(max(v[0] for v in vertices), 3)
            self.assertAlmostEqual(min((v[0]**2+v[1]**2)**.5 for v in vertices), bore/2)
            upper = [v for v in vertices if v[2] > .2]
            self.assertAlmostEqual(max(v[0] for v in upper), 2.4)

    def test_closed_consistently_oriented_positive_volume(self):
        for bore in SPECS.values():
            vertices, faces = mesh(bore)
            edges = Counter((a,b) for f in faces for a,b in zip(f, f[1:]+f[:1]))
            self.assertTrue(all(n == 1 and edges[b,a] == 1 for (a,b),n in edges.items()))
            volume = 0
            for face in faces:
                a,b,c = [vertices[i] for i in face]
                volume += (a[0]*(b[1]*c[2]-b[2]*c[1])+a[1]*(b[2]*c[0]-b[0]*c[2])+a[2]*(b[0]*c[1]-b[1]*c[0]))/6
            import math
            expected = math.pi*((3**2-(bore/2)**2)*.2+(2.4**2-(bore/2)**2)*1.2)
            self.assertGreater(volume, 0)
            self.assertAlmostEqual(volume/expected, 1, places=3)

    def test_rejects_impossible_bore(self):
        for bore in [0, -1, 4.8, 5]:
            with self.assertRaises(ValueError):
                mesh(bore)

if __name__ == '__main__':
    unittest.main()
