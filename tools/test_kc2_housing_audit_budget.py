"""CON-ARCH-006/OPS-ARCH-007: full-volume housing checks must not time out at5min."""
import ast
from pathlib import Path
import unittest

class HousingAuditBudgetTests(unittest.TestCase):
    def test_artifact_suite_allows_full_volume_housing_audit(self):
        path=Path(__file__).with_name('verify_kc2_x3_v2.py')
        tree=ast.parse(path.read_text(encoding='utf8'))
        matches=[]
        for node in ast.walk(tree):
            if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and node.func.attr=='run':
                if any(isinstance(item,ast.Name) and item.id=='housing_code' for item in ast.walk(node)):
                    matches.extend(ast.literal_eval(k.value) for k in node.keywords if k.arg=='timeout')
        self.assertEqual([1800],matches)

if __name__=='__main__':unittest.main()
