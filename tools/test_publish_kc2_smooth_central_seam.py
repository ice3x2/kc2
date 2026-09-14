"""CON-ARCH-006 publication refuses missing cavity and stale native evidence."""
import unittest
from tools.publish_kc2_smooth_central_seam import validate_records


class PublicationTests(unittest.TestCase):
    def test_no_review_cannot_publish(self):
        with self.assertRaises(ValueError): validate_records({}, {}, {})

    def test_failed_section_cannot_publish(self):
        with self.assertRaises(ValueError):
            validate_records({'status':'failed','errors':['STL still has guide cavity']},
                             {'status':'pass','errors':[]}, {'status':'pass','errors':[]})

    def test_incomplete_native_cannot_publish(self):
        with self.assertRaises(ValueError):
            validate_records({'status':'pass','errors':[],'rows':{s:{} for s in
                ('left:normal','left:magnetic','right:normal','right:magnetic')}},
                {'status':'pass','errors':[],'outputs':{}}, {'status':'pass','errors':[],'rows':{}})
