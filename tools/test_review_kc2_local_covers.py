"""CON-ARCH-006 local-cover delta must reject structure changes."""
import unittest
from unittest.mock import patch
import tempfile
from pathlib import Path
import cadquery as cq
from shapely.geometry import box
from tools.review_kc2_local_covers import audit_delta,locality_errors
from tools import review_kc2_local_covers as review

def block(x,y,z,dx,dy,dz):return cq.Solid.makeBox(dx,dy,dz,cq.Vector(x,y,z))

class LocalDeltaTests(unittest.TestCase):
    def test_changed_input_during_audit_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'input.step';source.write_text('original')
            bindings={'input.step':review.digest(source)}
            self.assertFalse(review.changed_bindings(root,bindings))
            source.write_text('changed')
            self.assertEqual(review.changed_bindings(root,bindings),['input.step'])
            source.unlink()
            self.assertEqual(review.changed_bindings(root,bindings),['input.step'])
    def setUp(self):
        self.before=block(0,0,-2.2,10,10,4.7)
        self.wall=block(9.8,4,-1,.6,2,3.5)
        self.floor=block(9.8,4,-2.2,.6,2,1.2)
        self.allowed=self.wall.fuse(self.floor)
        self.after=self.before.fuse(self.allowed)
    def test_connected_local_addition_passes(self):
        self.assertFalse(audit_delta(self.before,self.after,self.allowed)['errors'])
    def test_adjacent_wall_floor_compound_allowance_passes(self):
        allowed=cq.Compound.makeCompound([self.wall,self.floor])
        original=cq.Shape.cut
        def individual_solid_operands(subject,*tools,**kwargs):
            self.assertIsInstance(subject,cq.Solid)
            for tool in tools:self.assertIsInstance(tool,cq.Solid)
            return original(subject,*tools,**kwargs)
        with patch.object(cq.Shape,'cut',individual_solid_operands):
            self.assertAlmostEqual(review.cut_union(self.after,allowed).Volume(),
                                   self.after.cut(self.wall,self.floor).Volume())
            result=audit_delta(self.before,self.after,allowed)
        self.assertFalse(result['errors'],result)
    def test_removing_existing_support_fails(self):
        after=self.after.cut(block(2,2,0,1,1,2.5))
        self.assertIn('baseline material removed',audit_delta(self.before,after,self.allowed)['errors'])
    def test_nonlocal_new_wall_fails(self):
        after=self.after.fuse(block(9.8,0,-2.2,1,10,4.7))
        self.assertIn('added material outside local cover allowance',audit_delta(self.before,after,self.allowed)['errors'])
    def test_wall_across_pcb_thickness_fails(self):
        after=self.after.fuse(block(9.8,4,2.4,.6,2,1.7))
        self.assertIn('lower height changed',audit_delta(self.before,after,self.allowed)['errors'])
    def test_missing_requested_cover_fails(self):
        self.assertIn('requested cover missing',audit_delta(self.before,self.before,self.allowed)['errors'])
    def test_clearance_or_pocket_infill_fails(self):
        forbidden=block(10.1,4.5,0,.2,.5,1)
        self.assertIn('protected void obstructed',audit_delta(self.before,self.after,self.allowed,forbidden)['errors'])
    def test_detached_shell_fails(self):
        after=cq.Compound.makeCompound([self.after,block(20,20,0,1,1,1)])
        self.assertIn('solid count changed',audit_delta(self.before,after,self.allowed)['errors'])
    def test_only_existing_point_two_seam_may_omit_patch(self):
        outline=box(0,0,10,10);clearance=box(4.5,9,5.5,11)
        wrapped=clearance.buffer(.401,quad_segs=64)
        patch=outline.union(wrapped).difference(outline.buffer(-.3)).intersection(wrapped.buffer(.3,quad_segs=64))
        wall=patch.difference(clearance);gap=box(4.9,-2,5.1,13)
        parts=[patch.intersection(box(-2,-2,4.9,13)),patch.intersection(box(5.1,-2,12,13))]
        self.assertFalse(locality_errors(outline,clearance,wall,patch,parts,gap))
        parts[0]=parts[0].difference(box(3,10,4.8,12))
        self.assertIn('part patches omit material outside retained seam',locality_errors(outline,clearance,wall,patch,parts,gap))

if __name__=='__main__':unittest.main()
