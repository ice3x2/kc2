"""CON-ARCH-006 diagnostic cannot infer constant Z from one section."""
import unittest
from types import SimpleNamespace as N
from tools.diagnose_kc2_receiver_floor_prism import transitions

class TransitionTests(unittest.TestCase):
    def shape(self,zs,nz=0,kind='PLANE'):
        f=N(geomType=lambda:kind,normalAt=lambda:N(z=nz))
        return N(Vertices=lambda:[N(Z=z) for z in zs],Faces=lambda:[f])
    def test_constant_requires_only_band_endpoints_and_axis_faces(self):
        self.assertEqual(transitions(self.shape([-1,2.5]),-1,2.5),([-1,2.5],[]))
        levels,errors=transitions(self.shape([-1,0,2.5]),-1,2.5)
        self.assertEqual(levels,[-1,0,2.5]);self.assertIn('interior Z transition',errors)
        for shape in (self.shape([-1,2.5],.5),self.shape([-1,2.5],kind='CYLINDER')):
            self.assertTrue(transitions(shape,-1,2.5)[1])

if __name__=='__main__':unittest.main()
