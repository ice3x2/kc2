"""CON-ARCH-006 lossless triangulation conformity; no tolerance hole filling."""
import unittest
import numpy as np
import trimesh
from tools.kc2_stl_tjunction import normalize


def example(offset=0.):
    m = trimesh.creation.box()
    triangles = m.triangles.copy()
    a, b, c = triangles[0]
    midpoint = (a+b)/2 + np.array([offset, offset, offset])
    triangles = np.concatenate([triangles[1:], [[a, midpoint, c], [midpoint, b, c]]])
    return trimesh.exchange.stl.export_stl(trimesh.Trimesh(
        vertices=triangles.reshape(-1, 3), faces=np.arange(len(triangles)*3).reshape(-1, 3), process=False))


class TJunctionTests(unittest.TestCase):
    def test_exact_collinear_tjunction_is_closed_without_volume_change(self):
        output, record = normalize(example())
        self.assertEqual(record['split_count'], 1)
        self.assertAlmostEqual(record['volume_delta_mm3'], 0)
        self.assertTrue(record['output_watertight'])

    def test_noncollinear_hole_is_not_filled(self):
        with self.assertRaises(ValueError):
            normalize(example(.01))

    def test_good_mesh_is_byte_identical(self):
        source = trimesh.exchange.stl.export_stl(trimesh.creation.box())
        output, record = normalize(source)
        self.assertEqual(source, output)
        self.assertEqual(record['split_count'], 0)


if __name__ == '__main__':
    unittest.main()
