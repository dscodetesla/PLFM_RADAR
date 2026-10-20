"""Manufacturing checks exercise real CAD/XLSX readers and adversarial input."""

import importlib.util
import tempfile
import unittest
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / "audit.py"
SPEC = importlib.util.spec_from_file_location("manufacturing_audit", MODULE)
audit = importlib.util.module_from_spec(SPEC) if MODULE.exists() else None
if audit:
    SPEC.loader.exec_module(audit)


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(audit, "Manufacturing audit is missing")

    def test_duplicate_does_not_cover_missing_reference(self):
        findings = audit.check_bom(
            [{"Qty": 2, "Parts": "C1, C1"}], {"C1", "C2"}
        )
        self.assertEqual(
            {f["code"] for f in findings}, {"BOM_DUPLICATE", "BOM_MISSING"}
        )

    def test_quantity_and_empty_designators_fail(self):
        findings = audit.check_bom([{"Qty": 11, "Parts": "J1, J2"}], {"J1", "J2"})
        self.assertIn("BOM_QUANTITY", {f["code"] for f in findings})
        self.assertTrue(audit.check_bom([{"Qty": 0, "Parts": ""}], {"J1"}))

    def test_dnp_never_enters_placement(self):
        bom = [{"Qty": 1, "Parts": "SJ1", "REMARKS": "[DNP不要贴];"}]
        findings = audit.check_placement(bom, [{"Designator": "SJ1"}], {"SJ1"})
        self.assertIn("CPL_DNP", {f["code"] for f in findings})

    def test_placement_duplicate_and_extra_are_rejected(self):
        findings = audit.check_placement(
            [], [{"Designator": "X1"}, {"Designator": "X1"}], set()
        )
        self.assertEqual(
            {f["code"] for f in findings}, {"CPL_DUPLICATE", "CPL_EXTRA"}
        )

    def test_valid_inventory_is_not_a_release_approval(self):
        self.assertEqual(audit.check_bom([{"Qty": 1, "Parts": "R1"}], {"R1"}), [])
        self.assertEqual(audit.READINESS, "NOT_FOR_MANUFACTURE")

    def test_deleted_fitted_and_empty_placement_are_rejected(self):
        findings = audit.check_placement([], [], {"J1"}, required_refs={"J1"})
        self.assertIn("CPL_MISSING", {f["code"] for f in findings})
        self.assertIn("CPL_EMPTY", {f["code"] for f in findings})

    def test_cpl_schema_and_finite_values(self):
        row = {"Designator": "J1", "Mid X (mm)": "1.2", "Mid Y (mm)": "2.3",
               "Layer": "Top", "Rotation": 90}
        self.assertEqual(audit.check_cpl_values([row]), [])
        for field, value in (("Mid X (mm)", "NaN"), ("Mid Y (mm)", "bad"),
                             ("Rotation", float("inf")), ("Layer", "unknown")):
            with self.subTest(field=field):
                bad = {**row, field: value}
                self.assertTrue(audit.check_cpl_values([bad]))
        del row["Mid X (mm)"]
        self.assertTrue(audit.check_cpl_values([row]))

    def test_only_packaged_schematic_parts_count(self):
        xml = '''<eagle><drawing><schematic><libraries><library name="L">
        <devicesets><deviceset name="R"><devices><device name="" package="P"/>
        </devices></deviceset><deviceset name="GND"><devices><device name=""/>
        </devices></deviceset></devicesets></library></libraries><parts>
        <part name="R1" library="L" deviceset="R" device=""/>
        <part name="GND1" library="L" deviceset="GND" device=""/>
        </parts></schematic></drawing></eagle>'''
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "fixture.sch"
            path.write_text(xml)
            self.assertEqual(set(audit.schematic_parts(path)), {"R1"})
            self.assertIsNone(audit.schematic_parts(path)["R1"]["value"])

    def test_missing_workbook_raises_instead_of_empty_success(self):
        with self.assertRaises(FileNotFoundError):
            audit.read_xlsx(Path("/nonexistent/production.xlsx"))


if __name__ == "__main__":
    unittest.main()
