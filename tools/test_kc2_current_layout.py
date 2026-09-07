"""OPS-ARCH-006/007: one physical current tree and safe legacy aliases."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path


class CurrentLayoutTests(unittest.TestCase):
    def test_user_selected_canonical_paths(self):
        from tools.kc2_current_layout import ALIASES
        self.assertEqual('hardware/MODELS', ALIASES['hardware/case'])
        self.assertEqual('hardware/PCB/kc2_left', ALIASES['hardware/kicad/kc2_left'])
        self.assertEqual('hardware/GERBER', ALIASES['hardware/kicad/first_order/solid-floor-20260907-r4'])

    def test_setup_dry_run_idempotence_and_conflict(self):
        from tools.kc2_current_layout import ALIASES, setup
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            for target in ALIASES.values(): (root/target).mkdir(parents=True,exist_ok=True)
            self.assertEqual(len(ALIASES),len(setup(root,apply=False)))
            self.assertFalse((root/next(iter(ALIASES))).exists())
            setup(root,apply=True)
            for old,new in ALIASES.items(): self.assertEqual((root/old).resolve(),(root/new).resolve())
            self.assertEqual([],setup(root,apply=True))
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            for target in ALIASES.values(): (root/target).mkdir(parents=True,exist_ok=True)
            old=next(iter(ALIASES)); (root/old).mkdir(parents=True)
            with self.assertRaises(ValueError): setup(root,apply=True)
            self.assertTrue((root/old).is_dir())

    def test_missing_target_and_wrong_alias_are_rejected(self):
        from tools.kc2_current_layout import ALIASES, setup
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            with self.assertRaises(ValueError):setup(root,apply=True)
            for target in ALIASES.values():(root/target).mkdir(parents=True,exist_ok=True)
            setup(root,apply=True)
            # Another repository's alias target must never be silently accepted.
            canonical=root/next(iter(ALIASES.values()))
            renamed=canonical.with_name(canonical.name+'-moved')
            canonical.rename(renamed)
            with self.assertRaises(ValueError):setup(root,apply=True)

    def test_current_files_match_ordered_release_and_are_not_aliases(self):
        from tools.kc2_current_layout import ALIASES
        root=Path(__file__).resolve().parents[1]
        evidence=json.loads((root/'hardware/GERBER/review-evidence.json').read_text(encoding='utf-8'))
        for old,new in ALIASES.items():
            self.assertTrue((root/new).is_dir(),new)
            self.assertFalse((root/new).is_symlink(),new)
            self.assertEqual((root/old).resolve(),(root/new).resolve())
            # r5 intentionally replaces the r4 mechanical files, not ordered PCB.
            if new=='hardware/MODELS': continue
            for path,digest in evidence['bindings'].items():
                if path.startswith(old+'/'):
                    actual=root/new/path[len(old)+1:]
                    self.assertEqual(digest,hashlib.sha256(actual.read_bytes()).hexdigest(),path)

if __name__=='__main__':unittest.main()
