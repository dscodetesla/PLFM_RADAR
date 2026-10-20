"""The hardware clock contract must reject a fictitious FPGA pin reassignment."""
import importlib.util
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location("audit", ROOT / "tools/manufacturing/audit.py")
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)


class ClockContractTests(unittest.TestCase):
    def test_current_board_mismatch_is_reported(self):
        report = audit.audit_fpga_clocks(ROOT)
        self.assertEqual(len(report["findings"]), 1)
        detail = report["findings"][0]["detail"]
        self.assertEqual(detail["port"], "clk_120m_dac")
        self.assertEqual(detail["board_pads"], ["C13"])
        self.assertEqual(detail["xdc_pins"], ["D13"])

    def test_missing_duplicate_and_wrong_assignment_fail(self):
        board = ET.fromstring('''<board><signals><signal name="CLK">
            <contactref element="U42" pad="C13"/></signal></signals></board>''')
        contract = {"clock": "CLK"}
        good = 'set_property PACKAGE_PIN C13 [get_ports {clock}]'
        self.assertEqual(audit.check_clock_pins(board, good, contract), [])
        for invalid in ("", good.replace("C13", "D13"), good + "\n" + good):
            with self.subTest(xdc=invalid):
                self.assertTrue(audit.check_clock_pins(board, invalid, contract))

    def test_alternative_xdc_overrides_cannot_be_silently_ignored(self):
        board = ET.fromstring('''<board><signals><signal name="CLK">
            <contactref element="U42" pad="C13"/></signal></signals></board>''')
        good = 'set_property PACKAGE_PIN C13 [get_ports {clock}]'
        for override in ('set_property PACKAGE_PIN D13 [get_ports clock]',
                         'set_property PACKAGE_PIN D13 [get_ports {clock}] ;# revised pin'):
            with self.subTest(override=override):
                self.assertTrue(audit.check_clock_pins(board, good + '\n' + override,
                                                      {"clock": "CLK"}))

    def test_unsupported_pin_command_fails_closed(self):
        board = ET.fromstring('<board><signals/></board>')
        with self.assertRaisesRegex(ValueError, 'Unsupported PACKAGE_PIN'):
            audit.check_clock_pins(board,
                'set_property -dict {PACKAGE_PIN D13 IOSTANDARD LVCMOS33} [get_ports {clock}]',
                {"clock": "CLK"})


if __name__ == "__main__":
    unittest.main()
