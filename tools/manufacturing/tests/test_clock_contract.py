"""The hardware clock contract must report unmodified PCB vs clean MRCC XDC mismatches."""
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
        by_port = {item["detail"]["port"]: item["detail"] for item in report["findings"]}
        self.assertEqual(set(by_port.keys()), {"clk_120m_dac", "ft_clkout"})
        self.assertEqual(by_port["clk_120m_dac"]["board_pads"], ["C13"])
        self.assertEqual(by_port["clk_120m_dac"]["xdc_pins"], ["D13"])
        self.assertEqual(by_port["ft_clkout"]["board_pads"], ["C4"])
        self.assertEqual(by_port["ft_clkout"]["xdc_pins"], ["D4"])

    def test_missing_duplicate_and_wrong_assignment_fail(self):
        board = ET.fromstring(
            '<board><signals><signal name="CLK">'
            '<contactref element="U42" pad="C13"/></signal></signals></board>'
        )
        contract = {"clock": "CLK"}
        good = "set_property PACKAGE_PIN C13 [get_ports {clock}]"
        self.assertEqual(audit.check_clock_pins(board, good, contract), [])
        for invalid in ("", good.replace("C13", "D13"), f"{good}\n{good}"):
            with self.subTest(xdc=invalid):
                self.assertTrue(audit.check_clock_pins(board, invalid, contract))

    def test_alternative_xdc_overrides_cannot_be_silently_ignored(self):
        board = ET.fromstring(
            "\n".join(
                (
                    '<board><signals><signal name="CLK">',
                    '<contactref element="U42" pad="C13"/></signal></signals></board>',
                )
            )
        )
        good = "set_property PACKAGE_PIN C13 [get_ports {clock}]"
        overrides = (
            "set_property PACKAGE_PIN D13 [get_ports clock]",
            "set_property PACKAGE_PIN D13 [get_ports {clock}] ;# revised pin",
        )
        for override in overrides:
            with self.subTest(override=override):
                self.assertTrue(
                    audit.check_clock_pins(board, f"{good}\n{override}", {"clock": "CLK"})
                )

    def test_unsupported_pin_command_fails_closed(self):
        board = ET.fromstring("<board><signals/></board>")
        bad_cmd = "set_property -dict {PACKAGE_PIN D13 IOSTANDARD LVCMOS33} [get_ports {clock}]"
        with self.assertRaisesRegex(ValueError, "Unsupported PACKAGE_PIN"):
            audit.check_clock_pins(board, bad_cmd, {"clock": "CLK"})


if __name__ == "__main__":
    unittest.main()
