"""Unit tests for 50T FPGA XDC/TCL fixes, port parity, and legacy C13/C4 PCB conflicts."""
from __future__ import annotations

import re
import tempfile
import textwrap
import unittest
from pathlib import Path

from tools.manufacturing import check_fpga_clocks


def _tcl_glob_matches(port: str, pattern: str) -> bool:
    """Match a Vivado XDC port wildcard pattern (where [*] matches vector indices)."""
    regex = "^" + re.escape(pattern).replace(r"\*", ".*") + "$"
    return re.match(regex, port) is not None


def _parse_verilog_top_scalar_ports(verilog_path: Path) -> set[str]:
    """Expand all scalar and vector top-level ports of radar_system_top_50t.v."""
    text = verilog_path.read_text(encoding="utf-8")
    m = re.search(r"module\s+radar_system_top_50t\s*\((.*?)\)\s*;", text, re.DOTALL)
    if not m:
        raise ValueError("Could not locate module radar_system_top_50t header")
    header = m.group(1)
    ports: set[str] = set()
    for raw_line in header.splitlines():
        line = raw_line.split("//", 1)[0].strip().rstrip(",")
        if not line:
            continue
        m_decl = re.match(
            r"^(?:input|output|inout)\s+wire\s*(?:\[(\d+):(\d+)\])?\s+(.+)$",
            line,
        )
        if not m_decl:
            continue
        msb_s, lsb_s, names_part = m_decl.group(1), m_decl.group(2), m_decl.group(3)
        names = [n.strip().rstrip(",") for n in names_part.split(",") if n.strip()]
        for name in names:
            if msb_s is not None and lsb_s is not None:
                msb, lsb = int(msb_s), int(lsb_s)
                step = 1 if msb >= lsb else -1
                for idx in range(lsb, msb + 1 if step == 1 else msb - 1, step):
                    ports.add(f"{name}[{idx}]")
            else:
                ports.add(name)
    return ports


class TestFpgaXdcAndClockConstraints(unittest.TestCase):
    """Verify 6 FPGA XDC/TCL fixes, RTL port parity, and legacy C13/C4 conflict detection."""

    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[3]
        self.state_path = self.repo_root / "docs" / "project-context" / "state.json"
        self.fpga_dir = self.repo_root / "9_Firmware" / "9_2_FPGA"
        self.xdc_path = self.fpga_dir / "constraints" / "xc7a50t_ftg256.xdc"
        self.mmcm_xdc_path = self.fpga_dir / "constraints" / "adc_clk_mmcm.xdc"
        self.build_tcl_path = self.fpga_dir / "scripts" / "50t" / "build_50t.tcl"
        self.pre_gate_tcl_path = self.fpga_dir / "scripts" / "50t" / "pre_bitstream_gate.tcl"
        self.top_v_path = self.fpga_dir / "radar_system_top_50t.v"

    def test_01_production_50t_xdc_and_tcl_pass_zero_waiver_audit(self) -> None:
        res = check_fpga_clocks.audit_fpga_xdc_and_tcl(
            xdc_path=self.xdc_path,
            mmcm_xdc_path=self.mmcm_xdc_path,
            build_tcl_path=self.build_tcl_path,
        )
        self.assertTrue(res["files_present"])
        self.assertEqual(res["violations"], [])
        self.assertTrue(res["xdc_gate_valid"])

    def test_02_bank14_vcco33_lvds_diff_term_false_and_t5_lvcmos33(self) -> None:
        res = check_fpga_clocks.audit_fpga_xdc_and_tcl(
            xdc_path=self.xdc_path,
            mmcm_xdc_path=self.mmcm_xdc_path,
            build_tcl_path=self.build_tcl_path,
        )
        b14 = res["bank14_xdc"]
        self.assertEqual(b14["adc_pwdn_pin"], "T5")
        self.assertEqual(b14["adc_pwdn_iostandard"], "LVCMOS33")
        self.assertEqual(b14["adc_dco_diff_term"], "FALSE")
        self.assertEqual(b14["adc_d_diff_term"], "FALSE")
        xdc_text = self.xdc_path.read_text(encoding="utf-8")
        self.assertNotIn("DIFF_TERM TRUE", xdc_text)
        self.assertNotIn("LVCMOS25", xdc_text)

    def test_03_mrcc_p_side_d13_and_d4_without_clock_dedicated_route_false(self) -> None:
        res = check_fpga_clocks.audit_fpga_xdc_and_tcl(
            xdc_path=self.xdc_path,
            mmcm_xdc_path=self.mmcm_xdc_path,
            build_tcl_path=self.build_tcl_path,
        )
        clks = res["clock_pins_xdc"]
        self.assertEqual(clks["clk_100m"], "E12")
        self.assertEqual(clks["clk_120m_dac"], "D13")
        self.assertEqual(clks["adc_dco_p"], "N14")
        self.assertEqual(clks["ft_clkout"], "D4")
        for p in (self.xdc_path, self.build_tcl_path):
            active = "\n".join(
                check_fpga_clocks._strip_tcl_comments_and_join(p.read_text(encoding="utf-8"))
            )
            self.assertNotIn("CLOCK_DEDICATED_ROUTE", active)

    def test_04_hierarchy_paths_and_ft2232h_3p5ns_output_delays(self) -> None:
        res = check_fpga_clocks.audit_fpga_xdc_and_tcl(
            xdc_path=self.xdc_path,
            mmcm_xdc_path=self.mmcm_xdc_path,
            build_tcl_path=self.build_tcl_path,
        )
        delays = res["ft2232h_output_delay_max_ns"]
        for port in ("ft_data[*]", "ft_rd_n", "ft_wr_n", "ft_oe_n", "ft_siwu"):
            self.assertAlmostEqual(delays[port], 3.500, places=6)

        mmcm_active = "\n".join(
            check_fpga_clocks._strip_tcl_comments_and_join(
                self.mmcm_xdc_path.read_text(encoding="utf-8")
            )
        )
        self.assertNotIn("ft601_clk_in", mmcm_active)
        self.assertIn("[get_clocks ft_clkout]", mmcm_active)
        self.assertIn("u_core/rx_inst/adc/mmcm_inst/mmcm_adc_400m/LOCKED", mmcm_active)

        xdc_active = "\n".join(
            check_fpga_clocks._strip_tcl_comments_and_join(
                self.xdc_path.read_text(encoding="utf-8")
            )
        )
        self.assertIn("u_core/reset_sync*_reg[*]", xdc_active)

    def test_05_build_50t_and_pre_bitstream_gate_enforce_production_gate(self) -> None:
        self.assertTrue(self.pre_gate_tcl_path.exists())
        tcl_active = "\n".join(
            check_fpga_clocks._strip_tcl_comments_and_join(
                self.build_tcl_path.read_text(encoding="utf-8")
            )
        )
        for code in ("BIVC-1", "NSTD-1", "UCIO-1", "PLIO-9"):
            self.assertNotIn(code, tcl_active)
        self.assertIn("production_gate.tcl", tcl_active)
        self.assertIn("plfm_require_production_checks", tcl_active)
        self.assertLess(
            tcl_active.rfind("plfm_require_production_checks"),
            tcl_active.find("write_bitstream"),
        )

    def test_06_top_50t_ports_have_complete_unique_pin_and_iostandard_coverage(self) -> None:
        rtl_ports = _parse_verilog_top_scalar_ports(self.top_v_path)
        self.assertEqual(len(rtl_ports), 82)

        xdc_lines = check_fpga_clocks._strip_tcl_comments_and_join(
            self.xdc_path.read_text(encoding="utf-8")
        )
        pin_by_port: dict[str, str] = {}
        iostd_patterns: list[tuple[str, str]] = []
        for line in xdc_lines:
            m_prop = re.match(r"^set_property\s+(\S+)\s+(\S+)\s+(.+)$", line)
            if not m_prop:
                continue
            prop, val = m_prop.group(1), m_prop.group(2).strip("{}")
            target = check_fpga_clocks._extract_target(m_prop.group(3))
            if not target:
                continue
            if prop == "PACKAGE_PIN":
                self.assertNotIn(target, pin_by_port, f"Duplicate PACKAGE_PIN on port {target}")
                pin_by_port[target] = val
            elif prop == "IOSTANDARD":
                iostd_patterns.append((target, val))

        self.assertEqual(set(pin_by_port.keys()), rtl_ports)
        self.assertEqual(len(set(pin_by_port.values())), len(rtl_ports))

        for port in sorted(rtl_ports):
            matched_stds = [val for pat, val in iostd_patterns if _tcl_glob_matches(port, pat)]
            self.assertTrue(matched_stds, f"Port {port} missing IOSTANDARD in XDC")

    def test_07_unmodified_pcb_c13_c4_conflict_detected_against_new_xdc(self) -> None:
        res = check_fpga_clocks.audit_fpga_xdc_and_tcl(
            xdc_path=self.xdc_path,
            mmcm_xdc_path=self.mmcm_xdc_path,
            build_tcl_path=self.build_tcl_path,
            pcb_clock_pins={"clk_120m_dac": "C13", "ft_clkout": "C4"},
        )
        self.assertTrue(res["xdc_gate_valid"])
        self.assertFalse(res["pcb_matches_xdc"])
        conflict_by_port = {c["port"]: c for c in res["pcb_clock_conflicts"]}
        self.assertEqual(conflict_by_port["clk_120m_dac"]["pcb_pin"], "C13")
        self.assertEqual(conflict_by_port["clk_120m_dac"]["xdc_pin"], "D13")
        self.assertEqual(conflict_by_port["clk_120m_dac"]["pcb_pin_side"], "N")
        self.assertEqual(conflict_by_port["ft_clkout"]["pcb_pin"], "C4")
        self.assertEqual(conflict_by_port["ft_clkout"]["xdc_pin"], "D4")
        self.assertEqual(conflict_by_port["ft_clkout"]["pcb_pin_side"], "N")

        rc_pcb = check_fpga_clocks.main(
            [
                "--state",
                str(self.state_path),
                "--xdc",
                str(self.xdc_path),
                "--mmcm-xdc",
                str(self.mmcm_xdc_path),
                "--build-tcl",
                str(self.build_tcl_path),
                "--require-pcb-match",
            ]
        )
        self.assertEqual(rc_pcb, 1)

    def test_08_negative_fixture_legacy_c13_c4_and_bivc1_xdc_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            bad_xdc = tmp_dir / "legacy_broken.xdc"
            bad_mmcm = tmp_dir / "legacy_mmcm.xdc"
            bad_tcl = tmp_dir / "legacy_build_50t.tcl"

            bad_xdc.write_text(
                "\n".join(
                    (
                        "set_property PACKAGE_PIN E12 [get_ports {clk_100m}]",
                        "set_property PACKAGE_PIN C13 [get_ports {clk_120m_dac}]",
                        "set_property PACKAGE_PIN C4 [get_ports {ft_clkout}]",
                        "set_property CLOCK_DEDICATED_ROUTE FALSE [get_nets {ft_clkout_IBUF}]",
                        "set_property PACKAGE_PIN N14 [get_ports {adc_dco_p}]",
                        "set_property PACKAGE_PIN P14 [get_ports {adc_dco_n}]",
                        "set_property IOSTANDARD LVDS_25 [get_ports {adc_dco_p}]",
                        "set_property IOSTANDARD LVDS_25 [get_ports {adc_dco_n}]",
                        "set_property DIFF_TERM TRUE [get_ports {adc_dco_p}]",
                        "set_property PACKAGE_PIN T5 [get_ports {adc_pwdn}]",
                        "set_property IOSTANDARD LVCMOS25 [get_ports {adc_pwdn}]",
                        "set_property IOSTANDARD LVDS_25 [get_ports {adc_d_p[*]}]",
                        "set_property IOSTANDARD LVDS_25 [get_ports {adc_d_n[*]}]",
                        "set_property DIFF_TERM TRUE [get_ports {adc_d_p[*]}]",
                        "set_output_delay -clock [get_clocks ft_clkout] \\",
                        "    -max 11.667 [get_ports {ft_data[*]}]",
                        "set_false_path -from [get_cells reset_sync_reg[*]] \\",
                        "    -to [get_pins -filter {REF_PIN_NAME == CLR}]",
                    )
                ),
                encoding="utf-8",
            )
            bad_mmcm.write_text(
                textwrap.dedent(
                    """\
                    set_false_path -from [get_clocks clk_mmcm_out0] -to [get_clocks ft601_clk_in]
                    set_false_path -from [get_clocks ft601_clk_in] -to [get_clocks clk_mmcm_out0]
                    set_false_path -through [get_pins rx_inst/adc/mmcm_inst/mmcm_adc_400m/LOCKED]
                    """
                ),
                encoding="utf-8",
            )
            bad_tcl.write_text(
                textwrap.dedent(
                    """\
                    set_property SEVERITY {Warning} [get_drc_checks BIVC-1]
                    set_property SEVERITY {Warning} [get_drc_checks NSTD-1]
                    set_property SEVERITY {Warning} [get_drc_checks UCIO-1]
                    set_property SEVERITY {Warning} [get_drc_checks PLIO-9]
                    set_property CLOCK_DEDICATED_ROUTE FALSE [get_nets {ft_clkout_IBUF}]
                    write_bitstream -force out.bit
                    """
                ),
                encoding="utf-8",
            )

            res = check_fpga_clocks.audit_fpga_xdc_and_tcl(
                xdc_path=bad_xdc,
                mmcm_xdc_path=bad_mmcm,
                build_tcl_path=bad_tcl,
            )
            self.assertFalse(res["xdc_gate_valid"])
            joined = "\n".join(res["violations"])
            self.assertIn("MRCC_N_SIDE_OR_NON_CC_PIN:clk_120m_dac:C13", joined)
            self.assertIn("MRCC_N_SIDE_OR_NON_CC_PIN:ft_clkout:C4", joined)
            self.assertIn("FORBIDDEN_CLOCK_DEDICATED_ROUTE_FALSE_IN_XDC", joined)
            self.assertIn("BANK14_ADC_PWDN_IOSTANDARD_MISMATCH:LVCMOS25", joined)
            self.assertIn("BANK14_DIFF_TERM_NOT_FALSE:adc_dco_p:TRUE", joined)
            self.assertIn("BANK14_DIFF_TERM_NOT_FALSE:adc_d_p[*]:TRUE", joined)
            self.assertIn("MISSING_HIERARCHICAL_RESET_SYNC", joined)
            self.assertIn("FT2232H_OUTPUT_DELAY_MISMATCH:ft_data[*]:11.667", joined)
            self.assertIn("NONEXISTENT_FT601_CLK_IN_IN_MMCM_XDC", joined)
            self.assertIn("UNPREFIXED_MMCM_LOCKED_PATH_IN_MMCM_XDC", joined)
            self.assertIn("FORBIDDEN_DRC_WARNING_DEMOTION_IN_TCL:BIVC-1", joined)
            self.assertIn("FORBIDDEN_DRC_WARNING_DEMOTION_IN_TCL:PLIO-9", joined)
            self.assertIn("MISSING_PRODUCTION_GATE_SOURCE_IN_TCL", joined)

            rc = check_fpga_clocks.main(
                [
                    "--state",
                    str(self.state_path),
                    "--xdc",
                    str(bad_xdc),
                    "--mmcm-xdc",
                    str(bad_mmcm),
                    "--build-tcl",
                    str(bad_tcl),
                    "--verify-xdc",
                ]
            )
            self.assertEqual(rc, 1)

    def test_09_negative_fixture_trial11_lvcmos33_plus_diff_term_true_bivc1_trap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            trap_xdc = tmp_dir / "trial11_trap.xdc"
            trap_xdc.write_text(
                self.xdc_path.read_text(encoding="utf-8").replace(
                    "set_property DIFF_TERM FALSE [get_ports {adc_dco_p}]",
                    "set_property DIFF_TERM TRUE [get_ports {adc_dco_p}]",
                ),
                encoding="utf-8",
            )
            res = check_fpga_clocks.audit_fpga_xdc_and_tcl(
                xdc_path=trap_xdc,
                mmcm_xdc_path=self.mmcm_xdc_path,
                build_tcl_path=self.build_tcl_path,
            )
            self.assertFalse(res["xdc_gate_valid"])
            self.assertIn("BANK14_DIFF_TERM_NOT_FALSE:adc_dco_p:TRUE", res["violations"])


if __name__ == "__main__":
    unittest.main()
