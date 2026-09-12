"""CON-ARCH-006/OPS-ARCH-006 complete, portable, fail-closed publication."""
import unittest
from tools.publish_kc2_filled_plates import output_names,report_names,portable,require_pass,section_errors


class FilledPublicationTests(unittest.TestCase):
    def test_exact_three_family_output_inventory(self):
        names=output_names()
        self.assertEqual(len(names),21)
        self.assertEqual(sum(n.endswith('.stl') for n in names),9)
        self.assertTrue(all(any('_'+k+'_' in n for k in ['mx','choc_v1','deep_sea']) for n in names))

    def test_all_six_generation_step_and_native_audits_required(self):
        names=report_names()
        for side in ['left','right']:
            for kind in ['mx','choc_v1','deep_sea']:
                self.assertIn(f'{side}-{kind}.json',names)
                self.assertIn(f'{side}-{kind}-sectional-progress.json',names)
                self.assertIn(f'{side}-{kind}-native-review.json',names)

    def test_readback_evidence_is_not_an_extra_print_model(self):
        name='kc2_left_mx_upper_housing.native-readback.step'
        self.assertIn('/solid-filled-plates-20260913/',portable('.codex-tmp/solid-filled-plates/'+name))
        self.assertEqual(portable('.codex-tmp/solid-filled-plates/kc2_left_choc_v1_upper_housing.stl'),
                         'hardware/MODELS/kc2_left_choc_v1_upper_housing.stl')

    def test_unmapped_or_unsafe_paths_rejected(self):
        for path in ['../outside','C:/outside','.codex-tmp/unknown.py','.codex-tmp/solid-filled-plates/../../outside','/outside','a\\b']:
            with self.subTest(path=path),self.assertRaises(ValueError):portable(path)

    def test_pass_label_cannot_hide_errors_or_physical_claim(self):
        require_pass(dict(status='pass',errors=[],physical_qualified=False))
        for value in [dict(status='running'),dict(status='pass',errors=['hole filled']),dict(status='pass',physical_qualified=True)]:
            with self.assertRaises(ValueError):require_pass(value)

    def test_missing_sections_wrong_levels_and_excess_material_rejected(self):
        layers=[dict(z0=4.1,z1=4.4),dict(z0=4.4,z1=5.3)]
        good=dict(status='pass',errors=[],levels_mm=[4.1,4.4,5.3],
            sections=[dict(z_mm=4.25,missing_mm2=0,extra_mm2=0),dict(z_mm=4.85,missing_mm2=0,extra_mm2=0)],volume_error_mm3=0)
        self.assertEqual(section_errors(good,layers),[])
        for key,val in [('sections',[]),('levels_mm',[4.1,5.3]),('volume_error_mm3',float('nan'))]:
            self.assertTrue(section_errors({**good,key:val},layers))
        bad={**good,'sections':[dict(z_mm=4.25,missing_mm2=0,extra_mm2=.1),good['sections'][1]]}
        self.assertTrue(section_errors(bad,layers))


if __name__=='__main__':unittest.main()
