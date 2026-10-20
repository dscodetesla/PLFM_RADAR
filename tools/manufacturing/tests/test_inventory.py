"""Regression against actual manufacturing inputs; does not certify component fit."""
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location("audit", ROOT / "tools/manufacturing/audit.py")
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)

class InventoryRegression(unittest.TestCase):
    def test_four_board_bom_and_dnp_integrity(self):
        for board, spec in audit.BOARDS.items():
            with self.subTest(board=board):
                report = audit.audit_board(ROOT, *spec)
                inventory = [f for f in report["findings"]
                             if f["code"].startswith(("BOM_", "CPL_"))]
                self.assertEqual(inventory, [])

if __name__ == "__main__":
    unittest.main()
