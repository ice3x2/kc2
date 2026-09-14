"""CON-ARCH-006 distinct disjointness inheritance, never a fabricated zero."""
import copy
import unittest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch
from tools import kc2_receiver_bundle_transfer as transfer
from tools.review_kc2_receiver_cleanup import ZERO_FIELDS, ROLE_NAMES


def fixture():
    parent=dict(kind='predicate_bundle',predicates_qualified=True,old_v2_exact_zero=False,
        original_v2_status='fail',component_common_volume_mm3=None)
    row=dict(body_count=2,matched_body_count=2,valid_solids=True,removed_mm3=10.,
        required_stock_count=1,required_stock_details_mm3=[0.],
        protected_role_details_mm3={k:0. for k in ROLE_NAMES},**{k:0. for k in ZERO_FIELDS})
    proof=dict(schema='right-receiver-cleanup-delta-v2',status='pass',errors=[],side='right',
        native_readback=False,actual_exported_STEP_reimported=True,cut_z_mm=[-1,2.5],ys_mm=[73.25,86.25],
        parent_evidence=parent,parent_predicates_qualified=True,old_v2_exact_zero=False,
        strict_transfer_eligible=True,variants={v:copy.deepcopy(row) for v in ('normal','magnetic')},
        paired_removal=dict(normal_minus_magnetic_mm3=0.,magnetic_minus_normal_mm3=0.))
    return parent,proof


class TransferTests(unittest.TestCase):
    def test_immutable_emitter_does_not_relabel_original_or_accept_stale_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'source';source.write_bytes(b'original')
            record={'source_sha256':{'source':transfer.sha_bytes(source.read_bytes())}}
            with patch.object(transfer,'assemble',return_value=record):
                transfer.emit(root,'strata_bundle')
                output=root/transfer.output_path('strata_bundle')
                self.assertTrue(output.exists())
                self.assertEqual(source.read_bytes(),b'original')
                output.write_bytes(b'conflict')
                with self.assertRaises(ValueError):transfer.emit(root,'strata_bundle')
                source.write_bytes(b'changed')
                with self.assertRaises(ValueError):transfer.emit(root,'predicate_bundle')
                self.assertFalse((root/transfer.output_path('predicate_bundle')).exists())

    def test_strata_transfer_is_explicit_and_distinct(self):
        config=transfer.parent_config('strata_bundle')
        self.assertEqual(config['module'],'kc2_lower_strata_bundle')
        self.assertEqual(config['output'],transfer.STAGE+'/lower/right-strata-predicate-bundle.json')
        self.assertEqual(config['schema'],'right-receiver-strata-predicate-transfer-v1')
        self.assertEqual(config['method'],'whole_normal_z_strata_plus_actual_magnetic_subset')
        self.assertNotEqual(config['schema'],transfer.SCHEMA)
        for name in ('right-normal-strata-review.json','right-magnetic-subset-review.json'):
            self.assertEqual(config['mapping'][transfer.STAGE+'/lower/'+name],transfer.CACHE+'/'+name)
        with self.assertRaises(ValueError):transfer.parent_config('unknown')

    def test_sealed_aliases_current_code_and_final_identity(self):
        self._check_sealed_aliases('predicate_bundle')

    def test_strata_sealed_aliases_current_code_and_final_identity(self):
        self._check_sealed_aliases('strata_bundle')

    def _check_sealed_aliases(self,kind):
        import importlib
        from functools import partial
        from types import SimpleNamespace
        from tools import kc2_receiver_bundle_transfer as implementation
        config=implementation.parent_config(kind)
        transfer=SimpleNamespace(**vars(implementation))
        transfer.bundle=importlib.import_module('tools.'+config['module'])
        transfer.MAPPING=config['mapping']
        transfer.archived=partial(implementation.archived,mapping=config['mapping'])
        transfer.assemble=partial(implementation.assemble,kind=kind)
        files={};root=Path(__file__).resolve().parents[1]
        def put(name,value):files[name]=json.dumps(value).encode();return transfer.sha_bytes(files[name])
        historical={}
        for name in config['helpers']:
            p='tools/'+name+'.py';files[p]=(root/p).read_bytes();historical[p]=transfer.sha_bytes(files[p])
        old={'variants':{v:{'component_obstruction_mm3':46.79} for v in ('normal','magnetic')},'magnet':{},'component_envelope':{}}
        historical[transfer.bundle.ORIGINAL]=put(transfer.archived(transfer.bundle.ORIGINAL),old)
        historical[transfer.bundle.OUTPUT]=put(transfer.archived(transfer.bundle.OUTPUT),{})
        final={}
        for v in ('normal','magnetic'):
            folder=f'{transfer.STAGE}/lower/right-{v}';name=transfer.stem('lower','right',v)
            gp=folder+'/generation.json';sp=folder+'/'+name+'.step'
            files[transfer.archived(sp)]=b'old'+v.encode();historical[sp]=transfer.sha_bytes(files[transfer.archived(sp)])
            historical[gp]=put(transfer.archived(gp),{'outputs':{name+'.step':historical[sp]}})
            files[sp]=b'new'+v.encode();final[sp]=transfer.sha_bytes(files[sp])
            final[gp]=put(gp,dict(status='generated_pending_independent_review',side='right',magnetic=v=='magnetic',body_count=2,
                outputs={name+'.step':final[sp]},source_sha256={transfer.archived(sp):historical[sp]}))
        remapped={transfer.archived(n):s for n,s in historical.items()}
        snap=dict(status='verified_historical_snapshot',path_mapping=transfer.MAPPING,historical_original_sha256=historical,source_sha256=remapped,
            parent_proof_kind=kind,parent_proof_path=transfer.bundle.OUTPUT,parent_proof_sha256=historical[transfer.bundle.OUTPUT])
        ss=put(transfer.SNAPSHOT,snap)
        parent,proof=fixture()
        parent['kind']=kind
        parent.update(logical_report=transfer.bundle.OUTPUT,archived_report=transfer.archived(transfer.bundle.OUTPUT),sha256=historical[transfer.bundle.OUTPUT],
            original_v2_sha256=historical[transfer.bundle.ORIGINAL],component_method=config['method'],
            original_component_obstruction_mm3={v:46.79 for v in ('normal','magnetic')})
        proof['source_sha256']={**remapped,**final,transfer.SNAPSHOT:ss}
        for name in ('review_kc2_receiver_cleanup','test_review_kc2_receiver_cleanup','review_kc2_local_covers','kc2_lower_central_relief','kc2_magnetic_entry','kc2_receiver_bundle_transfer','test_kc2_receiver_bundle_transfer'):
            p='tools/'+name+'.py';files[p]=(root/p).read_bytes()
            if name not in ('kc2_receiver_bundle_transfer','test_kc2_receiver_bundle_transfer'):proof['source_sha256'][p]=transfer.sha_bytes(files[p])
        put(transfer.PROOF,proof)
        with patch.object(transfer.bundle,'validate_bundle',return_value=True) as check:
            report=transfer.assemble(files.__getitem__)
            self.assertEqual(report['schema'],config['schema'])
            check.assert_called_once()
            self.assertIsNone(report['component_clearance']['computed_common_volume_mm3'])
            self.assertNotIn('component_obstruction_mm3',report['derived_noncomponent_upper_bounds']['normal'])
            check.return_value=False
            with self.assertRaises(ValueError):transfer.assemble(files.__getitem__)
            check.return_value=True
            for target in (transfer.archived(transfer.bundle.ORIGINAL),'tools/kc2_required_lower_clearance.py',sp):
                changed=dict(files);changed[target]+=b'changed'
                with self.assertRaises(ValueError):transfer.assemble(changed.__getitem__)
            changed=dict(files);bad=copy.deepcopy(snap);bad['path_mapping']={**bad['path_mapping'],transfer.bundle.OUTPUT:'elsewhere'}
            changed[transfer.SNAPSHOT]=json.dumps(bad).encode()
            with self.assertRaises(ValueError):transfer.assemble(changed.__getitem__)
            changed=dict(files);bad=copy.deepcopy(proof);bad['variants']['normal']['added_mm3']=1e-15
            changed[transfer.PROOF]=json.dumps(bad).encode()
            with self.assertRaises(ValueError):transfer.assemble(changed.__getitem__)
            changed=dict(files);bad=copy.deepcopy(proof);del bad['source_sha256']['tools/kc2_magnetic_entry.py']
            changed[transfer.PROOF]=json.dumps(bad).encode()
            with self.assertRaises(ValueError):transfer.assemble(changed.__getitem__)

    def test_exact_delta_and_parent(self):
        parent,proof=fixture();transfer.check_delta(proof,parent)
        for field in ZERO_FIELDS:
            for value in (1e-15,-1e-15,False,float('nan')):
                bad=copy.deepcopy(proof);bad['variants']['normal'][field]=value
                with self.assertRaises(ValueError):transfer.check_delta(bad,parent)
        for field,value in [('old_v2_exact_zero',True),('parent_predicates_qualified',False),('schema','right-receiver-cleanup-delta-v1')]:
            bad=copy.deepcopy(proof);bad[field]=value
            with self.assertRaises(ValueError):transfer.check_delta(bad,parent)

    def test_individual_stock_and_parent_forgery(self):
        parent,proof=fixture()
        for action in (lambda p:p['variants']['normal'].update(required_stock_details_mm3=[1e-15]),
                       lambda p:p['variants']['normal']['protected_role_details_mm3'].update(rail=1e-15),
                       lambda p:p['parent_evidence'].update(component_common_volume_mm3=0),
                       lambda p:p['variants']['normal'].update(body_count=True)):
            bad=copy.deepcopy(proof);action(bad)
            with self.assertRaises(ValueError):transfer.check_delta(bad,parent)

    def test_missing_sources_fail_closed(self):
        with self.assertRaises(KeyError):transfer.assemble({}.__getitem__)
        with self.assertRaises(KeyError):transfer.assemble({}.__getitem__,kind='strata_bundle')
        with self.assertRaises(ValueError):transfer.assemble({}.__getitem__,kind='unknown')


if __name__=='__main__':unittest.main()
