"""CON-ARCH-006 / OPS-ARCH-006 publication gates."""
import copy
import unittest
from unittest.mock import patch
from tools import publish_kc2_local_covers as p

class PublicationTests(unittest.TestCase):
    def test_native_adaptive_pair_preserves_generation_default_identity(self):
        records=self.publication_fixture();expected={}
        for side in ['left','right']:
            for group in ['lower','upper']:expected.update(p.generation_outputs(side,group,records[side+'-'+group+'.json']))
        kernel=records['native-kernel-review-all.json'];native=records['native-all.json']
        for row in kernel['outputs'].values():
            for field in ['source_solids','reopened_solids']:
                row[field][0]['volume_mm3']+=.03
        self.assertEqual(p.native_errors(native,expected,kernel),[])
        changed=copy.deepcopy(kernel)
        for field in ['source_solids','reopened_solids']:
            changed['outputs']['left_lower'][field][0]['bounds_mm'][0]+=.1
        self.assertTrue(p.native_errors(native,expected,changed))
        kernel['outputs']['left_lower']['default_source_solids'][0]['volume_mm3']+=1
        self.assertTrue(p.native_errors(native,expected,kernel))
    def test_native_chain_requires_export_inventory_and_bound_diagnostics(self):
        records=self.publication_fixture()
        expected={}
        for side in ['left','right']:
            for group in ['lower','upper']:expected.update(p.generation_outputs(side,group,records[side+'-'+group+'.json']))
        native=records['native-all.json'];kernel=records['native-kernel-review-all.json'];export=records['native-review-export-all.json']
        self.assertEqual(p.native_chain_errors(native,expected,kernel,export),[])
        for mutate in [lambda k,e:e.update(status='failed'),lambda k,e:e.update(outputs={}),
                       lambda k,e:k['source_sha256'].pop(p.STAGE+'/native-check-left_lower.step'),
                       lambda k,e:e['outputs']['left_lower'].update(verification_step='other.step'),
                       lambda k,e:e['outputs']['left_lower'].update(verification_step_sha256='b'*64)]:
            k,e=copy.deepcopy(kernel),copy.deepcopy(export);mutate(k,e)
            self.assertTrue(p.native_chain_errors(native,expected,k,e))
    def test_same_kernel_native_gate_binds_exact_archives_and_strict_geometry(self):
        expected,native=self.fixture()
        kernel={'status':'pass','errors':[],'physical_qualified':False,'outputs':{}}
        for label,model in expected.items():
            native['outputs'][label]['f3d_sha256']='b'*64
            kernel['outputs'][label]={'source_step_sha256':model['step_sha256'],
                'default_source_solids':copy.deepcopy(model['solids']),
                'source_f3d_sha256':'b'*64,'source_solids':copy.deepcopy(model['solids']),
                'reopened_solids':copy.deepcopy(model['solids']),'errors':[]}
            # Fusion's approximate mass is compared only to Fusion's own reopen.
            for field in ['source_solids','reopened_solids']:
                native['outputs'][label][field][0]['volume_mm3']+=.01
        self.assertEqual(p.native_errors(native,expected,kernel),[])
        for mutate in [lambda k:k['outputs']['left_lower'].__setitem__('source_f3d_sha256','stale'),
                       lambda k:k['outputs']['left_lower']['reopened_solids'][0].__setitem__('volume_mm3',100.003),
                       lambda k:k['outputs'].pop('right_mx_upper')]:
            changed=copy.deepcopy(kernel);mutate(changed)
            self.assertTrue(p.native_errors(native,expected,changed))

    def assembly_fixture(self):
        return {'status':'pass','errors':[],'physical_qualified':False,'new_fabrication_approval':False,
            'source_sha256':{p.STAGE+'/'+side+'-'+group+'-review.json':'a'*64
                             for side in ['left','right'] for group in ['lower','upper']},
            'joined':{'minimum_gap_mm':1.3,'overlap_mm2':0.,'errors':[]},
            'original_right_transform_mm':{'dx':124.62499999999999,'dy':0.},
            'intent':[{'side':side,'local_lower_openings':count,'lower_max_z_mm':2.5,
                       'upper_skirt_min_z_mm':4.4,'pcb_bottom_top_mm':[2.5,4.1],
                       'upper_skirt_clearance_above_pcb_mm':.3,'new_wall_to_wall_load_path':False,
                       'lower_local_outline_added_mm2':1.,'upper_local_outline_added_mm2':1.}
                      for side,count in [('left',5),('right',7)]],
            'feet':[{'stl':name.split('/')[-1],'centroid_mm':[5.,5.,0.],
                     'centers_xy_mm':[[0.,0.],[10.,0.],[10.,10.],[0.,10.]],'inside_foot_hull':True}
                    for name in sorted(p.expected_cad_names()) if 'lower_housing' in name and name.endswith('.stl')]}

    def test_assembly_requires_complete_evidence_not_just_pass_status(self):
        self.assertEqual(p.assembly_errors(self.assembly_fixture()),[])
        for field in ['joined','intent','feet','original_right_transform_mm','source_sha256']:
            row=self.assembly_fixture();row.pop(field)
            self.assertTrue(p.assembly_errors(row),field)

    def test_assembly_rejects_wrong_clearances_counts_identity_and_claims(self):
        mutations=[lambda r:r['joined'].__setitem__('minimum_gap_mm',float('nan')),
                   lambda r:r['joined'].__setitem__('minimum_gap_mm',.29),
                   lambda r:r['joined'].__setitem__('overlap_mm2',.01),
                   lambda r:r['original_right_transform_mm'].__setitem__('dx',129.225),
                   lambda r:r['intent'][0].__setitem__('local_lower_openings',4),
                   lambda r:r['intent'][0].__setitem__('upper_skirt_min_z_mm',4.1),
                   lambda r:r['intent'][0].__setitem__('new_wall_to_wall_load_path',True),
                   lambda r:r['feet'][0].__setitem__('inside_foot_hull',False),
                   lambda r:r['feet'][0].__setitem__('stl',r['feet'][1]['stl']),
                   lambda r:r['feet'][0].__setitem__('centroid_mm',[float('inf'),0,0]),
                   lambda r:r['source_sha256'].pop(next(iter(r['source_sha256']))),
                   lambda r:r.__setitem__('physical_qualified',True)]
        for mutate in mutations:
            row=self.assembly_fixture();mutate(row)
            self.assertTrue(p.assembly_errors(row))

    def test_incomplete_assembly_summary_has_zero_publication_writes(self):
        records=self.publication_fixture()
        records['independent-review-final.json'].pop('feet')
        with patch.object(p,'read',side_effect=lambda path:copy.deepcopy(records[p.Path(path).name])), patch.object(p,'digest',return_value='a'*64), \
             patch.object(p,'preserved_hardware',return_value={k:'a'*64 for k in p.preserved_paths()}), \
             patch.object(p.shutil,'copyfile') as copies, patch.object(p,'write') as writes:
            with self.assertRaisesRegex(ValueError,'Assembly'):p.publish()
            copies.assert_not_called();writes.assert_not_called()

    def test_native_rejects_oversize_body(self):
        expected,native=self.fixture()
        for records in [expected['left_lower']['solids'],native['outputs']['left_lower']['source_solids'],native['outputs']['left_lower']['reopened_solids']]:
            records[0]['bounds_mm'][3]=151
        self.assertTrue(p.native_errors(native,expected))
    def test_generation_rejects_variant_relabel(self):
        row=self.publication_fixture()['left-lower.json']
        row['outputs']['normal']['step']='kc2_right_lower_housing.step'
        with self.assertRaises(ValueError):p.generation_outputs('left','lower',row)
    def test_portable_rejects_backslash_traversal(self):
        with self.assertRaises(ValueError):p.portable('tools/..\\secret')
    def fixture(self):
        expected={};native={'status':'pass','outputs':{},'physical_qualified':False}
        for side in ['left','right']:
            for kind in ['lower','lower_magnetic','mx_upper']:
                label=side+'_'+kind
                solids=[{'bounds_mm':[0,0,0,10,10,1],'volume_mm3':100.} for _ in range(1 if side=='left' else 2)]
                expected[label]={'step_sha256':'a','solids':solids}
                native['outputs'][label]={'source_sha256':'a','round_trip_verified':True,
                    'source_solids':copy.deepcopy(solids),'reopened_solids':copy.deepcopy(solids)}
        return expected,native
    def test_requires_every_native_and_actual_matching_geometry(self):
        expected,native=self.fixture()
        self.assertEqual(p.native_errors(native,expected),[])
        del native['outputs']['right_mx_upper']
        self.assertTrue(p.native_errors(native,expected))
    def test_rejects_relabelled_or_changed_native(self):
        expected,native=self.fixture()
        native['outputs']['left_lower']['reopened_solids'][0]['volume_mm3']=99
        self.assertTrue(p.native_errors(native,expected))
    def test_rejects_unearned_physical_qualification(self):
        expected,native=self.fixture();native['physical_qualified']=True
        self.assertTrue(p.native_errors(native,expected))
        expected,native=self.fixture();native['outputs']['left_lower']['source_sha256']='stale'
        self.assertTrue(p.native_errors(native,expected))
    def test_portable_paths_no_unresolved_temp_or_alias(self):
        self.assertEqual(p.portable('.codex-tmp/local-cover-build/kc2_left_lower_housing.stl'),
                         'hardware/MODELS/kc2_left_lower_housing.stl')
        self.assertEqual(p.portable('.codex-tmp/local-cover-build/left-lower.json'),
                         'docs/reports/local-covers-20260910/left-lower.json')
        self.assertEqual(p.portable('hardware/kicad/kc2_left/kc2_left.kicad_pcb'),
                         'hardware/PCB/kc2_left/kc2_left.kicad_pcb')
        with self.assertRaises(ValueError):p.portable('.codex-tmp/unknown.json')
    def test_rejects_empty_bindings_and_fake_twenty_one_outputs(self):
        forged={'status':'digital_geometry_verified','physical_qualified':False,
                'new_fabrication_approval':False,'source_sha256':{},
                'baseline_commit':p.BASELINE,
                'preserved_pcb_gerber_sha256':{},'observed_path_mapping':{},
                'outputs':['hardware/MODELS/missing.stl']*21,'native_report':p.REPORT+'/native-all.json'}
        expected,native=self.fixture()
        def fake_read(path):
            name=str(path)
            if name.endswith('kc2_local_cover_manifest.json'):return forged
            if name.endswith('native-all.json'):return native
            return {'outputs':{k:v for k,v in expected.items() if k.startswith('left_' if 'left-' in name else 'right_')}}
        with patch.object(p,'read',side_effect=fake_read):
            with self.assertRaises(ValueError):p.verify()
    def inventory_fixture(self):
        required={path:'a'*64 for path in p.static_inputs()|p.preserved_paths()|p.expected_cad_names()}
        source=p.STAGE+'/kc2_left_lower_housing.step'
        observed={source:p.portable(source)}
        result={'source_sha256':copy.deepcopy(required),'observed_path_mapping':copy.deepcopy(observed),
                'preserved_pcb_gerber_sha256':{path:'a'*64 for path in p.preserved_paths()},
                'outputs':sorted(p.expected_cad_names()),'physical_qualified':False,'new_fabrication_approval':False}
        return result,required,observed
    def test_complete_derived_inventory(self):
        self.assertEqual(p.inventory_errors(*self.inventory_fixture()),[])
        self.assertEqual(len(p.expected_cad_names()),21)
        self.assertEqual(len(p.preserved_paths()),16)
    def test_missing_guide_or_output_binding_rejected(self):
        for path in ['hardware/MODELS/PRINT-local-covers.md','hardware/MODELS/kc2_left_lower_housing.stl']:
            result,required,observed=self.inventory_fixture()
            del result['source_sha256'][path]
            self.assertTrue(p.inventory_errors(result,required,observed))
    def test_report_hash_or_observed_mapping_mismatch_rejected(self):
        result,required,observed=self.inventory_fixture()
        result['source_sha256']['hardware/MODELS/kc2_left_lower_housing.step']='b'*64
        self.assertTrue(p.inventory_errors(result,required,observed))
        result,required,observed=self.inventory_fixture();result['observed_path_mapping']={}
        self.assertTrue(p.inventory_errors(result,required,observed))
    def test_truncated_preservation_inventory_rejected(self):
        result,required,observed=self.inventory_fixture();result['preserved_pcb_gerber_sha256'].pop(next(iter(p.preserved_paths())))
        self.assertTrue(p.inventory_errors(result,required,observed))
    def test_fabrication_approval_rejected(self):
        result,required,observed=self.inventory_fixture();result['new_fabrication_approval']=True
        self.assertTrue(p.inventory_errors(result,required,observed))
    def test_publish_preflight_rejects_bad_native_before_writes(self):
        records=self.publication_fixture()
        records['native-all.json']['outputs']['left_lower']['f3d']='kc2_wrong_lower_housing.f3d'
        with patch.object(p,'read',side_effect=lambda path:copy.deepcopy(records[p.Path(path).name])), patch.object(p,'digest',return_value='a'*64), \
             patch.object(p,'preserved_hardware',return_value={k:'a'*64 for k in p.preserved_paths()}), \
             patch.object(p.shutil,'copyfile') as copies, patch.object(p,'write') as writes:
            with self.assertRaisesRegex(ValueError,'Native filename'):p.publish()
            copies.assert_not_called();writes.assert_not_called()
    def test_publish_incomplete_output_set_has_zero_writes(self):
        records=self.publication_fixture()
        records['left-lower.json']['outputs']['normal']['meshes']={}
        with patch.object(p,'read',side_effect=lambda path:copy.deepcopy(records[p.Path(path).name])), patch.object(p,'digest',return_value='a'*64), \
             patch.object(p,'preserved_hardware',return_value={k:'a'*64 for k in p.preserved_paths()}), \
             patch.object(p.shutil,'copyfile') as copies, patch.object(p,'write') as writes:
            with self.assertRaisesRegex(ValueError,'Expected exact unique'):p.publish()
            copies.assert_not_called();writes.assert_not_called()
    def publication_fixture(self):
        expected,native=self.fixture();records={};sha='a'*64
        for side in ['left','right']:
            outputs={}
            for kind,suffix in [('lower',''),('lower','_magnetic'),('mx_upper','')]:
                label=side+'_'+kind+suffix;base=f'kc2_{side}_{kind}_housing'
                model=expected[label];model.update(step=base+suffix+'.step',step_sha256=sha,
                    meshes={base+part+suffix+'.stl':{'watertight':True,'winding_consistent':True,'shells':1,'sha256':sha}
                            for part in ([''] if side=='left' else ['_part_a','_part_b'])})
                outputs[label]=model
                native['outputs'][label].update(source_sha256=sha,f3d=base+suffix+'.f3d',f3d_sha256=sha)
            for group in ['lower','upper']:
                chosen={'normal':outputs[side+'_lower' if group=='lower' else side+'_mx_upper']}
                if group=='lower':chosen['magnetic']=outputs[side+'_lower_magnetic']
                records[side+'-'+group+'.json']={'status':'generated_not_independently_verified','physical_qualified':False,'outputs':chosen,'source_sha256':{'tools/model.py':sha}}
                records[side+'-'+group+'-review.json']={'status':'pass','errors':[],'source_sha256':{'tools/model.py':sha}}
        for name in p.REVIEW_NAMES:records[name]={'status':'pass','errors':[],'source_sha256':{'tools/model.py':sha}}
        records['independent-review-final.json']=self.assembly_fixture()
        native['script_sha256']=sha;records['native-all.json']=native;records['joined-plan.json']={'dx':1}
        records['native-kernel-review-all.json']={'status':'pass','errors':[],
            'physical_qualified':False,'source_sha256':{'tools/native.py':sha},'outputs':{
                label:{'source_step_sha256':model['step_sha256'],'source_f3d_sha256':sha,
                       'default_source_solids':copy.deepcopy(model['solids']),
                       'source_solids':copy.deepcopy(model['solids']),
                       'reopened_solids':copy.deepcopy(model['solids']),'errors':[]}
                for label,model in expected.items()}}
        kernel=records['native-kernel-review-all.json'];kernel['sources_unchanged']=True
        export={'status':'exported_not_geometry_verified','physical_qualified':False,'sources_unchanged':True,
                'source_sha256':{path:sha for path in ['tools/fusion/KC2LocalNativeReview/KC2LocalNativeReview.py','tools/fusion/KC2StepToF3D/KC2StepToF3D.py']},'outputs':{}}
        kernel['source_sha256']={path:sha for path in ['tools/review_kc2_local_native.py','tools/test_review_kc2_local_native.py',p.STAGE+'/native-review-export-all.json']}
        for label,model in expected.items():
            name=model['step'];f3d=p.Path(name).with_suffix('.f3d').name;check='native-check-'+label+'.step'
            export['outputs'][label]={'source_step':name,'source_step_sha256':sha,'source_f3d':f3d,'source_f3d_sha256':sha,
                'verification_step':check,'verification_step_sha256':sha,'body_count':1 if label.startswith('left_') else 2}
            for file in [name,f3d]:export['source_sha256'][p.STAGE+'/'+file]=sha
            kernel['source_sha256'][p.STAGE+'/'+check]=sha
            kernel['outputs'][label]['verification_step_sha256']=sha
        kernel['source_sha256'].update(export['source_sha256'])
        records['native-review-export-all.json']=export
        # The old implementation reaches its writes then calls verify. This
        # incomplete saved record causes ValueError only after those writes.
        records['kc2_local_cover_manifest.json']={'status':'incomplete'}
        return records

if __name__=='__main__':unittest.main()
