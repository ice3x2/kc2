"""CON-ARCH-006 / OPS-ARCH-006 publication gates."""
import copy
import unittest
from unittest.mock import patch
from tools import publish_kc2_enclosure as p

class PublicationTests(unittest.TestCase):
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
        self.assertEqual(p.portable('.codex-tmp/enclosure-build/kc2_left_lower_housing.stl'),
                         'hardware/MODELS/kc2_left_lower_housing.stl')
        self.assertEqual(p.portable('.codex-tmp/enclosure-build/left-generation.json'),
                         'docs/reports/enclosed-housing-20260909/left-generation.json')
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
            if name.endswith('kc2_enclosure_manifest.json'):return forged
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
        for path in ['hardware/MODELS/PRINT-enclosed.md','hardware/MODELS/kc2_left_lower_housing.stl']:
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
        records['left-generation.json']['outputs']['left_lower']['meshes']={}
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
            records[side+'-generation.json']={'status':'generated_not_independently_verified','outputs':outputs,'source_sha256':{'tools/model.py':sha}}
            records[side+'-audit.json']={'status':'pass','errors':[],'source_sha256':{'tools/model.py':sha}}
        for name in p.REVIEW_NAMES:records[name]={'status':'pass','errors':[],'source_sha256':{'tools/model.py':sha}}
        native['script_sha256']=sha;records['native-all.json']=native;records['joined-plan.json']={'dx':1}
        # The old implementation reaches its writes then calls verify. This
        # incomplete saved record causes ValueError only after those writes.
        records['kc2_enclosure_manifest.json']={'status':'incomplete'}
        return records

if __name__=='__main__':unittest.main()
