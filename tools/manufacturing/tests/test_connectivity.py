"""Electrical membership regressions; these do not test routed copper continuity."""
import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import audit

ROOT = Path(__file__).resolve().parents[3]


class ConnectivityTests(unittest.TestCase):
    def test_all_four_schematic_pad_net_maps_match_boards(self):
        for name, (source, *_) in audit.BOARDS.items():
            with self.subTest(board=name):
                cad = ROOT / audit.BASE / "4_6_Schematics" / source
                self.assertEqual(audit.check_connectivity(
                    cad.with_suffix(".sch"), cad.with_suffix(".brd")), [])

    def test_reassigned_and_missing_pad_are_detected(self):
        expected = {("X1", "1"): "+5V", ("X1", "2"): "GND"}
        actual = {("X1", "1"): "GND", ("X2", "1"): "+5V"}
        findings = audit.compare_pad_nets(expected, actual)
        self.assertEqual(len(findings), 3)
        self.assertEqual({f["code"] for f in findings}, {"CAD_PAD_NET"})

    def test_conflicting_membership_is_rejected(self):
        mapping = {("X1", "1"): "GND"}
        with self.assertRaises(ValueError):
            audit.add_pad_net(mapping, ("X1", "1"), "+5V")

    def test_multi_pad_pin_and_supply_symbol(self):
        root = ET.fromstring('''<schematic><libraries><library name="lib">
          <devicesets><deviceset name="connector"><devices><device name="" package="pkg">
          <connects><connect gate="G" pin="S" pad="1 2"/></connects>
          </device></devices></deviceset><deviceset name="supply">
          <devices><device name=""/></devices></deviceset></devicesets>
          </library></libraries><parts>
          <part name="X1" library="lib" deviceset="connector" device=""/>
          <part name="P1" library="lib" deviceset="supply" device=""/></parts>
          <sheets><sheet><nets><net name="GND"><segment>
          <pinref part="X1" gate="G" pin="S"/>
          <pinref part="P1" gate="G" pin="GND"/>
          </segment></net></nets></sheet></sheets></schematic>''')
        self.assertEqual(audit.schematic_pad_nets(root),
                         {("X1", "1"): "GND", ("X1", "2"): "GND"})
        root.find('.//connect').set('pin', 'WRONG')
        with self.assertRaises(ValueError):
            audit.schematic_pad_nets(root)


if __name__ == "__main__":
    unittest.main()
