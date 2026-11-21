#!/usr/bin/env python3
"""Audit FPGA clock pin assignments, Bank 14 electrical rules, and 50T XDC/TCL gates."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STATE_PATH = Path("docs/project-context/state.json")
DEFAULT_XDC_PATH = REPO_ROOT / "9_Firmware" / "9_2_FPGA" / "constraints" / "xc7a50t_ftg256.xdc"
DEFAULT_MMCM_XDC_PATH = REPO_ROOT / "9_Firmware" / "9_2_FPGA" / "constraints" / "adc_clk_mmcm.xdc"
DEFAULT_BUILD_TCL_PATH = REPO_ROOT / "9_Firmware" / "9_2_FPGA" / "scripts" / "50t" / "build_50t.tcl"

UNMODIFIED_PCB_CLOCK_PINS: dict[str, str] = {
    "clk_120m_dac": "C13",
    "ft_clkout": "C4",
}

FTG256_CLOCK_CAPABLE_PINS: dict[str, dict[str, Any]] = {
    "E12": {"side": "P", "bank": 15, "pin_type": "IO_L11P_T1_SRCC_15"},
    "D13": {"side": "P", "bank": 15, "pin_type": "IO_L12P_T1_MRCC_15"},
    "C13": {"side": "N", "bank": 15, "pin_type": "IO_L12N_T1_MRCC_15"},
    "N14": {"side": "P", "bank": 14, "pin_type": "IO_L13P_T2_MRCC_14"},
    "P14": {"side": "N", "bank": 14, "pin_type": "IO_L13N_T2_MRCC_14"},
    "D4": {"side": "P", "bank": 35, "pin_type": "IO_L12P_T1_MRCC_35"},
    "C4": {"side": "N", "bank": 35, "pin_type": "IO_L12N_T1_MRCC_35"},
}

FT2232H_OUTPUT_TARGETS: tuple[str, ...] = (
    "ft_data[*]",
    "ft_rd_n",
    "ft_wr_n",
    "ft_oe_n",
    "ft_siwu",
)
CRITICAL_DRC_CODES: tuple[str, ...] = ("BIVC-1", "NSTD-1", "UCIO-1", "PLIO-9")

_OUT_DELAY_RE = re.compile(
    "".join(
        (
            r"^set_output_delay\s+-clock\s+\[get_clocks\s+\{?ft_clkout\}?\]\s+",
            r"-max\s+([0-9.]+)\s+(.+)$",
        )
    )
)
_CDC_MMCM_TO_FT_RE = re.compile(
    "".join(
        (
            r"set_false_path\s+-from\s+\[get_clocks\s+\{?clk_mmcm_out0\}?\]\s+",
            r"-to\s+\[get_clocks\s+\{?ft_clkout\}?\]",
        )
    )
)
_CDC_FT_TO_MMCM_RE = re.compile(
    "".join(
        (
            r"set_false_path\s+-from\s+\[get_clocks\s+\{?ft_clkout\}?\]\s+",
            r"-to\s+\[get_clocks\s+\{?clk_mmcm_out0\}?\]",
        )
    )
)


def _strip_tcl_comments_and_join(text: str) -> list[str]:
    """Strip full-line/inline Tcl comments and join backslash-continued lines."""
    logical_lines: list[str] = []
    buf = ""
    for raw in text.splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if ";#" in stripped:
            stripped = stripped.split(";#", 1)[0].rstrip()
        if stripped.endswith("\\"):
            buf = f"{buf}{stripped[:-1].rstrip()} "
            continue
        buf = f"{buf}{stripped}"
        if buf.strip():
            logical_lines.append(buf.strip())
        buf = ""
    if buf.strip():
        logical_lines.append(buf.strip())
    return logical_lines


def _extract_target(expr: str) -> str:
    """Normalize target inside [get_ports {...}] or [get_ports ...]."""
    m = re.search(r"\[get_ports\s+(?:-quiet\s+)?(?:\{([^}]+)\}|([^\]]+))\]", expr)
    if not m:
        return ""
    return (m.group(1) or m.group(2) or "").strip()


def audit_fpga_xdc_and_tcl(
    xdc_path: Path = DEFAULT_XDC_PATH,
    mmcm_xdc_path: Path = DEFAULT_MMCM_XDC_PATH,
    build_tcl_path: Path = DEFAULT_BUILD_TCL_PATH,
    pcb_clock_pins: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Static verification of 50T XDC/TCL constraints, Bank 14 rules, and MRCC pins."""
    pcb_map = dict(UNMODIFIED_PCB_CLOCK_PINS if pcb_clock_pins is None else pcb_clock_pins)
    violations: list[str] = []

    if not xdc_path.exists():
        return {
            "files_present": False,
            "xdc_gate_valid": False,
            "pcb_matches_xdc": False,
            "violations": [f"MISSING_XDC:{xdc_path}"],
            "pcb_clock_conflicts": [],
        }

    xdc_lines = _strip_tcl_comments_and_join(xdc_path.read_text(encoding="utf-8"))
    package_pins: dict[str, str] = {}
    iostandards: dict[str, str] = {}
    diff_terms: dict[str, str] = {}
    ft_output_max_delays: dict[str, float] = {}
    cdr_false_entries: list[str] = []
    reset_sync_patterns: list[str] = []

    for line in xdc_lines:
        if re.search(r"CLOCK_DEDICATED_ROUTE\s+FALSE", line):
            cdr_false_entries.append(line)

        m_prop = re.match(r"^set_property\s+(\S+)\s+(\S+)\s+(.+)$", line)
        if m_prop:
            prop, val, rest = m_prop.group(1), m_prop.group(2).strip("{}"), m_prop.group(3)
            port = _extract_target(rest)
            if port:
                if prop == "PACKAGE_PIN":
                    package_pins[port] = val
                elif prop == "IOSTANDARD":
                    iostandards[port] = val
                elif prop == "DIFF_TERM":
                    diff_terms[port] = val.upper()

        m_out = _OUT_DELAY_RE.match(line)
        if m_out:
            delay_val = float(m_out.group(1))
            port = _extract_target(m_out.group(2))
            if port:
                ft_output_max_delays[port] = delay_val

        if line.startswith("set_false_path") and "reset_sync" in line:
            m_cells = re.search(r"\[get_cells\s+(?:\{([^}]+)\}|([^\]]+))\]", line)
            if m_cells:
                reset_sync_patterns.append((m_cells.group(1) or m_cells.group(2) or "").strip())

    pcb_conflicts: list[dict[str, str]] = []
    for clk_port, expected_p_pin in (("clk_120m_dac", "D13"), ("ft_clkout", "D4")):
        actual_pin = package_pins.get(clk_port, "")
        pin_meta = FTG256_CLOCK_CAPABLE_PINS.get(actual_pin)
        if not actual_pin:
            violations.append(f"MISSING_CLOCK_PACKAGE_PIN:{clk_port}")
        elif pin_meta is None or pin_meta["side"] != "P":
            violations.append(f"MRCC_N_SIDE_OR_NON_CC_PIN:{clk_port}:{actual_pin}")
        elif actual_pin != expected_p_pin:
            violations.append(f"UNEXPECTED_CLOCK_PIN:{clk_port}:{actual_pin}!={expected_p_pin}")

        pcb_pin = pcb_map.get(clk_port, "")
        if pcb_pin and actual_pin and pcb_pin != actual_pin:
            pcb_side = FTG256_CLOCK_CAPABLE_PINS.get(pcb_pin, {}).get("side", "UNKNOWN")
            pcb_conflicts.append(
                {
                    "port": clk_port,
                    "pcb_pin": pcb_pin,
                    "xdc_pin": actual_pin,
                    "pcb_pin_side": pcb_side,
                }
            )

    if cdr_false_entries:
        violations.append("FORBIDDEN_CLOCK_DEDICATED_ROUTE_FALSE_IN_XDC")

    if package_pins.get("adc_pwdn") != "T5":
        violations.append(f"ADC_PWDN_PIN_MISMATCH:{package_pins.get('adc_pwdn')}")
    if iostandards.get("adc_pwdn") != "LVCMOS33":
        violations.append(f"BANK14_ADC_PWDN_IOSTANDARD_MISMATCH:{iostandards.get('adc_pwdn')}")

    for lvds_port in ("adc_dco_p", "adc_dco_n", "adc_d_p[*]", "adc_d_n[*]"):
        std_val = iostandards.get(lvds_port)
        if std_val != "LVDS_25":
            violations.append(f"BANK14_LVDS_IOSTANDARD_MISMATCH:{lvds_port}:{std_val}")

    violations.extend(
        f"BANK14_DIFF_TERM_NOT_FALSE:{diff_port}:{diff_terms.get(diff_port)}"
        for diff_port in ("adc_dco_p", "adc_d_p[*]")
        if diff_terms.get(diff_port) != "FALSE"
    )
    violations.extend(
        f"BANK14_DIFF_TERM_NOT_FALSE:{diff_n_port}:{diff_terms[diff_n_port]}"
        for diff_n_port in ("adc_dco_n", "adc_d_n[*]")
        if diff_n_port in diff_terms and diff_terms[diff_n_port] != "FALSE"
    )

    if "u_core/reset_sync*_reg[*]" not in reset_sync_patterns:
        violations.append(f"MISSING_HIERARCHICAL_RESET_SYNC:{reset_sync_patterns}")
    if "reset_sync_reg[*]" in reset_sync_patterns:
        violations.append("UNPREFIXED_RESET_SYNC_REG_IN_XDC")

    for target in FT2232H_OUTPUT_TARGETS:
        dval = ft_output_max_delays.get(target)
        if dval is None or abs(dval - 3.500) > 1e-6:
            violations.append(f"FT2232H_OUTPUT_DELAY_MISMATCH:{target}:{dval}")

    if not mmcm_xdc_path.exists():
        violations.append(f"MISSING_MMCM_XDC:{mmcm_xdc_path}")
    else:
        mmcm_lines = _strip_tcl_comments_and_join(mmcm_xdc_path.read_text(encoding="utf-8"))
        mmcm_joined = "\n".join(mmcm_lines)
        if "ft601_clk_in" in mmcm_joined:
            violations.append("NONEXISTENT_FT601_CLK_IN_IN_MMCM_XDC")
        if not (_CDC_MMCM_TO_FT_RE.search(mmcm_joined) and _CDC_FT_TO_MMCM_RE.search(mmcm_joined)):
            violations.append("MISSING_FT_CLKOUT_CDC_FALSE_PATH_IN_MMCM_XDC")
        if "u_core/rx_inst/adc/mmcm_inst/mmcm_adc_400m/LOCKED" not in mmcm_joined:
            violations.append("MISSING_U_CORE_MMCM_LOCKED_PATH_IN_MMCM_XDC")
        locked_unprefixed = r"\[get_pins\s+\{?rx_inst/adc/mmcm_inst/mmcm_adc_400m/LOCKED\}?\]"
        if re.search(locked_unprefixed, mmcm_joined):
            violations.append("UNPREFIXED_MMCM_LOCKED_PATH_IN_MMCM_XDC")

    if not build_tcl_path.exists():
        violations.append(f"MISSING_BUILD_TCL:{build_tcl_path}")
    else:
        tcl_lines = _strip_tcl_comments_and_join(build_tcl_path.read_text(encoding="utf-8"))
        tcl_joined = "\n".join(tcl_lines)
        violations.extend(
            f"FORBIDDEN_DRC_WARNING_DEMOTION_IN_TCL:{code}"
            for code in CRITICAL_DRC_CODES
            if re.search(rf"SEVERITY\s+\{{?Warning\}}?.*{re.escape(code)}", tcl_joined)
        )
        if re.search(r"CLOCK_DEDICATED_ROUTE\s+FALSE", tcl_joined):
            violations.append("FORBIDDEN_CLOCK_DEDICATED_ROUTE_FALSE_IN_TCL")
        if "production_gate.tcl" not in tcl_joined and "evidence_gate_tcl" not in tcl_joined:
            violations.append("MISSING_PRODUCTION_GATE_SOURCE_IN_TCL")
        if "production_gate.tcl" not in build_tcl_path.read_text(encoding="utf-8"):
            violations.append("MISSING_PRODUCTION_GATE_SOURCE_IN_TCL")
        gate_idx = tcl_joined.find("plfm_require_production_checks")
        bit_idx = tcl_joined.find("write_bitstream")
        if gate_idx == -1 or (bit_idx != -1 and gate_idx > bit_idx):
            violations.append("MISSING_PRE_BITSTREAM_GATE_INVOCATION_IN_TCL")

    return {
        "files_present": True,
        "xdc_gate_valid": len(violations) == 0,
        "pcb_matches_xdc": len(pcb_conflicts) == 0,
        "clock_pins_xdc": {
            "clk_100m": package_pins.get("clk_100m"),
            "clk_120m_dac": package_pins.get("clk_120m_dac"),
            "adc_dco_p": package_pins.get("adc_dco_p"),
            "ft_clkout": package_pins.get("ft_clkout"),
        },
        "bank14_xdc": {
            "adc_pwdn_pin": package_pins.get("adc_pwdn"),
            "adc_pwdn_iostandard": iostandards.get("adc_pwdn"),
            "adc_dco_diff_term": diff_terms.get("adc_dco_p"),
            "adc_d_diff_term": diff_terms.get("adc_d_p[*]"),
        },
        "ft2232h_output_delay_max_ns": ft_output_max_delays,
        "pcb_clock_conflicts": pcb_conflicts,
        "violations": violations,
    }


def evaluate_fpga_clocks(
    state_path: Path = DEFAULT_STATE_PATH,
    xdc_path: Path = DEFAULT_XDC_PATH,
    mmcm_xdc_path: Path = DEFAULT_MMCM_XDC_PATH,
    build_tcl_path: Path = DEFAULT_BUILD_TCL_PATH,
    pcb_clock_pins: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Return structured audit of FPGA clock candidates, Bank 14 rules, and XDC gate status."""
    state: dict[str, Any] = {}
    if state_path.exists():
        state = json.loads(state_path.read_text(encoding="utf-8"))

    xdc_audit = audit_fpga_xdc_and_tcl(
        xdc_path=xdc_path,
        mmcm_xdc_path=mmcm_xdc_path,
        build_tcl_path=build_tcl_path,
        pcb_clock_pins=pcb_clock_pins,
    )
    xdc_clocks = xdc_audit.get("clock_pins_xdc", {})

    clock_findings = [
        {
            "signal": "FPGA_DAC_CLOCK",
            "net": "clk_120m_dac",
            "frequency_mhz": 120.0,
            "sch_brd_pin": "C13",
            "sch_brd_pin_type": "IO_L12N_T1_MRCC_15 (N-side MRCC, Bank 15)",
            "xdc_pin": xdc_clocks.get("clk_120m_dac") or "D13",
            "xdc_pin_type": "IO_L12P_T1_MRCC_15 (P-side MRCC, Bank 15)",
            "classification": "ECO_CANDIDATE",
            "investigation_id": "#9",
            "evidence_tag": "[Proposal]",
            "resolved": False,
            "notes": " ".join(
                (
                    "C13->D13 is an ECO candidate [Proposal], not an approved PCB change.",
                    "XDC uses clean P-side MRCC D13 without waivers; physical BGA escape",
                    "routing and timing sign-off remain tracked under Investigation #9.",
                )
            ),
        },
        {
            "signal": "FT_CLKOUT",
            "net": "ft_clkout_60m",
            "frequency_mhz": 60.0,
            "sch_brd_pin": "C4",
            "sch_brd_pin_type": "IO_L12N_T1_MRCC_35 (N-side MRCC, Bank 35)",
            "xdc_pin": xdc_clocks.get("ft_clkout") or "D4",
            "candidate_pin": "D4",
            "candidate_pin_type": "IO_L12P_T1_MRCC_35 (P-side MRCC, Bank 35)",
            "classification": "ECO_CANDIDATE",
            "investigation_id": "#10",
            "evidence_tag": "[Proposal]",
            "resolved": False,
            "notes": " ".join(
                (
                    "C4->D4 is an ECO candidate [Proposal] under Investigation #10.",
                    "XDC uses clean P-side MRCC D4 without CLOCK_DEDICATED_ROUTE FALSE;",
                    "absence of contactref on D4 in XML does not guarantee BGA routability.",
                )
            ),
        },
    ]

    bank14_findings = {
        "bank": 14,
        "vcco_volts": 3.3,
        "lvds_inputs": "LVDS_25 (DIFF_TERM FALSE; external 100-ohm R2..R12 fitted)",
        "single_ended_pin": "T5 (IO_L23N_T3_A02_D18_14, adc_pwdn, LVCMOS33 via R36=830R/R37=1k)",
        "drc_codes": ["BIVC-1", "PLIO-9"],
        "xdc_bivc1_clean": (
            xdc_audit.get("bank14_xdc", {}).get("adc_pwdn_iostandard") == "LVCMOS33"
            and xdc_audit.get("bank14_xdc", {}).get("adc_dco_diff_term") == "FALSE"
            and xdc_audit.get("bank14_xdc", {}).get("adc_d_diff_term") == "FALSE"
        ),
        "investigation_id": "#11",
        "evidence_tag": "[?]",
        "resolved": False,
        "notes": " ".join(
            (
                "XDC sets DIFF_TERM FALSE on AD9484 LVDS_25 pairs (external 100R R2..R12)",
                "and LVCMOS33 on T5 adc_pwdn (divider R36=830R / R37=1k); tolerance/absmax",
                "sign-off tracked under Investigation #11 before hardware release.",
            )
        ),
    }

    guardrail_ok = bool(
        state.get("terminology_guardrails", {}).get(
            "unapproved_eco_revisions_forbidden", True
        )
    )

    return {
        "fpga_part": state.get("fpga_part", "xc7a50tftg256-2"),
        "status": "INVESTIGATION_REQUIRED",
        "firmware_flash_status": "NOT_FOR_FLASH",
        "dependency_order": {
            "first_wave": ["#9", "#10", "#11"],
            "after_first_wave": ["#12"],
            "independent": ["#13", "#14"],
        },
        "clock_candidates": clock_findings,
        "bank14_audit": bank14_findings,
        "xdc_verification": xdc_audit,
        "terminology_clean": guardrail_ok,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check PLFM_RADAR FPGA clock, Bank 14, and 50T XDC/TCL constraints."
    )
    parser.add_argument(
        "--state",
        type=Path,
        default=DEFAULT_STATE_PATH,
        help="Path to docs/project-context/state.json",
    )
    parser.add_argument(
        "--xdc",
        type=Path,
        default=DEFAULT_XDC_PATH,
        help="Path to 9_Firmware/9_2_FPGA/constraints/xc7a50t_ftg256.xdc",
    )
    parser.add_argument(
        "--mmcm-xdc",
        type=Path,
        default=DEFAULT_MMCM_XDC_PATH,
        help="Path to 9_Firmware/9_2_FPGA/constraints/adc_clk_mmcm.xdc",
    )
    parser.add_argument(
        "--build-tcl",
        type=Path,
        default=DEFAULT_BUILD_TCL_PATH,
        help="Path to 9_Firmware/9_2_FPGA/scripts/50t/build_50t.tcl",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional path to write JSON clock audit report",
    )
    parser.add_argument(
        "--verify-xdc",
        action="store_true",
        help="Return exit code 1 if XDC/TCL zero-waiver constraints fail verification",
    )
    parser.add_argument(
        "--require-pcb-match",
        action="store_true",
        help="Return exit code 1 if unmodified PCB clock pins (C13/C4) conflict with XDC (D13/D4)",
    )
    parser.add_argument(
        "--require-resolved",
        action="store_true",
        help="Return non-zero exit code if any clock or Bank 14 investigation is still open",
    )
    args = parser.parse_args(argv)

    report = evaluate_fpga_clocks(
        state_path=args.state,
        xdc_path=args.xdc,
        mmcm_xdc_path=args.mmcm_xdc,
        build_tcl_path=args.build_tcl,
    )
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(f"{json.dumps(report, indent=2)}\n", encoding="utf-8")

    xdc_ver = report["xdc_verification"]
    xdc_tag = "PASS" if xdc_ver["xdc_gate_valid"] else "FAIL"
    drc_str = ",".join(report["bank14_audit"]["drc_codes"])
    msg = (
        f"[check_fpga_clocks] part={report['fpga_part']} status={report['status']} "
        f"clocks={len(report['clock_candidates'])} bank14_drc={drc_str} xdc_gate={xdc_tag}\n"
    )
    sys.stdout.write(msg)

    if (args.verify_xdc or xdc_ver["files_present"]) and not xdc_ver["xdc_gate_valid"]:
        return 1
    if args.require_pcb_match and not xdc_ver["pcb_matches_xdc"]:
        return 1
    if args.require_resolved:
        unresolved = any(not c["resolved"] for c in report["clock_candidates"]) or (
            not report["bank14_audit"]["resolved"]
        )
        if unresolved:
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
