"""OPS-ARCH-006 release source hashes must survive Git line-ending handling."""
from pathlib import Path
import subprocess,unittest

class GitBytesTests(unittest.TestCase):
    def test_all_added_executable_sources_are_raw_bytes(self):
        from tools.kc2_registered_release_gate import BASELINE
        root=Path(__file__).resolve().parents[1]
        changed=subprocess.check_output(['git','diff','--name-only',BASELINE,'--','tools'],cwd=root,text=True).splitlines()
        untracked=subprocess.check_output(['git','ls-files','--others','--exclude-standard','tools'],cwd=root,text=True).splitlines()
        paths=sorted({p for p in changed+untracked if p.endswith('.py') and (root/p).exists()})
        self.assertTrue(paths)
        output=subprocess.check_output(['git','check-attr','text','--',*paths],cwd=root,text=True).splitlines()
        self.assertEqual(len(output),len(paths))
        self.assertTrue(all(line.endswith(': text: unset') for line in output),'\n'.join(output))
    def test_new_source_and_evidence_are_raw_bytes(self):
        root=Path(__file__).resolve().parents[1]
        paths=['tools/kc2_actual_sections.py','tools/test_kc2_actual_sections.py','tools/review_kc2_actual_envelopes.py','tools/kc2_registered_upper.py',
            'tools/kc2_central_flexure.py','tools/kc2_perimeter_wall.py','tools/kc2_profile_split.py',
            'tools/kc2_lower_split_extension.py','tools/kc2_joined_sweep.py','tools/stage_kc2_ab_relief.py',
            'tools/kc2_wall_registration.py','tools/kc2_split_fit_relief.py',
            'tools/fusion/KC2RegisteredHousingToF3D/KC2RegisteredHousingToF3D.py',
            'docs/reports/registered-housing-fit-20260913/evidence/future-native.step']
        text=subprocess.check_output(['git','check-attr','text','--',*paths],cwd=root,text=True)
        self.assertEqual(len(text.splitlines()),len(paths))
        self.assertTrue(all(line.endswith(': text: unset') for line in text.splitlines()),text)

if __name__=='__main__':unittest.main()
