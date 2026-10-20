#!/usr/bin/env python3
"""Read-only EAGLE/XLSX inventory audit. This is NOT native ERC/DRC or CAM verification."""

import argparse
import hashlib
import json
import math
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from zipfile import ZipFile

READINESS = "NOT_FOR_MANUFACTURE"
BASE = Path("4_Schematics and Boards Layout")
BOARDS = {
    "main": ("MainBoard/RADAR_Main_Board", "Gerber_Main_Board", "BOM_Main_Board.xlsx"),
    "synth": (
        "FrequencySynthesizerBoard/Clocks_Freq_Synth_board",
        "Gerber_freq_synth", "BOM_Freq_Synth.xlsx",
    ),
    "power": ("PowerBoard/PowerBoard", "Gerber_PowerBoard", "BOM_Power_Board.xlsx"),
    "patch": (
        "Antennas/Patch/8x16/Patch_Anetnna_16_8",
        "Gerber_Patch_Antenna", "BOM_Patch_Antenna.xlsx",
    ),
}
NS = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
CLOCK_NETS = {
    "clk_100m": "FPGA_SYS_CLOCK", "clk_120m_dac": "FPGA_DAC_CLOCK",
    "ft_clkout": "FT_CLKOUT", "adc_dco_p": "ADC_DCO_P", "adc_dco_n": "ADC_DCO_N",
}


def read_xlsx(path):
    """Read first-sheet cells, respecting actual cell addresses and string storage.

    Formulas are deliberately rejected: an uncalculated cached value is not evidence.
    """
    with ZipFile(path) as archive:
        strings = []
        if "xl/sharedStrings.xml" in archive.namelist():
            strings = [
                "".join(x.itertext())
                for x in ET.fromstring(archive.read("xl/sharedStrings.xml"))
            ]
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        sheet = workbook.find("s:sheets/s:sheet", NS)
        rel_id = sheet.get(
            "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
        )
        rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        target = next(x.get("Target") for x in rels if x.get("Id") == rel_id)
        member = target.lstrip("/") if target.startswith("/") else f"xl/{target}"
        root = ET.fromstring(archive.read(member))
        rows = []
        for row in root.findall("s:sheetData/s:row", NS):
            cells = {}
            for cell in row:
                if cell.find("s:f", NS) is not None:
                    raise ValueError(f"{path}: formula at {cell.get('r')} needs native recalculation")
                address = re.fullmatch(r"([A-Z]+)([0-9]+)", cell.get("r", ""))
                if not address:
                    raise ValueError(f"{path}: missing or invalid cell address")
                index = 0
                for char in address[1]:
                    index = index * 26 + ord(char) - ord("A") + 1
                value = cell.findtext("s:v", default="", namespaces=NS)
                kind = cell.get("t")
                if kind == "s":
                    value = strings[int(value)]
                elif kind == "inlineStr":
                    value = "".join(cell.find("s:is", NS).itertext())
                elif kind not in ("str", "e") and value:
                    value = float(value)
                cells[index - 1] = value
            if any(v != "" for v in cells.values()):
                rows.append((int(row.get("r")), cells))
        if not rows:
            raise ValueError(f"{path}: empty workbook")
        header = rows[0][1]
        return [
            {**{str(name): cells.get(i, "") for i, name in header.items() if name},
             "_row": number}
            for number, cells in rows[1:]
        ]


def refs(row):
    return [s.strip() for s in str(row.get("Parts", "")).split(",") if s.strip()]


def finding(code, detail):
    return {"code": code, "detail": detail}


def check_bom(rows, elements):
    results = []
    counts = Counter()
    for row in rows:
        names = refs(row)
        counts.update(names)
        if row.get("Qty") != len(names) or not names:
            results.append(finding("BOM_QUANTITY", {
                "row": row.get("_row"), "declared": row.get("Qty"),
                "references": len(names),
            }))
    for name, count in sorted(counts.items()):
        if count > 1:
            results.append(finding("BOM_DUPLICATE", {"ref": name, "count": count}))
    for code, names in (
        ("BOM_MISSING", elements - counts.keys()),
        ("BOM_EXTRA", counts.keys() - elements),
    ):
        if names:
            results.append(finding(code, sorted(names)))
    return results


def placement_ref(row):
    return str(row.get("Designator", row.get("DESIGNATOR", ""))).strip()


def dnp_refs(rows):
    return {
        ref for row in rows for ref in refs(row)
        if any(token in " ".join(str(v).upper() for v in row.values())
               for token in ("DNP", "DO NOT PUT", "NOT A COMPONENT"))
    }


def check_placement(bom, placement, elements, required_refs=None):
    results = []
    counts = Counter(placement_ref(row) for row in placement)
    if not placement and elements - dnp_refs(bom):
        results.append(finding("CPL_EMPTY", "No placements for a populated board"))
    if "" in counts:
        results.append(finding("CPL_EMPTY_REF", counts[""]))
    for code, names in (
        ("CPL_DNP", dnp_refs(bom) & counts.keys()),
        ("CPL_EXTRA", counts.keys() - elements),
        ("CPL_DUPLICATE", {name for name, count in counts.items() if count > 1}),
        ("CPL_MISSING", set(required_refs or ()) - dnp_refs(bom) - counts.keys()),
    ):
        if names:
            results.append(finding(code, sorted(names)))
    return results


def check_cpl_values(rows):
    """Validate export fields only; this cannot establish true pick-and-place centroids."""
    results = []
    for row in rows:
        normalized = {re.sub(r"[^a-z]", "", str(key).lower()): value
                      for key, value in row.items()}
        required = {"designator", "midxmm", "midymm", "layer", "rotation"}
        missing = required - normalized.keys()
        if missing:
            results.append(finding("CPL_SCHEMA", {"row": row.get("_row"),
                                                  "missing": sorted(missing)}))
            continue
        for field in ("midxmm", "midymm", "rotation"):
            try:
                value = float(normalized[field])
                valid = math.isfinite(value)
            except (ValueError, TypeError):
                valid = False
            if not valid:
                results.append(finding("CPL_NUMBER", {"ref": placement_ref(row),
                                                       "field": field}))
        if str(normalized["layer"]).strip().lower() not in ("top", "bottom"):
            results.append(finding("CPL_LAYER", {"ref": placement_ref(row),
                                                 "value": normalized["layer"]}))
    return results


def schematic_parts(path):
    root = ET.parse(path).getroot().find("./drawing/schematic")
    if root is None:
        raise ValueError(f"{path}: not an EAGLE schematic")
    devices = {}
    for library in root.findall("./libraries/library"):
        for device_set in library.findall("./devicesets/deviceset"):
            for device in device_set.findall("./devices/device"):
                devices[(library.get("name"), device_set.get("name"),
                         device.get("name", ""))] = device
    parts = {}
    for part in root.findall("./parts/part"):
        device = devices[(part.get("library"), part.get("deviceset"), part.get("device", ""))]
        if device.get("package"):
            parts[part.get("name")] = {
                "package": device.get("package"), "value": part.get("value"),
            }
    return parts


def add_pad_net(mapping, contact, net):
    if contact in mapping and mapping[contact] != net:
        raise ValueError(f"Conflicting nets for {contact}: {mapping[contact]} / {net}")
    mapping[contact] = net


def schematic_pad_nets(schematic):
    """Resolve saved pinrefs through device connects, including multi-pad pins.

    This compares logical net membership only. Geometry, routed continuity,
    implicit native supply semantics and hierarchical modules require native ERC.
    """
    if schematic is None or schematic.findall("./modules/module"):
        raise ValueError("Missing schematic or unsupported hierarchical modules")
    devices = {
        (lib.get("name"), ds.get("name"), dev.get("name", "")): dev
        for lib in schematic.findall("./libraries/library")
        for ds in lib.findall("./devicesets/deviceset")
        for dev in ds.findall("./devices/device")
    }
    parts = {
        p.get("name"): devices[(p.get("library"), p.get("deviceset"), p.get("device", ""))]
        for p in schematic.findall("./parts/part")
    }
    mapping = {}
    for net in schematic.findall("./sheets/sheet/nets/net"):
        for ref in net.iter("pinref"):
            device = parts[ref.get("part")]
            if not device.get("package"):
                continue
            connects = [c for c in device.findall("./connects/connect")
                        if (c.get("gate"), c.get("pin")) ==
                        (ref.get("gate"), ref.get("pin"))]
            if len(connects) != 1 or not connects[0].get("pad", "").strip():
                raise ValueError(f"Unresolved/ambiguous device connect: {ref.attrib}")
            for pad in connects[0].get("pad").split():
                add_pad_net(mapping, (ref.get("part"), pad), net.get("name"))
    return mapping


def board_pad_nets(board):
    if board is None:
        raise ValueError("Missing EAGLE board")
    mapping = {}
    for signal in board.findall("./signals/signal"):
        for ref in signal.findall("contactref"):
            add_pad_net(mapping, (ref.get("element"), ref.get("pad")), signal.get("name"))
    return mapping


def compare_pad_nets(schematic, board):
    return [finding("CAD_PAD_NET", {"ref": ref, "pad": pad,
                                   "schematic": schematic.get((ref, pad)),
                                   "board": board.get((ref, pad))})
            for ref, pad in sorted(schematic.keys() | board.keys())
            if schematic.get((ref, pad)) != board.get((ref, pad))]


def check_connectivity(schematic_path, board_path):
    return compare_pad_nets(
        schematic_pad_nets(ET.parse(schematic_path).getroot().find("./drawing/schematic")),
        board_pad_nets(ET.parse(board_path).getroot().find("./drawing/board")),
    )


def check_clock_pins(board, xdc, contract=CLOCK_NETS):
    """Check five explicit clock assignments, not evaluate arbitrary Tcl/XDC."""
    assignments = {}
    for line in xdc.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        match = re.fullmatch(
            r"\s*set_property\s+PACKAGE_PIN\s+(\w+)\s+"
            r"\[get_ports\s+(?:\{([^{}]+)\}|([A-Za-z_]\w*))\]\s*;?\s*(?:#.*)?", line)
        if match:
            assignments.setdefault(match[2] or match[3], []).append(match[1])
        elif re.search(r"\bPACKAGE_PIN\b", line.split("#", 1)[0]):
            raise ValueError(f"Unsupported PACKAGE_PIN syntax; native review required: {line}")
    saved_nets = board_pad_nets(board)
    findings = []
    for port, net in contract.items():
        pads = sorted(pad for (ref, pad), signal in saved_nets.items()
                      if ref == "U42" and signal == net)
        pins = assignments.get(port, [])
        if len(pads) != 1 or pins != pads:
            findings.append(finding("FPGA_CLOCK_PIN", {"port": port, "net": net,
                                                      "board_pads": pads, "xdc_pins": pins}))
    return findings


def audit_fpga_clocks(repo):
    board = repo / BASE / "4_6_Schematics/MainBoard/RADAR_Main_Board.brd"
    xdc = repo / "9_Firmware/9_2_FPGA/constraints/xc7a50t_ftg256.xdc"
    return {
        "scope": "Five MainBoard U42 clock pins; no clock routing/timing approval",
        "inputs": {str(p.relative_to(repo)): hashlib.sha256(p.read_bytes()).hexdigest()
                   for p in (board, xdc)},
        "findings": check_clock_pins(ET.parse(board).getroot().find("./drawing/board"),
                                     xdc.read_text(encoding="utf-8")),
    }


def audit_board(repo, source, production, bom_name):
    cad = repo / BASE / "4_6_Schematics" / source
    prod = repo / BASE / "4_7_Production Files" / production
    paths = [cad.with_suffix(".sch"), cad.with_suffix(".brd"), prod / bom_name, prod / "CPL.xlsx"]
    sch = schematic_parts(paths[0])
    xml = ET.parse(paths[1]).getroot()
    board = xml.find("./drawing/board")
    elements = {e.get("name"): e for e in board.findall("./elements/element")}
    if not elements:
        raise ValueError(f"{paths[1]}: empty board")
    bom, cpl = read_xlsx(paths[2]), read_xlsx(paths[3])
    errors = check_bom(bom, set(elements)) + check_cpl_values(cpl)
    sch_nets = schematic_pad_nets(ET.parse(paths[0]).getroot().find("./drawing/schematic"))
    brd_nets = board_pad_nets(board)
    errors.extend(compare_pad_nets(sch_nets, brd_nets))
    for code, names in (
        ("CAD_BOARD_ONLY", elements.keys() - sch.keys()),
        ("CAD_SCHEMATIC_ONLY", sch.keys() - elements.keys()),
    ):
        if names:
            errors.append(finding(code, sorted(names)))
    for ref in sorted(elements.keys() & sch.keys()):
        for field in ("package", "value"):
            # No explicit value means a library-derived EAGLE value, not an empty part.
            if sch[ref][field] is None:
                continue
            if elements[ref].get(field, "") != sch[ref][field]:
                errors.append(finding("CAD_IDENTITY", {"ref": ref, "field": field,
                    "board": elements[ref].get(field, ""), "schematic": sch[ref][field]}))
    rules = {p.get("name"): p.get("value") for p in board.findall("./designrules/param")}
    setup = rules.get("layerSetup", "")
    layers = sorted({int(v) for v in re.findall(r"\d+", setup)})
    drills = Counter(v.get("drill") for v in board.findall("./signals/signal/via"))
    unresolved = []
    placed = {placement_ref(row) for row in cpl}
    required_placements = set()
    for ref in sorted(elements):
        element = elements[ref]
        package = next(
            p for lib in board.findall("./libraries/library")
            if lib.get("name") == element.get("library")
            for p in lib.findall("./packages/package")
            if p.get("name") == element.get("package")
        )
        if package.findall("smd"):
            required_placements.add(ref)
        if ref not in placed and ref not in dnp_refs(bom):
            unresolved.append({"ref": ref, "package": element.get("package"),
                "smd_pads": len(package.findall("smd")),
                "through_hole_pads": len(package.findall("pad"))})
    errors.extend(check_placement(bom, cpl, set(elements), required_placements))
    return {
        "inputs": {str(p.relative_to(repo)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
        "eagle_file_version": xml.get("version"),
        "board_elements": len(elements), "schematic_physical_parts": len(sch),
        "schematic_connected_pads": len(sch_nets), "board_connected_pads": len(brd_nets),
        "bom_rows": len(bom), "cpl_rows": len(cpl),
        "layer_setup": setup, "copper_layers": layers, "copper_layer_count": len(layers),
        "via_drills_mm": dict(sorted(drills.items())),
        "minimum_via_drill_mm": min(map(float, drills)) if drills else None,
        "stored_layer19_wires": len(board.findall("./signals/signal/wire[@layer='19']")),
        "findings": errors,
        "assembly_disposition_required": unresolved,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--output", type=Path)
    parser.add_argument("--strict", action="store_true", help="Fail on static inventory findings")
    args = parser.parse_args()
    repo = args.repo.resolve()
    report = {"schema_version": 1, "readiness": READINESS,
              "limitations": ["No native ERC/DRC or unrouted-net calculation",
                              "Saved logical pad/net membership only; no copper continuity or RF/impedance simulation",
                              "CPL origin, rotation, component fit and DNP intent need native review",
                              "Gerbers are existing unverified exports; no CAM equivalence proven"],
              "boards": {}}
    try:
        report["source_commit"] = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=repo, text=True
        ).strip()
        for name, spec in BOARDS.items():
            report["boards"][name] = audit_board(repo, *spec)
        report["fpga_clocks"] = audit_fpga_clocks(repo)
    except (OSError, ValueError, KeyError, ET.ParseError) as exc:
        sys.stderr.write(f"Audit input error: {exc}\n")
        return 2
    report["static_finding_count"] = (sum(len(b["findings"]) for b in report["boards"].values())
                                      + len(report["fpga_clocks"]["findings"]))
    report["static_status"] = "FINDINGS" if report["static_finding_count"] else "CHECKS_PASS"
    encoded = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    else:
        sys.stdout.write(encoded)
    return 1 if args.strict and report["static_finding_count"] else 0


if __name__ == "__main__":
    sys.exit(main())
