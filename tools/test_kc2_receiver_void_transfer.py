"""CON-ARCH-006 subtraction proof must not masquerade as a V2 rerun."""
import copy,math,unittest
from tools import kc2_receiver_void_transfer as t
from tools import publish_kc2_registered_housings as p

class ReceiverTransferTests(unittest.TestCase):
    def old(self):
        return dict(status='pass',errors=[],schema='lower-void-v2',side='right',native_readback=False,
          variants={v:dict(body_count=2,**{k:0. for k in p.LOWER_VOID_ZERO}) for v in t.VARIANTS},
          magnet=dict(original_mm3=10.,revised_mm3=20.,missing_mm3=0.,extra_mm3=0.,blocked_mm3=0.,entry_obstruction_mm3=0.),
          component_envelope=dict(required_clearance_mm=.3,conservative_offset_mm=.301,quad_segs=4,circumscribed_buffer_radius_mm=.301/math.cos(math.pi/16),z_mm=[-.4,2.5],raw_classes_wkt={k:'POLYGON EMPTY' for k in p.COMPONENT_CLASSES},required_union_wkt='POLYGON ((0 0,1 0,1 1,0 0))'))
    def proof(self):
        return dict(schema=t.DELTA_SCHEMA,status='pass',errors=[],side='right',native_readback=False,actual_exported_STEP_reimported=True,strict_transfer_eligible=True,cut_z_mm=[-1,2.5],ys_mm=[73.25,86.25],
          variants={v:dict(body_count=2,matched_body_count=2,valid_solids=True,removed_mm3=10.,**{k:0. for k in t.DELTA_ZERO}) for v in t.VARIANTS},
          paired_removal=dict(normal_minus_magnetic_mm3=0.,magnetic_minus_normal_mm3=0.))
    def test_only_exact_independent_delta_can_transfer(self):
        t.check_predicates(self.old(),self.proof())
        for value in (1e-14,-1e-14,False,None,float('nan'),float('inf')):
            for key in t.DELTA_ZERO:
                bad=self.proof();bad['variants']['magnetic'][key]=value
                with self.subTest(value=value,key=key),self.assertRaises(ValueError):t.check_predicates(self.old(),bad)
        for field,value in [('actual_exported_STEP_reimported',False),('ys_mm',[73.25]),('cut_z_mm',[-2.2,2.5]),('schema','producer')]:
            with self.assertRaises(ValueError):t.check_predicates(self.old(),dict(self.proof(),**{field:value}))
    def test_original_tolerance_pass_and_pair_cancellation_rejected(self):
        for key in p.LOWER_VOID_ZERO:
            old=self.old();old['variants']['normal'][key]=.00001
            with self.assertRaises(ValueError):t.check_predicates(old,self.proof())
        proof=self.proof();proof['paired_removal']={'normal_minus_magnetic_mm3':1e-15,'magnetic_minus_normal_mm3':-1e-15}
        with self.assertRaises(ValueError):t.check_predicates(self.old(),proof)
        proof=self.proof();proof['variants'].pop('magnetic')
        with self.assertRaises(ValueError):t.check_predicates(self.old(),proof)
    def test_archive_resolution_is_explicit_not_new_hash_substitution(self):
        logical=t.STAGE+'/lower/right-normal/generation.json';target=t.CACHE+'/right-normal/generation.json'
        self.assertEqual(t.archived(logical),target)
        self.assertEqual(t.archived('hardware/MODELS/original.step'),'hardware/MODELS/original.step')
        with self.assertRaises(ValueError):t.archived('../escape')

if __name__=='__main__':unittest.main()
