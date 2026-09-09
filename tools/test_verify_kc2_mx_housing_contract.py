"""CON-ARCH-006 nominal housing contracts must fail closed under mutations."""
import copy
import json
import unittest
from pathlib import Path

from tools import verify_kc2_mx_housing_contract as check
from tools.historical_housing_test_fixture import historical_json, historical_artifact_root


class MXHousingContractTests(unittest.TestCase):
    """Historical r5 contract mutations, not current enclosed-CAD approval."""
    def test_canonical_hardware_model_paths_preserve_exact_binding(self):
        lower,upper=copy.deepcopy(self.lower),copy.deepcopy(self.upper)
        def relocate(value):
            if isinstance(value,dict):
                for key,item in value.items():
                    if isinstance(item,str) and item.startswith('hardware/case/'):
                        value[key]='hardware/MODELS/'+item[len('hardware/case/'):]
                    else:relocate(item)
            elif isinstance(value,list):
                for item in value:relocate(item)
        relocate(lower);relocate(upper)
        self.assertEqual([],self.report(lower=lower,upper=upper)['errors'])

    def test_closed_floor_missing_thin_and_unknown_projection_fail_closed(self):
        lower=copy.deepcopy(self.lower)
        lower.pop('closed_floor',None)
        self.assertTrue(any('closed_floor' in e for e in self.report(lower=lower)['errors']))
        for field,value in [('thickness_mm',.6),('top_z_mm',0),('maximum_component_projection_mm',0),
                            ('physical_qualification',True),('continuous_per_part',False)]:
            lower=copy.deepcopy(self.lower)
            lower.setdefault('closed_floor',{})[field]=value
            self.assertTrue(any('closed_floor' in e for e in self.report(lower=lower)['errors']),field)

    def test_actual_lower_mesh_old_bottom_is_rejected(self):
        artifacts=copy.deepcopy(self.artifacts)
        path='hardware/case/kc2_left_lower_housing.stl'
        artifacts[path]['desk_contact_z_mm']=-1.
        self.assertTrue(any('closed_floor actual STL.desk_contact_z_mm' in e
                            for e in self.report(artifacts=artifacts)['errors']))

    @classmethod
    def setUpClass(cls):
        cls.lower=historical_json('kc2_housing_manifest.json')
        cls.upper=historical_json('kc2_mx_upper_housing_manifest.json')
        with historical_artifact_root(check._paths()) as fixture_root:
            cls.artifacts=check.collect_artifacts(fixture_root)
        # Rebinding is optional in regenerated canonical manifests. Keep its
        # validation exercised through an explicit synthetic fixture either way.
        cls.lower.setdefault('source_rebinding_evidence',{
            side:dict(old_source_sha256='1'*64,
                new_source_sha256=cls.lower['outputs'][side]['source_board_sha256'],
                identical_full_extraction_sha256='2'*64) for side in ('left','right')})
        cls.signatures={s:r['identical_full_extraction_sha256'] for s,r in cls.lower['source_rebinding_evidence'].items()}
        # Synthetic revised contract fixture: not evidence that old canonical CAD passes.
        cls.lower['generator_sha256']=cls.artifacts[check.LOWER_GENERATOR]['sha256']
        cls.upper['generator_sha256']=cls.artifacts[check.UPPER_GENERATOR]['sha256']
        cls.upper['lower_generator_sha256']=cls.artifacts[check.LOWER_GENERATOR]['sha256']
        cls.upper['stack'].update(head_pocket_diameter_mm=3.4,head_pocket_depth_mm=1.5,
            head_bearing_z_mm=7.8,head_top_z_mm=9.,upper_collar_diameter_mm=4.6,
            collar_bottom_z_mm=5.3,pcb_landing_diameter_mm=3.,nominal_collar_wall_mm=.6,
            nominal_under_head_to_receiver_entry_mm=5.3,
            collar_strength_qualification='engineering_geometry_only_not_strength_pass')
        for side,count in [('left',8),('right',9)]:
            cls.upper['outputs'][side]['recess_geometry_checks']=[dict(ref=f'MH{i+1}',
                head_intersection_mm3=0.,collar_slice_mm3=3.141592653589793,
                outside_landing_mm3=0.,collar_contained_in_one_part=True) for i in range(count)]

    def report(self, lower=None, upper=None, artifacts=None, signatures=None):
        return check.validate_manifests(self.lower if lower is None else lower,self.upper if upper is None else upper,
            artifacts=self.artifacts if artifacts is None else artifacts,
            rebinding_signatures=self.signatures if signatures is None else signatures)

    def test_revised_fixture_is_digital_only(self):
        report=self.report()
        self.assertEqual(report['errors'],[])
        self.assertTrue(report['digital_valid'])
        self.assertFalse(report['order_ready'])
        self.assertFalse(report['print_ready'])
        self.assertTrue(report['qualification_blockers'])
        self.assertTrue(report['closed_floor']['digital_valid'])
        self.assertEqual(report['closed_floor']['errors'],[])
        self.assertEqual(report['closed_floor']['printable_part_count'],3)
        self.assertEqual(report['closed_floor']['bonding_pad_count'],12)
        self.assertEqual(report['closed_floor']['floor_bottom_z_mm'],-2.2)

    def test_recess_mutations_fail_closed(self):
        for field,value in [('head_pocket_diameter_mm',3.),('head_pocket_depth_mm',1.),
                ('head_bearing_z_mm',8.3),('head_top_z_mm',9.5),
                ('upper_collar_diameter_mm',3.),('collar_bottom_z_mm',4.1),
                ('pcb_landing_diameter_mm',4.6),('nominal_collar_wall_mm',.2)]:
            upper=copy.deepcopy(self.upper)
            upper['stack'][field]=value
            self.assertTrue(any(field in e for e in self.report(upper=upper)['errors']),field)
        for field,value in [('head_intersection_mm3',.01),('collar_slice_mm3',0.),
                ('outside_landing_mm3',.01),('collar_contained_in_one_part',False),
                ('collar_slice_mm3',float('nan'))]:
            upper=copy.deepcopy(self.upper)
            upper['outputs']['right']['recess_geometry_checks'][7][field]=value
            self.assertTrue(any(field in e for e in self.report(upper=upper)['errors']),field)
        upper=copy.deepcopy(self.upper)
        upper['outputs']['right']['recess_geometry_checks'].pop()
        self.assertTrue(self.report(upper=upper)['errors'])

    def test_missing_malformed_and_false_qualification_rejected(self):
        changes=[lambda l,u:l.pop('mx_receptacle_stack'),
                 lambda l,u:l['mx_receptacle_stack'].__setitem__('nominal_barrel_below_pcb_mm',1.36),
                 lambda l,u:l['mx_receptacle_stack'].__setitem__('qualified_minimum_desk_clearance_mm',.5),
                 lambda l,u:l['mx_receptacle_stack'].__setitem__('qualified',True),
                 lambda l,u:l['outputs']['left']['component_cutouts']['mx_pins_pads_fillets']['selected_receptacle'].__setitem__('nominal_total_length_mm',4),
                 lambda l,u:u.__setitem__('print_ready',True),
                 lambda l,u:u['stack'].__setitem__('plate_top_z_mm',9.4),
                 lambda l,u:u['stack'].__setitem__('qualified_long_screw_length_mm',9),
                 lambda l,u:u['outputs']['left']['printable_parts'][0].__setitem__('print_ready',True),
                 lambda l,u:u['stack'].__setitem__('pending',[]),
                 lambda l,u:u['outputs']['right'].__setitem__('hard_stop_count',8),
                 lambda l,u:u['outputs']['right']['split_joint'].__setitem__('clamp_count_by_part',[1,8]),
                 lambda l,u:u['outputs']['left'].__setitem__('step','../../other.step'),
                 lambda l,u:u['outputs']['left']['printable_parts'][0].__setitem__('volume_mm3',float('nan')),
                 lambda l,u:u['outputs']['left']['printable_parts'][0].__setitem__('bounds_xyz_mm',[0]*6)]
        for mutate in changes:
            lower,upper=copy.deepcopy(self.lower),copy.deepcopy(self.upper)
            mutate(lower,upper)
            with self.subTest(mutate=mutate): self.assertTrue(self.report(lower,upper)['errors'])

    def test_rebind_optional_but_if_present_requires_fresh_geometry(self):
        lower=copy.deepcopy(self.lower)
        lower.pop('source_rebinding_evidence')
        self.assertEqual(self.report(lower=lower)['errors'],[])
        for change in ('missing_side','bad_hash','stale_geometry'):
            lower=copy.deepcopy(self.lower)
            if change=='missing_side': lower['source_rebinding_evidence'].pop('left')
            elif change=='bad_hash': lower['source_rebinding_evidence']['left']['new_source_sha256']='0'*64
            else: lower['source_rebinding_evidence']['left']['identical_full_extraction_sha256']='0'*64
            self.assertTrue(self.report(lower=lower)['errors'])

    def test_actual_artifact_corruption_is_not_a_qualification_blocker_only(self):
        for path in ('hardware/case/kc2_left_mx_upper_housing.step','hardware/case/kc2_left_mx_upper_housing.stl',
                     'hardware/kicad/kc2_left/kc2_left.kicad_pcb','tools/generate_kc2_mx_upper_housings.py'):
            artifacts=copy.deepcopy(self.artifacts)
            artifacts[path]['sha256']='0'*64
            self.assertTrue(self.report(artifacts=artifacts)['errors'])
        for key,value in [('watertight',False),('shell_count',2),('volume_mm3',0),
                          ('volume_mm3',float('nan')),('bounds_xyz_mm',[float('nan')]*6)]:
            artifacts=copy.deepcopy(self.artifacts)
            artifacts['hardware/case/kc2_left_mx_upper_housing.stl'][key]=value
            self.assertTrue(self.report(artifacts=artifacts)['errors'])
        artifacts=copy.deepcopy(self.artifacts)
        artifacts['hardware/case/kc2_right_mx_upper_housing.step']['solid_count']=1
        self.assertTrue(self.report(artifacts=artifacts)['errors'])

    def test_bad_types_never_crash(self):
        for value in (None,[],True,4,'bad'):
            self.assertTrue(self.report(lower=value if value is not None else [])['errors'])
            upper=copy.deepcopy(self.upper)
            upper['outputs']['right']['printable_parts']=value
            self.assertTrue(self.report(upper=upper)['errors'])


if __name__=='__main__': unittest.main()
