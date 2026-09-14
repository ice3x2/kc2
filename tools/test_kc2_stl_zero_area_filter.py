"""CON-ARCH-006 exact serialized degeneracies only, no mesh repair waiver."""
import struct
import unittest
import numpy as np
import trimesh
from tools import kc2_stl_zero_area_filter as filter_stl


def append(data,triangles):
    count=struct.unpack_from('<I',data,80)[0]
    extra=b''.join(struct.pack('<12fH',0,0,0,*np.asarray(t).reshape(-1),0) for t in triangles)
    return data[:80]+struct.pack('<I',count+len(triangles))+data[84:]+extra


class FilterTests(unittest.TestCase):
    def test_float64_cancellation_does_not_delete_positive_area(self):
        tri=np.asarray([[1e20,1e20,0],[1e-20,0,0],[0,-1e-20,0]],dtype=np.float32).astype(float)
        self.assertTrue(np.all(np.cross(tri[1]-tri[0],tri[2]-tri[0])==0))
        self.assertFalse(filter_stl.exact_zero_facet(tri))

    def setUp(self):
        self.box=trimesh.creation.box().export(file_type='stl')

    def test_six_zero_facets_only_and_noop_identity(self):
        output,record=filter_stl.normalize(self.box)
        self.assertEqual(output,self.box);self.assertEqual(record['removed_count'],0)
        triangles=[[[.5,.5,.5],[.5,.5,.5],[-.5,.5,.5]]]*6
        original=append(self.box,triangles)
        output,record=filter_stl.normalize(original)
        self.assertEqual(output,self.box)
        self.assertEqual(record['removed_count'],6)
        self.assertEqual(len(record['removed_facets']),6)
        self.assertTrue(all(r['area_mm2']==0 for r in record['removed_facets']))
        self.assertEqual(record['surviving_oriented_records_sha256'],record['output_oriented_records_sha256'])
        self.assertEqual(record['volume_delta_mm3'],0)

    def test_hole_tiny_positive_nonfinite_and_remote_zero_fail(self):
        count=struct.unpack_from('<I',self.box,80)[0]
        hole=self.box[:80]+struct.pack('<I',count-1)+self.box[84:-50]
        tiny=append(self.box,[[[0,0,0],[.000001,0,0],[0,.000001,0]]])
        nonfinite=append(self.box,[[[float('nan'),0,0],[0,0,0],[0,0,0]]])
        remote=append(self.box,[[[100,0,0],[100,0,0],[100,0,0]]])
        for data in (hole,tiny,nonfinite,remote,self.box[:-1]):
            with self.assertRaises(ValueError):filter_stl.normalize(data)


if __name__=='__main__':unittest.main()
