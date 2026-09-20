"""CON-ARCH-006: all changed upper and lower native jobs are mandatory."""
import unittest
from tools.kc2_wrap_native import jobs, select_jobs


class NativeJobTests(unittest.TestCase):
    def test_partial_export_is_explicit_and_cannot_name_unknown_jobs(self):
        self.assertEqual(select_jobs(['left:normal', 'right:magnetic']), ['left:normal', 'right:magnetic'])
        self.assertEqual(set(select_jobs(None)), set(jobs()))
        with self.assertRaises(ValueError):
            select_jobs(['unknown'])
        with self.assertRaises(ValueError):
            select_jobs(['left:normal', 'left:normal'])

    def test_all_ten_changed_models_are_named(self):
        expected = {s+':'+k for s in ('left', 'right') for k in ('normal', 'magnetic', 'mx', 'choc_v1', 'deep_sea')}
        self.assertEqual(set(jobs()), expected)
        self.assertEqual(len({j['folder'] for j in jobs().values()}), 10)
        for label, j in jobs().items():
            self.assertEqual(j['body_count'], 1 if label.startswith('left:') else 2)
            self.assertTrue(j['step'].endswith('.step'))


if __name__ == '__main__':
    unittest.main()
