#!/usr/bin/env python3
"""Fail fast on MainBoard clock pin mismatch before a production Vivado build."""
import json
import sys
from pathlib import Path

from audit import audit_fpga_clocks


def main():
    report = audit_fpga_clocks(Path(__file__).resolve().parents[2])
    print(json.dumps(report, indent=2))
    return 1 if report["findings"] else 0


if __name__ == "__main__":
    sys.exit(main())
