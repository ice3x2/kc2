"""CON-ARCH-006 exported cleanup delta must fail closed."""
import tempfile
import unittest
from pathlib import Path
from shapely.geometry import box


class CleanupDeltaTests(unittest.TestCase):
    def parent_fixture(self,root,kind='direct_v2'):
        import json
        from tools.review_kc2_receiver_cleanup import V2_FIELDS,digest,PARENT_ORIGINAL,PARENT_BUNDLE
        old=dict(schema='lower-void-v2',status='pass',errors=[],side='right',native_readback=False,
                 variants={v:dict(body_count=2,**{k:0 for k in V2_FIELDS}) for v in ('normal','magnetic')},
                 magnet={k:0 for k in ('missing_mm3','extra_mm3','blocked_mm3','entry_obstruction_mm3')},source_sha256={})
        if kind in ('predicate_bundle','strata_bundle'):
            old.update(status='fail',errors=[v+': component_obstruction_mm3' for v in ('normal','magnetic')])
            for row in old['variants'].values():row['component_obstruction_mm3']=46.794929654225015
        bundle=dict(schema='right-lower-predicate-bundle-v1',status='pass',original_v2_status=old['status'],
                    component_clearance={'computed_common_volume_mm3':None},source_sha256={})
        originals={PARENT_ORIGINAL:json.dumps(old).encode(),PARENT_BUNDLE:json.dumps(bundle).encode()}
        strata_path='.codex-tmp/registered-housing-fit/lower/right-strata-predicate-bundle.json'
        strata=dict(bundle,schema='right-lower-strata-predicate-bundle-v1',component_clearance={
            'computed_common_volume_mm3':None,'method':'complete_normal_strata_with_actual_magnetic_subset',
            'disjointness_proved':True})
        originals[strata_path]=json.dumps(strata).encode()
        repository=Path(__file__).resolve().parents[1]
        for name in ('kc2_lower_predicate_bundle.py','test_kc2_lower_predicate_bundle.py','kc2_registered_release_gate.py',
                     'kc2_required_lower_clearance.py','kc2_component_local_certificate.py'):
            originals['tools/'+name]=(repository/'tools'/name).read_bytes()
        if kind=='strata_bundle':
            for name in ('kc2_lower_strata_bundle','kc2_lower_strata','kc2_magnetic_subset'):
                path=repository/'tools'/(name+'.py')
                originals['tools/'+name+'.py']=path.read_bytes()
        snapshot=dict(path_mapping={},historical_original_sha256={},source_sha256={},parent_proof_kind=kind)
        for i,(name,data) in enumerate(originals.items()):
            target='archive/'+str(i);p=root/target;p.parent.mkdir(exist_ok=True);p.write_bytes(data)
            sha=digest(p);snapshot['path_mapping'][name]=target;snapshot['historical_original_sha256'][name]=sha;snapshot['source_sha256'][target]=sha
        logical={'direct_v2':PARENT_ORIGINAL,'predicate_bundle':PARENT_BUNDLE,'strata_bundle':strata_path}[kind]
        snapshot.update(parent_proof_path=logical,parent_proof_sha256=snapshot['historical_original_sha256'][logical])
        return snapshot

    def test_strata_parent_selector_reaches_only_strata_validator(self):
        from tools.review_kc2_receiver_cleanup import qualify_parent
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);snapshot=self.parent_fixture(root,'strata_bundle')
            with patch('tools.kc2_lower_predicate_bundle.validate_bundle',side_effect=AssertionError('wrong validator')), \
                    patch('tools.kc2_lower_strata_bundle.validate_bundle',return_value=True):
                result=qualify_parent(root,snapshot)
            self.assertEqual(result['component_method'],'whole_normal_z_strata_plus_actual_magnetic_subset')

    def test_strata_parent_exact_archived_helpers_and_null_common(self):
        import json
        from unittest.mock import patch
        from tools.review_kc2_receiver_cleanup import qualify_parent,digest
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);snapshot=self.parent_fixture(root,'strata_bundle')
            with patch('tools.kc2_lower_strata_bundle.validate_bundle',return_value=True) as validator:
                result=qualify_parent(root,snapshot)
                validator.assert_called_once()
            self.assertFalse(result['old_v2_exact_zero'])
            self.assertEqual(result['original_v2_status'],'fail')
            self.assertIsNone(result['component_common_volume_mm3'])
            self.assertEqual(result['component_method'],'whole_normal_z_strata_plus_actual_magnetic_subset')
            with patch('tools.kc2_lower_strata_bundle.validate_bundle',return_value=False):
                with self.assertRaises(ValueError):qualify_parent(root,snapshot)
            logical=snapshot['parent_proof_path'];path=root/snapshot['path_mapping'][logical]
            data=json.loads(path.read_text());data['component_clearance']['computed_common_volume_mm3']=0
            path.write_text(json.dumps(data));sha=digest(path)
            snapshot['historical_original_sha256'][logical]=sha;snapshot['source_sha256'][snapshot['path_mapping'][logical]]=sha;snapshot['parent_proof_sha256']=sha
            with patch('tools.kc2_lower_strata_bundle.validate_bundle',return_value=True):
                with self.assertRaises(ValueError):qualify_parent(root,snapshot)
            for name in ('kc2_lower_strata_bundle','kc2_lower_strata','kc2_magnetic_subset',
                         'kc2_lower_predicate_bundle','kc2_registered_release_gate','kc2_required_lower_clearance'):
                snapshot=self.parent_fixture(root,'strata_bundle')
                logical='tools/'+name+'.py';path=root/snapshot['path_mapping'][logical]
                path.write_bytes(path.read_bytes()+b'\n# different archived qualifier\n');sha=digest(path)
                snapshot['historical_original_sha256'][logical]=sha;snapshot['source_sha256'][snapshot['path_mapping'][logical]]=sha
                with patch('tools.kc2_lower_strata_bundle.validate_bundle',return_value=True):
                    with self.assertRaisesRegex(ValueError,'archived revision'):qualify_parent(root,snapshot)

    def test_parent_direct_and_no_current_read_fallback(self):
        from tools.review_kc2_receiver_cleanup import qualify_parent,historical_reader
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);snapshot=self.parent_fixture(root)
            result=qualify_parent(root,snapshot)
            self.assertTrue(result['old_v2_exact_zero'])
            (root/'unlisted').write_text('current data')
            with self.assertRaises(ValueError):historical_reader(root,snapshot)('unlisted')
            snapshot['parent_proof_kind']='unknown'
            with self.assertRaises(ValueError):qualify_parent(root,snapshot)

    def test_bundle_validator_must_run_and_original_failure_not_zeroed(self):
        from unittest.mock import patch
        from tools.review_kc2_receiver_cleanup import qualify_parent
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);snapshot=self.parent_fixture(root,'predicate_bundle')
            with patch('tools.kc2_lower_predicate_bundle.validate_bundle',return_value=True) as validate:
                result=qualify_parent(root,snapshot)
                validate.assert_called_once()
            self.assertFalse(result['old_v2_exact_zero'])
            self.assertEqual(result['original_v2_status'],'fail')
            self.assertIsNone(result['component_common_volume_mm3'])
            self.assertTrue(result['predicates_qualified'])
            with patch('tools.kc2_lower_predicate_bundle.validate_bundle',side_effect=ValueError('missing full proof')):
                with self.assertRaises(ValueError):qualify_parent(root,snapshot)
            snapshot['parent_proof_kind']='direct_v2'
            with self.assertRaises(ValueError):qualify_parent(root,snapshot)

    def test_bundle_rejects_synthetic_boolean_zero_and_alias_change(self):
        import json
        from unittest.mock import patch
        from tools.review_kc2_receiver_cleanup import qualify_parent,PARENT_BUNDLE,digest
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);snapshot=self.parent_fixture(root,'predicate_bundle');path=root/snapshot['path_mapping'][PARENT_BUNDLE]
            data=json.loads(path.read_text());data['component_clearance']['computed_common_volume_mm3']=0
            path.write_text(json.dumps(data));sha=digest(path)
            snapshot['historical_original_sha256'][PARENT_BUNDLE]=sha;snapshot['source_sha256'][snapshot['path_mapping'][PARENT_BUNDLE]]=sha;snapshot['parent_proof_sha256']=sha
            with patch('tools.kc2_lower_predicate_bundle.validate_bundle',return_value=True):
                with self.assertRaises(ValueError):qualify_parent(root,snapshot)

    def test_compound_subject_and_touching_tools_have_set_semantics(self):
        import cadquery as cq
        from tools.review_kc2_receiver_cleanup import subtract,intersection
        from tools.review_kc2_local_covers import prism
        subject=cq.Compound.makeCompound([*prism(box(0,0,2,2),0,2).Solids(),*prism(box(4,0,6,2),0,2).Solids()])
        tools=cq.Compound.makeCompound([*prism(box(-1,-1,7,3),0,1).Solids(),*prism(box(-1,-1,7,3),1,2).Solids()])
        self.assertEqual(subtract(subject,tools).Volume(),0)
        self.assertAlmostEqual(intersection(subject,tools).Volume(),16)

    def test_role_inventory_exact_and_individual_metrics_required(self):
        from tools.review_kc2_receiver_cleanup import ROLE_NAMES,validate_roles,transfer_eligible,ZERO_FIELDS
        expected={'support_posts','rail','mounting_lands','reset_local_support','existing_reinforced_socket_covers','new_perimeter_wall','registrar_top_a','registrar_top_b','registrar_outer'}
        self.assertEqual(ROLE_NAMES,expected)
        validate_roles({k:box(0,0,1,1) for k in expected})
        with self.assertRaises(ValueError):validate_roles({'registrars':box(0,0,1,1)})
        row={k:0 for k in ZERO_FIELDS};row.update(removed_mm3=1,body_count=2,matched_body_count=2,valid_solids=True)
        pair={'normal_minus_magnetic_mm3':0,'magnetic_minus_normal_mm3':0}
        self.assertFalse(transfer_eligible({'normal':row,'magnetic':row},pair,True))
        row.update(required_stock_details_mm3=[1,-1],required_stock_count=2,protected_role_details_mm3={k:0 for k in expected})
        self.assertFalse(transfer_eligible({'normal':row,'magnetic':row},pair,True))

    def test_bool_nan_negative_not_numeric_zero(self):
        from tools.review_kc2_receiver_cleanup import transfer_eligible,ZERO_FIELDS,ROLE_NAMES
        row={k:0 for k in ZERO_FIELDS};row.update(removed_mm3=1,body_count=2,matched_body_count=2,valid_solids=True,
            required_stock_details_mm3=[0],required_stock_count=1,protected_role_details_mm3={k:0 for k in ROLE_NAMES})
        pair={'normal_minus_magnetic_mm3':0,'magnetic_minus_normal_mm3':0}
        for value in (False,float('nan'),-1e-15):
            bad=dict(row,added_mm3=value)
            self.assertFalse(transfer_eligible({'normal':bad,'magnetic':row},pair,True))
        self.assertFalse(transfer_eligible({'normal':dict(row,body_count=2.0),'magnetic':row},pair,True))
        self.assertFalse(transfer_eligible({'normal':row,'magnetic':row},dict(pair,normal_minus_magnetic_mm3=False),True))

    def test_exact_subset_passes_and_floor_damage_fails(self):
        from tools.review_kc2_receiver_cleanup import audit_variant
        from tools.review_kc2_local_covers import prism
        a=prism(box(-5,0,-2,4),-2.2,2.5)
        b=prism(box(0,0,5,5),-2.2,2.5)
        cutter=prism(box(0,0,1,1),-1,2.5)
        floor=prism(box(-6,-1,6,6),-2.2,-1)
        new=b.cut(cutter)
        row,_=audit_variant([a,b],[a,new],cutter,floor,{},[],None)
        self.assertEqual(row['added_mm3'],0)
        self.assertEqual(row['off_cutter_removed_mm3'],0)
        self.assertGreater(row['removed_mm3'],0)
        bad=new.cut(prism(box(0,0,1,1),-2.2,-1))
        row,_=audit_variant([a,b],[a,bad],cutter,floor,{},[],None)
        self.assertGreater(row['floor_removed_mm3'],0)
        self.assertGreater(row['off_cutter_removed_mm3'],0)

    def test_protected_stock_and_added_material_rejected(self):
        from tools.review_kc2_receiver_cleanup import audit_variant
        from tools.review_kc2_local_covers import prism
        a=prism(box(-5,0,-2,4),-2.2,2.5);b=prism(box(0,0,5,5),-2.2,2.5)
        cutter=prism(box(0,0,1,1),-1,2.5);floor=prism(box(-6,-1,6,6),-2.2,-1)
        row,_=audit_variant([a,b],[a,b.cut(cutter)],cutter,floor,{'post':cutter},[cutter],cutter)
        self.assertGreater(row['protected_roles_removed_mm3'],0)
        self.assertGreater(row['required_stock_removed_mm3'],0)
        self.assertGreater(row['pocket_entry_protected_material_removed_mm3'],0)
        with self.assertRaises(ValueError):audit_variant([a,b],[b],cutter,floor,{},[],None)

    def test_tiny_nonzero_cannot_transfer(self):
        from tools.review_kc2_receiver_cleanup import transfer_eligible,ZERO_FIELDS,ROLE_NAMES
        row={k:0 for k in ZERO_FIELDS}
        row.update(removed_mm3=1,body_count=2,matched_body_count=2,valid_solids=True)
        row.update(required_stock_details_mm3=[0],required_stock_count=1,protected_role_details_mm3={k:0 for k in ROLE_NAMES})
        paired={'normal_minus_magnetic_mm3':0,'magnetic_minus_normal_mm3':0}
        self.assertTrue(transfer_eligible({'normal':row,'magnetic':row},paired,True))
        bad=dict(row,added_mm3=1e-15)
        self.assertFalse(transfer_eligible({'normal':bad,'magnetic':row},paired,True))
        del bad['floor_removed_mm3']
        self.assertFalse(transfer_eligible({'normal':bad,'magnetic':row},paired,True))

    def test_snapshot_alias_requires_old_hash_and_safe_path(self):
        from tools.review_kc2_receiver_cleanup import resolve_historical,digest
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'archive').mkdir();(root/'archive/a').write_text('old')
            sha=digest(root/'archive/a')
            snapshot={'path_mapping':{'live':'archive'},'historical_original_sha256':{'live/a':sha},'source_sha256':{'archive/a':sha}}
            self.assertEqual(resolve_historical(root,snapshot,'live/a',sha),root/'archive/a')
            with self.assertRaises(ValueError):resolve_historical(root,snapshot,'live/a','wrong')
            snapshot['path_mapping']={'live':'../outside'}
            with self.assertRaises(ValueError):resolve_historical(root,snapshot,'live/a',sha)


if __name__=='__main__':unittest.main()
