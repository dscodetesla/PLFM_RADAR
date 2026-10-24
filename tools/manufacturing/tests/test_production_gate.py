"""Block bitstream acceptance on invalid native DRC/timing evidence."""
import tkinter
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
GATE = ROOT / "9_Firmware/9_2_FPGA/scripts/50t/production_gate.tcl"


class ProductionGateTests(unittest.TestCase):
    def run_gate(self, violations="", severity="Error", setup="0.2", hold="0.1",
                 missing=False):
        tcl = tkinter.Tcl()
        tcl.setvar("violations", violations)
        tcl.setvar("severity", severity)
        tcl.setvar("setup_slack", setup)
        tcl.setvar("hold_slack", hold)
        tcl.setvar("missing", int(missing))
        tcl.eval("""
            proc get_drc_violations {args} {return $::violations}
            proc get_timing_paths {args} {
                if {$::missing} {return {}}
                if {[lsearch -exact $args min] >= 0} {return hold_path}
                return setup_path
            }
            proc get_property {property object} {
                if {$property eq "SEVERITY"} {return $::severity}
                if {$object eq "hold_path"} {return $::hold_slack}
                return $::setup_slack
            }
        """)
        tcl.call("source", str(GATE))
        tcl.call("plfm_require_production_checks")

    def test_valid_timed_paths_pass(self):
        self.run_gate()
        self.run_gate(setup="0", hold="0")

    def test_drc_and_timing_failures_block_acceptance(self):
        for case in ({"violations": "BIVC-1"},
                     {"violations": "PLIO-9", "severity": "Critical Warning"},
                     {"setup": "-0.001"}, {"hold": "-0.001"},
                     {"setup": "N/A"}, {"setup": "Inf"}, {"setup": "NaN"},
                     {"violations": "unknown", "severity": ""}, {"missing": True}):
            with self.subTest(case=case), self.assertRaises(tkinter.TclError):
                self.run_gate(**case)

    def test_production_script_preserves_native_drc_and_gates_bitstream(self):
        script = GATE.with_name("build_50t.tcl").read_text()
        self.assertNotIn("set_property SEVERITY", script)
        self.assertNotIn("CLOCK_DEDICATED_ROUTE FALSE", script)
        self.assertLess(script.index("report_drc"), script.index("plfm_require_production_checks"))
        self.assertLess(script.index("plfm_require_production_checks"),
                        script.index("write_bitstream"))


if __name__ == "__main__":
    unittest.main()
