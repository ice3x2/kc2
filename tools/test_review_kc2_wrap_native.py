"""CON-ARCH-006 all ten native jobs are mandatory even with staged audits."""
import unittest
from tools.kc2_wrap_native import jobs
from tools.review_kc2_wrap_native import review_status, reusable_native


class NativeReviewScopeTests(unittest.TestCase):
    def test_partial_never_claims_complete_native_review(self):
        labels = list(jobs())
        self.assertEqual(review_status(labels, []), 'pass')
        self.assertEqual(review_status(labels[:-1], []), 'partial')
        self.assertEqual(review_status(labels, ['wrong geometry']), 'failed')

    def test_cached_readback_requires_identical_sources_and_body_count(self):
        sources = {'source.step':'a', 'readback.step':'b', 'audit.py':'c'}
        record = dict(status='pass', source_sha256=sources,
                      row=dict(errors=[], parts=[dict(errors=[])]))
        self.assertTrue(reusable_native(record, sources, 1))
        self.assertFalse(reusable_native(record, {**sources,'readback.step':'new'}, 1))
        self.assertFalse(reusable_native(record, sources, 2))
        self.assertFalse(reusable_native({**record,'status':'failed'}, sources, 1))


if __name__ == '__main__':
    unittest.main()
