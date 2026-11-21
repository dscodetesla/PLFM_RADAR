#!/usr/bin/env python3
"""Unit test suite (23 tests) for PLFM_RADAR manufacturing, FPGA clock, and CAD XML gates."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.manufacturing import audit, check_fpga_clocks


class TestManufacturingAndClockGates(unittest.TestCase):
    """Verify R&D checkpoint invariants, ECO candidate terminology, and strict CI gates."""

    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[3]
        self.state_path = self.repo_root / "docs" / "project-context" / "state.json"

    def test_01_state_file_exists_and_valid_json(self) -> None:
        self.assertTrue(self.state_path.exists())
        data = json.loads(self.state_path.read_text(encoding="utf-8"))
        self.assertEqual(data["project"], "PLFM_RADAR")

    def test_02_variant_scope_is_aeris_10n_four_boards(self) -> None:
        data = json.loads(self.state_path.read_text(encoding="utf-8"))
        self.assertEqual(data["variant"], "AERIS-10N Nexus R0.1")
        boards = [b["name"] for b in data["included_boards"]]
        self.assertEqual(
            boards,
            ["MainBoard", "Frequency Synthesizer", "PowerBoard", "Patch 8x16"],
        )

    def test_03_excluded_extended_hardware_documented(self) -> None:
        data = json.loads(self.state_path.read_text(encoding="utf-8"))
        excluded = " ".join(data["excluded_hardware"])
        self.assertIn("QPA2962", excluded)
        self.assertIn("DFSWA.dwg", excluded)

    def test_04_checkpoint_and_upstream_commits_recorded(self) -> None:
        data = json.loads(self.state_path.read_text(encoding="utf-8"))
        self.assertEqual(data["checkpoint_branch"], "checkpoint/rnd-2026-10-24")
        self.assertEqual(data["checkpoint_commit"], "a4840b40")
        self.assertEqual(
            data["upstream_base_commit"],
            "749bd0f86a07a28a86347d8ce9c141e601057c40",
        )

    def test_05_readiness_guards_not_for_manufacture_or_flash(self) -> None:
        data = json.loads(self.state_path.read_text(encoding="utf-8"))
        self.assertEqual(data["readiness"], "Draft")
        self.assertEqual(data["manufacturing_status"], "NOT_FOR_MANUFACTURE")
        self.assertEqual(data["firmware_flash_status"], "NOT_FOR_FLASH")

    def test_06_completed_iterations_1_through_8(self) -> None:
        data = json.loads(self.state_path.read_text(encoding="utf-8"))
        self.assertEqual(data["completed_iterations"], [1, 2, 3, 4, 5, 6, 7, 8])

    def test_07_investigation_dependency_order_9_to_14(self) -> None:
        data = json.loads(self.state_path.read_text(encoding="utf-8"))
        inv = data["open_investigations"]
        self.assertEqual(inv["first_wave"], [9, 10, 11])
        self.assertEqual(inv["dependent_on_first_wave"], [12])
        self.assertEqual(inv["independent_parallel"], [13, 14])

    def test_08_c13_d13_framed_as_eco_candidate_investigation_9(self) -> None:
        report = check_fpga_clocks.evaluate_fpga_clocks(self.state_path)
        dac_clk = report["clock_candidates"][0]
        self.assertEqual(dac_clk["signal"], "FPGA_DAC_CLOCK")
        self.assertEqual(dac_clk["sch_brd_pin"], "C13")
        self.assertEqual(dac_clk["xdc_pin"], "D13")
        self.assertEqual(dac_clk["classification"], "ECO_CANDIDATE")
        self.assertEqual(dac_clk["investigation_id"], "#9")
        self.assertFalse(dac_clk["resolved"])

    def test_09_c4_d4_framed_as_eco_candidate_investigation_10(self) -> None:
        report = check_fpga_clocks.evaluate_fpga_clocks(self.state_path)
        ft_clk = report["clock_candidates"][1]
        self.assertEqual(ft_clk["signal"], "FT_CLKOUT")
        self.assertEqual(ft_clk["sch_brd_pin"], "C4")
        self.assertEqual(ft_clk["candidate_pin"], "D4")
        self.assertEqual(ft_clk["classification"], "ECO_CANDIDATE")
        self.assertEqual(ft_clk["investigation_id"], "#10")
        self.assertFalse(ft_clk["resolved"])

    def test_10_bank14_bivc1_plio9_investigation_11(self) -> None:
        report = check_fpga_clocks.evaluate_fpga_clocks(self.state_path)
        b14 = report["bank14_audit"]
        self.assertEqual(b14["bank"], 14)
        self.assertEqual(b14["drc_codes"], ["BIVC-1", "PLIO-9"])
        self.assertEqual(b14["investigation_id"], "#11")
        self.assertFalse(b14["resolved"])

    def test_11_check_fpga_clocks_cli_default_and_require_resolved(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_path = Path(tmp) / "clocks.json"
            rc_default = check_fpga_clocks.main(
                ["--state", str(self.state_path), "--output", str(out_path)]
            )
            self.assertEqual(rc_default, 0)
            self.assertTrue(out_path.exists())
            rc_strict = check_fpga_clocks.main(
                ["--state", str(self.state_path), "--require-resolved"]
            )
            self.assertEqual(rc_strict, 1)

    def test_12_audit_non_strict_returns_zero_and_writes_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_path = Path(tmp) / "audit.json"
            rc = audit.main(
                [
                    "--state",
                    str(self.state_path),
                    "--repo-root",
                    str(self.repo_root),
                    "--output",
                    str(out_path),
                ]
            )
            self.assertEqual(rc, 0)
            report = json.loads(out_path.read_text(encoding="utf-8"))
            self.assertFalse(report["release_ready"])
            self.assertGreaterEqual(report["blocker_count"], 4)

    def test_13_audit_strict_returns_nonzero_when_blockers_active(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_path = Path(tmp) / "audit-strict.json"
            rc = audit.main(
                [
                    "--strict",
                    "--state",
                    str(self.state_path),
                    "--repo-root",
                    str(self.repo_root),
                    "--output",
                    str(out_path),
                ]
            )
            self.assertEqual(rc, 1)

    def test_14_audit_strict_returns_zero_when_all_gates_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            custom_state = json.loads(self.state_path.read_text(encoding="utf-8"))
            for k in custom_state["gates"]:
                custom_state["gates"][k] = "PASS"
            state_file = tmp_path / "state_pass.json"
            state_file.write_text(json.dumps(custom_state), encoding="utf-8")
            out_file = tmp_path / "audit_pass.json"
            rc = audit.main(
                [
                    "--strict",
                    "--state",
                    str(state_file),
                    "--repo-root",
                    str(tmp_path),
                    "--output",
                    str(out_file),
                ]
            )
            self.assertEqual(rc, 0)

    def test_15_zero_occurrences_of_fabricated_rev_eco1_term(self) -> None:
        hits = audit.scan_forbidden_terminology(self.repo_root)
        self.assertEqual(hits, [])

    def test_16_forbidden_term_detector_catches_violation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            (tmp_root / "README.md").write_text(
                f"Bad reference to {audit.FORBIDDEN_TERM}", encoding="utf-8"
            )
            hits = audit.scan_forbidden_terminology(tmp_root)
            self.assertEqual(hits, ["README.md"])

    def test_17_mainboard_profile_matches_verified_metrics(self) -> None:
        data = json.loads(self.state_path.read_text(encoding="utf-8"))
        mb = next(b for b in data["included_boards"] if b["name"] == "MainBoard")
        self.assertEqual(mb["copper_layers"], 10)
        self.assertEqual(mb["cad_elements"], 791)
        self.assertEqual(mb["fitted_cpl_items"], 709)
        self.assertEqual(mb["connected_pads"], 3453)
        self.assertEqual(mb["via_count"], 1604)
        self.assertTrue(mb["gerber_stale"])

    def test_18_powerboard_x36_recovered_in_sch_and_pending_native_cad(self) -> None:
        data = json.loads(self.state_path.read_text(encoding="utf-8"))
        pb = next(b for b in data["included_boards"] if b["name"] == "PowerBoard")
        self.assertEqual(pb["copper_layers"], 2)
        self.assertTrue(pb["x36_recovered_in_sch"])
        self.assertIn(13, data["open_investigations"]["independent_parallel"])

    def test_19_production_gate_tcl_enforces_zero_waivers(self) -> None:
        tcl_path = (
            self.repo_root
            / "docs"
            / "manufacturing"
            / "evidence"
            / "production_gate.tcl"
        )
        self.assertTrue(tcl_path.exists())
        tcl_text = tcl_path.read_text(encoding="utf-8")
        self.assertIn("plfm_require_production_checks", tcl_text)
        for code in ["NSTD-1", "UCIO-1", "BIVC-1", "PLIO-9", "CLOCK_DEDICATED_ROUTE"]:
            self.assertIn(code, tcl_text)

    def test_20_rnd_checkpoint_report_contains_all_investigations_9_to_14(self) -> None:
        rnd_txt = (
            self.repo_root / "docs" / "rnd" / "PLFM_RADAR_RND_20261024.txt"
        ).read_text(encoding="utf-8")
        for tag in [
            "Investigation #9",
            "Investigation #10",
            "Investigation #11",
            "Investigation #12",
            "Investigation #13",
            "Investigation #14",
        ]:
            self.assertIn(tag, rnd_txt)

    def test_21_evidence_pack_files_present(self) -> None:
        ev_dir = self.repo_root / "docs" / "manufacturing" / "evidence"
        expected = [
            "production_gate.tcl",
            "vivado-2026.1-part-probe.txt",
            "negative-drc-nstd1-gate.txt",
            "audit-report-2026-10-24.json",
            "fpga-clocks-audit-2026-10-24.json",
        ]
        for fname in expected:
            self.assertTrue((ev_dir / fname).exists(), f"Missing evidence file: {fname}")

    def test_22_mainboard_brd_62d4c556_short_resolved_and_adversarial_detection(
        self,
    ) -> None:
        mb_brd = self.repo_root / audit.MAINBOARD_BRD_REL
        self.assertTrue(mb_brd.exists(), f"Missing {mb_brd}")
        res = audit.verify_mainboard_brd_xml(mb_brd)
        self.assertTrue(res["valid"], f"Unexpected MainBoard XML errors: {res['errors']}")
        self.assertEqual(res["eagle_version"], "7.6.0")
        self.assertEqual(res["elements"], 791)
        self.assertEqual(res["connected_pads"], 3453)
        self.assertEqual(res["min_drill_0p15_vias"], 1604)
        self.assertEqual(res["short_hits"], [])

        orig_seg = '<wire x1="55.35" y1="137.2" x2="55.475" y2="137.275" width="0.1" layer="1"/>'
        short_seg = '<wire x1="55.35" y1="137.2" x2="53.4" y2="135.25" width="0.1" layer="1"/>'
        with tempfile.TemporaryDirectory() as tmp:
            bad_brd = Path(tmp) / "bad_main.brd"
            bad_xml = mb_brd.read_text(encoding="utf-8").replace(
                orig_seg,
                f"{short_seg}\n{orig_seg}",
                1,
            )
            bad_brd.write_text(bad_xml, encoding="utf-8")
            bad_res = audit.verify_mainboard_brd_xml(bad_brd)
            self.assertFalse(bad_res["valid"])
            self.assertEqual(len(bad_res["short_hits"]), 1)

    def test_23_patch_antenna_16x8_pitch_coax_and_64_pad_parity(self) -> None:
        patch_brd = self.repo_root / audit.PATCH_BRD_REL
        patch_sch = self.repo_root / audit.PATCH_SCH_REL
        patch_mnt = self.repo_root / audit.PATCH_MNT_REL
        self.assertTrue(patch_brd.exists(), f"Missing {patch_brd}")
        self.assertTrue(patch_sch.exists(), f"Missing {patch_sch}")
        self.assertTrue(patch_mnt.exists(), f"Missing {patch_mnt}")

        res = audit.verify_patch_antenna_xml(patch_brd, patch_sch, patch_mnt)
        self.assertTrue(res["valid"], f"Unexpected Patch 8x16 XML errors: {res['errors']}")
        self.assertEqual(res["sma_connectors"], 16)
        self.assertEqual(res["patch_columns"], 16)
        self.assertEqual(res["board_connected_pads"], 64)
        self.assertEqual(res["schematic_connected_pads"], 64)
        self.assertTrue(res["sch_brd_parity"])

        pkg_spec = 'library="142-0731-211" package="1420731211" value="142-0731-211"'
        j9_good = f'name="J9" {pkg_spec} x="172.74"'
        j9_bad = j9_good.replace('x="172.74"', 'x="172.82"')
        with tempfile.TemporaryDirectory() as tmp:
            bad_patch = Path(tmp) / "bad_patch.brd"
            bad_patch.write_text(
                patch_brd.read_text(encoding="utf-8").replace(j9_good, j9_bad),
                encoding="utf-8",
            )
            bad_res = audit.verify_patch_antenna_xml(bad_patch, patch_sch, None)
            self.assertFalse(bad_res["valid"])
            self.assertEqual(len(bad_res["pitch_errors"]), 1)
            self.assertEqual(bad_res["pitch_errors"][0]["ref"], "J9")


if __name__ == "__main__":
    unittest.main()
