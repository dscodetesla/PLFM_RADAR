#!/usr/bin/env python3
"""Manufacturing, 4-board EAGLE/XLSX inventory, and R&D readiness gate audit for PLFM_RADAR."""
from __future__ import annotations

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
from typing import Any
from zipfile import ZipFile

try:
    from tools.manufacturing.check_fpga_clocks import evaluate_fpga_clocks
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from tools.manufacturing.check_fpga_clocks import evaluate_fpga_clocks

REPO_ROOT = Path(__file__).resolve().parents[2]
READINESS = "NOT_FOR_MANUFACTURE"
DEFAULT_STATE_PATH = Path("docs/project-context/state.json")
FORBIDDEN_TERM = "".join(("MainBoard", " Rev-ECO1"))

BASE = Path("4_Schematics and Boards Layout")
BOARDS: dict[str, tuple[str, str, str]] = {
    "main": ("MainBoard/RADAR_Main_Board", "Gerber_Main_Board", "BOM_Main_Board.xlsx"),
    "synth": (
        "FrequencySynthesizerBoard/Clocks_Freq_Synth_board",
        "Gerber_freq_synth",
        "BOM_Freq_Synth.xlsx",
    ),
    "power": ("PowerBoard/PowerBoard", "Gerber_PowerBoard", "BOM_Power_Board.xlsx"),
    "patch": (
        "Antennas/Patch/8x16/Patch_Anetnna_16_8",
        "Gerber_Patch_Antenna",
        "BOM_Patch_Antenna.xlsx",
    ),
}
NS = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
CLOCK_NETS: dict[str, str] = {
    "clk_100m": "FPGA_SYS_CLOCK",
    "clk_120m_dac": "FPGA_DAC_CLOCK",
    "ft_clkout": "FT_CLKOUT",
    "adc_dco_p": "ADC_DCO_P",
    "adc_dco_n": "ADC_DCO_N",
}

MAINBOARD_BRD_REL = Path(
    "4_Schematics and Boards Layout/4_6_Schematics/MainBoard/RADAR_Main_Board.brd"
)
PATCH_BRD_REL = Path(
    "4_Schematics and Boards Layout/4_6_Schematics/Antennas/Patch/8x16/Patch_Anetnna_16_8.brd"
)
PATCH_SCH_REL = BASE / "4_6_Schematics/Antennas/Patch/8x16/Patch_Anetnna_16_8.sch"
PATCH_MNT_REL = BASE / "4_7_Production Files/Gerber_Patch_Antenna/Patch_Anetnna_16_8.mnt"

_PACKAGE_PIN_RE = re.compile(
    "".join(
        (
            r"\s*set_property\s+PACKAGE_PIN\s+(\w+)\s+",
            r"\[get_ports\s+(?:\{([^{}]+)\}|([A-Za-z_]\w*))\]\s*;?\s*(?:#.*)?",
        )
    )
)


def read_xlsx(path: Path) -> list[dict[str, Any]]:
    """Read first-sheet cells, respecting actual cell addresses and string storage."""
    with ZipFile(path) as archive:
        strings: list[str] = []
        if "xl/sharedStrings.xml" in archive.namelist():
            strings = [
                "".join(x.itertext())
                for x in ET.fromstring(archive.read("xl/sharedStrings.xml"))
            ]
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        sheet = workbook.find("s:sheets/s:sheet", NS)
        if sheet is None:
            raise ValueError(f"{path}: missing worksheet")
        rel_ns = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
        rel_id = sheet.get(rel_ns)
        rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        target = next(x.get("Target", "") for x in rels if x.get("Id") == rel_id)
        member = target.lstrip("/") if target.startswith("/") else f"xl/{target}"
        root = ET.fromstring(archive.read(member))
        rows: list[tuple[int, dict[int, Any]]] = []
        for row in root.findall("s:sheetData/s:row", NS):
            cells: dict[int, Any] = {}
            for cell in row:
                if cell.find("s:f", NS) is not None:
                    raise ValueError(
                        f"{path}: formula at {cell.get('r')} needs native recalculation"
                    )
                address = re.fullmatch(r"([A-Z]+)([0-9]+)", cell.get("r", ""))
                if not address:
                    raise ValueError(f"{path}: missing or invalid cell address")
                index = 0
                for char in address[1]:
                    index = index * 26 + ord(char) - ord("A") + 1
                raw_val = cell.findtext("s:v", default="", namespaces=NS)
                kind = cell.get("t")
                value: Any = raw_val
                if kind == "s":
                    value = strings[int(raw_val)]
                elif kind == "inlineStr":
                    is_node = cell.find("s:is", NS)
                    value = "".join(is_node.itertext()) if is_node is not None else ""
                elif kind not in ("str", "e") and raw_val:
                    value = float(raw_val)
                cells[index - 1] = value
            if any(v != "" for v in cells.values()):
                rows.append((int(row.get("r", "0")), cells))
        if not rows:
            raise ValueError(f"{path}: empty workbook")
        header = rows[0][1]
        return [
            {
                **{str(name): cells.get(i, "") for i, name in header.items() if name},
                "_row": number,
            }
            for number, cells in rows[1:]
        ]


def refs(row: dict[str, Any]) -> list[str]:
    return [s.strip() for s in str(row.get("Parts", "")).split(",") if s.strip()]


def finding(code: str, detail: Any) -> dict[str, Any]:
    return {"code": code, "detail": detail}


def check_bom(rows: list[dict[str, Any]], elements: set[str]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    for row in rows:
        names = refs(row)
        counts.update(names)
        if row.get("Qty") != len(names) or not names:
            results.append(
                finding(
                    "BOM_QUANTITY",
                    {
                        "row": row.get("_row"),
                        "declared": row.get("Qty"),
                        "references": len(names),
                    },
                )
            )
    for name, count in sorted(counts.items()):
        if count > 1:
            results.append(finding("BOM_DUPLICATE", {"ref": name, "count": count}))
    for code, names_set in (
        ("BOM_MISSING", elements - counts.keys()),
        ("BOM_EXTRA", counts.keys() - elements),
    ):
        if names_set:
            results.append(finding(code, sorted(names_set)))
    return results


def placement_ref(row: dict[str, Any]) -> str:
    return str(row.get("Designator", row.get("DESIGNATOR", ""))).strip()


def dnp_refs(rows: list[dict[str, Any]]) -> set[str]:
    return {
        ref
        for row in rows
        for ref in refs(row)
        if any(
            token in " ".join(str(v).upper() for v in row.values())
            for token in ("DNP", "DO NOT PUT", "NOT A COMPONENT")
        )
    }


def check_placement(
    bom: list[dict[str, Any]],
    placement: list[dict[str, Any]],
    elements: set[str],
    required_refs: set[str] | None = None,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    counts = Counter(placement_ref(row) for row in placement)
    if not placement and elements - dnp_refs(bom):
        results.append(finding("CPL_EMPTY", "No placements for a populated board"))
    if "" in counts:
        results.append(finding("CPL_EMPTY_REF", counts[""]))
    for code, names_set in (
        ("CPL_DNP", dnp_refs(bom) & counts.keys()),
        ("CPL_EXTRA", counts.keys() - elements),
        ("CPL_DUPLICATE", {name for name, count in counts.items() if count > 1}),
        ("CPL_MISSING", set(required_refs or ()) - dnp_refs(bom) - counts.keys()),
    ):
        if names_set:
            results.append(finding(code, sorted(names_set)))
    return results


def check_cpl_values(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Validate export fields only; this cannot establish true pick-and-place centroids."""
    results: list[dict[str, Any]] = []
    for row in rows:
        normalized = {
            re.sub(r"[^a-z]", "", str(key).lower()): value for key, value in row.items()
        }
        required = {"designator", "midxmm", "midymm", "layer", "rotation"}
        missing = required - normalized.keys()
        if missing:
            results.append(
                finding("CPL_SCHEMA", {"row": row.get("_row"), "missing": sorted(missing)})
            )
            continue
        for field in ("midxmm", "midymm", "rotation"):
            try:
                value = float(normalized[field])
                valid = math.isfinite(value)
            except (ValueError, TypeError):
                valid = False
            if not valid:
                results.append(
                    finding("CPL_NUMBER", {"ref": placement_ref(row), "field": field})
                )
        if str(normalized["layer"]).strip().lower() not in ("top", "bottom"):
            results.append(
                finding(
                    "CPL_LAYER",
                    {"ref": placement_ref(row), "value": normalized["layer"]},
                )
            )
    return results


def schematic_parts(path: Path) -> dict[str, dict[str, str | None]]:
    root = ET.parse(path).getroot().find("./drawing/schematic")
    if root is None:
        raise ValueError(f"{path}: not an EAGLE schematic")
    devices = {}
    for library in root.findall("./libraries/library"):
        for device_set in library.findall("./devicesets/deviceset"):
            for device in device_set.findall("./devices/device"):
                devices[
                    (library.get("name"), device_set.get("name"), device.get("name", ""))
                ] = device
    parts: dict[str, dict[str, str | None]] = {}
    for part in root.findall("./parts/part"):
        device = devices[
            (part.get("library"), part.get("deviceset"), part.get("device", ""))
        ]
        if device.get("package"):
            name = part.get("name")
            if name:
                parts[name] = {
                    "package": device.get("package"),
                    "value": part.get("value"),
                }
    return parts


def add_pad_net(mapping: dict[tuple[str, str], str], contact: tuple[str, str], net: str) -> None:
    if contact in mapping and mapping[contact] != net:
        raise ValueError(f"Conflicting nets for {contact}: {mapping[contact]} / {net}")
    mapping[contact] = net


def schematic_pad_nets(schematic: ET.Element | None) -> dict[tuple[str, str], str]:
    """Resolve saved pinrefs through device connects, including multi-pad pins."""
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
    mapping: dict[tuple[str, str], str] = {}
    for net in schematic.findall("./sheets/sheet/nets/net"):
        net_name = net.get("name", "")
        for ref in net.iter("pinref"):
            part_name = ref.get("part", "")
            device = parts[part_name]
            if not device.get("package"):
                continue
            connects = [
                c
                for c in device.findall("./connects/connect")
                if (c.get("gate"), c.get("pin")) == (ref.get("gate"), ref.get("pin"))
            ]
            if len(connects) != 1 or not connects[0].get("pad", "").strip():
                raise ValueError(f"Unresolved/ambiguous device connect: {ref.attrib}")
            for pad in connects[0].get("pad", "").split():
                add_pad_net(mapping, (part_name, pad), net_name)
    return mapping


def board_pad_nets(board: ET.Element | None) -> dict[tuple[str, str], str]:
    if board is None:
        raise ValueError("Missing EAGLE board")
    mapping: dict[tuple[str, str], str] = {}
    for signal in board.findall("./signals/signal"):
        sig_name = signal.get("name", "")
        for ref in signal.findall("contactref"):
            add_pad_net(mapping, (ref.get("element", ""), ref.get("pad", "")), sig_name)
    return mapping


def compare_pad_nets(
    schematic: dict[tuple[str, str], str],
    board: dict[tuple[str, str], str],
) -> list[dict[str, Any]]:
    return [
        finding(
            "CAD_PAD_NET",
            {
                "ref": ref,
                "pad": pad,
                "schematic": schematic.get((ref, pad)),
                "board": board.get((ref, pad)),
            },
        )
        for ref, pad in sorted(schematic.keys() | board.keys())
        if schematic.get((ref, pad)) != board.get((ref, pad))
    ]


def check_connectivity(schematic_path: Path, board_path: Path) -> list[dict[str, Any]]:
    return compare_pad_nets(
        schematic_pad_nets(ET.parse(schematic_path).getroot().find("./drawing/schematic")),
        board_pad_nets(ET.parse(board_path).getroot().find("./drawing/board")),
    )


def check_clock_pins(
    board: ET.Element | None,
    xdc: str,
    contract: dict[str, str] = CLOCK_NETS,
) -> list[dict[str, Any]]:
    """Check five explicit clock assignments against saved MainBoard U42 pads."""
    assignments: dict[str, list[str]] = {}
    for line in xdc.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        match = _PACKAGE_PIN_RE.fullmatch(line)
        if match:
            port_key = match[2] or match[3]
            assignments.setdefault(port_key, []).append(match[1])
        elif re.search(r"\bPACKAGE_PIN\b", line.split("#", 1)[0]):
            raise ValueError(f"Unsupported PACKAGE_PIN syntax; native review required: {line}")
    saved_nets = board_pad_nets(board)
    findings: list[dict[str, Any]] = []
    for port, net in contract.items():
        pads = sorted(
            pad for (ref, pad), signal in saved_nets.items() if ref == "U42" and signal == net
        )
        pins = assignments.get(port, [])
        if len(pads) != 1 or pins != pads:
            findings.append(
                finding(
                    "FPGA_CLOCK_PIN",
                    {"port": port, "net": net, "board_pads": pads, "xdc_pins": pins},
                )
            )
    return findings


def audit_fpga_clocks(repo: Path) -> dict[str, Any]:
    board = repo / BASE / "4_6_Schematics/MainBoard/RADAR_Main_Board.brd"
    xdc = repo / "9_Firmware/9_2_FPGA/constraints/xc7a50t_ftg256.xdc"
    return {
        "scope": "Five MainBoard U42 clock pins; no clock routing/timing approval",
        "inputs": {
            str(p.relative_to(repo)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (board, xdc)
        },
        "findings": check_clock_pins(
            ET.parse(board).getroot().find("./drawing/board"),
            xdc.read_text(encoding="utf-8"),
        ),
    }


def audit_board(repo: Path, source: str, production: str, bom_name: str) -> dict[str, Any]:
    cad = repo / BASE / "4_6_Schematics" / source
    prod = repo / BASE / "4_7_Production Files" / production
    paths = [cad.with_suffix(".sch"), cad.with_suffix(".brd"), prod / bom_name, prod / "CPL.xlsx"]
    sch = schematic_parts(paths[0])
    xml = ET.parse(paths[1]).getroot()
    board = xml.find("./drawing/board")
    if board is None:
        raise ValueError(f"{paths[1]}: missing board")
    elements = {e.get("name", ""): e for e in board.findall("./elements/element")}
    if not elements:
        raise ValueError(f"{paths[1]}: empty board")
    bom, cpl = read_xlsx(paths[2]), read_xlsx(paths[3])
    errors = check_bom(bom, set(elements)) + check_cpl_values(cpl)
    sch_nets = schematic_pad_nets(ET.parse(paths[0]).getroot().find("./drawing/schematic"))
    brd_nets = board_pad_nets(board)
    errors.extend(compare_pad_nets(sch_nets, brd_nets))
    for code, names_set in (
        ("CAD_BOARD_ONLY", elements.keys() - sch.keys()),
        ("CAD_SCHEMATIC_ONLY", sch.keys() - elements.keys()),
    ):
        if names_set:
            errors.append(finding(code, sorted(names_set)))
    for ref in sorted(elements.keys() & sch.keys()):
        for field in ("package", "value"):
            if sch[ref][field] is None:
                continue
            if elements[ref].get(field, "") != sch[ref][field]:
                errors.append(
                    finding(
                        "CAD_IDENTITY",
                        {
                            "ref": ref,
                            "field": field,
                            "board": elements[ref].get(field, ""),
                            "schematic": sch[ref][field],
                        },
                    )
                )
    rules = {p.get("name"): p.get("value") for p in board.findall("./designrules/param")}
    setup = rules.get("layerSetup") or ""
    layers = sorted({int(v) for v in re.findall(r"\d+", setup)})
    drills = Counter(v.get("drill", "") for v in board.findall("./signals/signal/via"))
    unresolved: list[dict[str, Any]] = []
    placed = {placement_ref(row) for row in cpl}
    required_placements: set[str] = set()
    for ref in sorted(elements):
        element = elements[ref]
        package = next(
            p
            for lib in board.findall("./libraries/library")
            if lib.get("name") == element.get("library")
            for p in lib.findall("./packages/package")
            if p.get("name") == element.get("package")
        )
        if package.findall("smd"):
            required_placements.add(ref)
        if ref not in placed and ref not in dnp_refs(bom):
            unresolved.append(
                {
                    "ref": ref,
                    "package": element.get("package"),
                    "smd_pads": len(package.findall("smd")),
                    "through_hole_pads": len(package.findall("pad")),
                }
            )
    errors.extend(check_placement(bom, cpl, set(elements), required_placements))
    return {
        "inputs": {
            str(p.relative_to(repo)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths
        },
        "eagle_file_version": xml.get("version"),
        "board_elements": len(elements),
        "schematic_physical_parts": len(sch),
        "schematic_connected_pads": len(sch_nets),
        "board_connected_pads": len(brd_nets),
        "bom_rows": len(bom),
        "cpl_rows": len(cpl),
        "layer_setup": setup,
        "copper_layers": layers,
        "copper_layer_count": len(layers),
        "via_drills_mm": dict(sorted(drills.items())),
        "minimum_via_drill_mm": min(map(float, drills)) if drills else None,
        "stored_layer19_wires": len(board.findall("./signals/signal/wire[@layer='19']")),
        "findings": errors,
        "assembly_disposition_required": unresolved,
    }


def _seg_point_dist(
    x1: float, y1: float, x2: float, y2: float, px: float, py: float
) -> float:
    dx, dy = x2 - x1, y2 - y1
    if dx == 0.0 and dy == 0.0:
        return math.hypot(px - x1, py - y1)
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))


def _seg_seg_dist(
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    x3: float,
    y3: float,
    x4: float,
    y4: float,
) -> float:
    def _orient(
        ax: float, ay: float, bx: float, by: float, cx: float, cy: float
    ) -> float:
        return (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)

    o1 = _orient(x1, y1, x2, y2, x3, y3)
    o2 = _orient(x1, y1, x2, y2, x4, y4)
    o3 = _orient(x3, y3, x4, y4, x1, y1)
    o4 = _orient(x3, y3, x4, y4, x2, y2)
    if (o1 * o2 <= 0.0) and (o3 * o4 <= 0.0):
        x_overlap = max(min(x1, x2), min(x3, x4)) <= min(max(x1, x2), max(x3, x4)) + 1e-9
        y_overlap = max(min(y1, y2), min(y3, y4)) <= min(max(y1, y2), max(y3, y4)) + 1e-9
        if x_overlap and y_overlap:
            return 0.0
    return min(
        _seg_point_dist(x1, y1, x2, y2, x3, y3),
        _seg_point_dist(x1, y1, x2, y2, x4, y4),
        _seg_point_dist(x3, y3, x4, y4, x1, y1),
        _seg_point_dist(x3, y3, x4, y4, x2, y2),
    )


def verify_mainboard_brd_xml(brd_path: Path) -> dict[str, Any]:
    """Verify MainBoard XML invariants and absence of +5V0_0 <-> GND Layer-1 short."""
    root = ET.parse(brd_path).getroot()
    board = root.find("./drawing/board")
    if board is None:
        raise ValueError(f"{brd_path}: missing <board> node")

    elements = board.findall("./elements/element")
    signals = board.findall("./signals/signal")
    crefs = [
        (c.attrib["element"], c.attrib["pad"], s.attrib["name"])
        for s in signals
        for c in s.findall("contactref")
    ]
    vias = [v for s in signals for v in s.findall("via")]
    wires = [w for s in signals for w in s.findall("wire")]
    via_drills = Counter(v.attrib["drill"] for v in vias)

    sig_gnd = board.find("./signals/signal[@name='GND']")
    sig_5v0 = board.find("./signals/signal[@name='+5V0_0']")
    short_hits: list[dict[str, Any]] = []
    if sig_gnd is not None and sig_5v0 is not None:
        wires_5v0 = [
            (
                w.attrib["layer"],
                float(w.attrib["x1"]),
                float(w.attrib["y1"]),
                float(w.attrib["x2"]),
                float(w.attrib["y2"]),
                float(w.attrib["width"]),
            )
            for w in sig_5v0.findall("wire")
        ]
        for w in sig_gnd.findall("wire"):
            lay = w.attrib["layer"]
            gx1 = float(w.attrib["x1"])
            gy1 = float(w.attrib["y1"])
            gx2 = float(w.attrib["x2"])
            gy2 = float(w.attrib["y2"])
            gw = float(w.attrib["width"])
            for l5, vx1, vy1, vx2, vy2, vw in wires_5v0:
                if lay != l5:
                    continue
                edge_clr = _seg_seg_dist(gx1, gy1, gx2, gy2, vx1, vy1, vx2, vy2) - (
                    gw / 2.0 + vw / 2.0
                )
                if edge_clr <= 0.0:
                    short_hits.append(
                        {
                            "layer": lay,
                            "gnd_wire": [gx1, gy1, gx2, gy2, gw],
                            "v5_wire": [vx1, vy1, vx2, vy2, vw],
                            "edge_clearance_mm": round(edge_clr, 6),
                        }
                    )

    errors: list[str] = []
    if len(elements) != 791:
        errors.append(f"MAINBOARD_ELEMENTS:{len(elements)}")
    if len(crefs) != 3453:
        errors.append(f"MAINBOARD_CONNECTED_PADS:{len(crefs)}")
    if via_drills.get("0.15", 0) != 1604:
        errors.append(f"MAINBOARD_MIN_DRILL_VIAS:{via_drills.get('0.15', 0)}")
    if short_hits:
        errors.append(f"MAINBOARD_SHORT_CIRCUIT:{len(short_hits)}")

    return {
        "eagle_version": root.attrib.get("version", ""),
        "elements": len(elements),
        "signals": len(signals),
        "connected_pads": len(crefs),
        "total_vias": len(vias),
        "min_drill_0p15_vias": via_drills.get("0.15", 0),
        "wires": len(wires),
        "short_hits": short_hits,
        "errors": errors,
        "valid": len(errors) == 0,
    }


def verify_patch_antenna_xml(
    brd_path: Path,
    sch_path: Path | None = None,
    mnt_path: Path | None = None,
) -> dict[str, Any]:
    """Verify Patch 8x16 SMA 14.34 mm pitch, feeder coaxiality, and 64-pad SCH<->BRD parity."""
    board = ET.parse(brd_path).getroot().find("./drawing/board")
    if board is None:
        raise ValueError(f"{brd_path}: missing <board> node")

    elements = sorted(
        board.findall("./elements/element"),
        key=lambda el: float(el.attrib["x"]),
    )
    feeder_wires_y18 = {
        round(float(w.attrib["x1"]), 4): (
            s.attrib["name"],
            float(w.attrib["x1"]),
            float(w.attrib["x2"]),
        )
        for s in board.findall("./signals/signal")
        for w in s.findall("wire")
        if abs(float(w.attrib["y1"]) - 18.0) < 1e-6
    }
    patch_col_centers = sorted(
        {
            round((float(r.attrib["x1"]) + float(r.attrib["x2"])) / 2.0, 4)
            for r in board.findall("./plain/rectangle")
        }
    )

    pitch_errors: list[dict[str, Any]] = []
    coax_errors: list[dict[str, Any]] = []
    for idx, el in enumerate(elements):
        name = el.attrib["name"]
        ex = float(el.attrib["x"])
        ey = float(el.attrib["y"])
        expected_x = round(15.0 + idx * 14.34, 4)
        dx = round(ex - expected_x, 6)
        if abs(dx) > 1e-6 or abs(ey - 18.0) > 1e-6:
            pitch_errors.append(
                {"ref": name, "x": ex, "y": ey, "expected_x": expected_x, "dx_mm": dx}
            )
        if round(ex, 4) not in feeder_wires_y18:
            coax_errors.append({"ref": name, "x": ex})

    brd_pad_nets = {
        (c.attrib["element"], c.attrib["pad"]): s.attrib["name"]
        for s in board.findall("./signals/signal")
        for c in s.findall("contactref")
    }
    non_gnd_crefs = [
        (s.attrib["name"], c.attrib["element"], c.attrib["pad"])
        for s in board.findall("./signals/signal")
        if s.attrib["name"] != "GND"
        for c in s.findall("contactref")
    ]

    sch_parity_ok = True
    sch_connected_pads: int | None = None
    if sch_path is not None and sch_path.exists():
        sch = ET.parse(sch_path).getroot().find("./drawing/schematic")
        if sch is None:
            raise ValueError(f"{sch_path}: missing <schematic> node")
        sch_pad_nets = schematic_pad_nets(sch)
        sch_connected_pads = len(sch_pad_nets)
        sch_parity_ok = sch_pad_nets == brd_pad_nets

    mnt_mismatches: list[str] = []
    if mnt_path is not None and mnt_path.exists():
        brd_xy = {
            el.attrib["name"]: (float(el.attrib["x"]), float(el.attrib["y"]))
            for el in elements
        }
        for line in mnt_path.read_text(encoding="utf-8").splitlines():
            parts_line = line.split()
            if not parts_line:
                continue
            ref, mx, my = parts_line[0], float(parts_line[1]), float(parts_line[2])
            if ref not in brd_xy or (
                abs(brd_xy[ref][0] - mx) > 1e-6 or abs(brd_xy[ref][1] - my) > 1e-6
            ):
                mnt_mismatches.append(ref)

    errors: list[str] = []
    if len(elements) != 16:
        errors.append(f"PATCH_ELEMENTS:{len(elements)}")
    if len(patch_col_centers) != 16:
        errors.append(f"PATCH_COLUMNS:{len(patch_col_centers)}")
    if pitch_errors:
        errors.append("PATCH_PITCH_OFFSET:" + ",".join(e["ref"] for e in pitch_errors))
    if coax_errors:
        errors.append("PATCH_FEEDER_COAX:" + ",".join(e["ref"] for e in coax_errors))
    if len(brd_pad_nets) != 64 or non_gnd_crefs:
        errors.append(f"PATCH_BRD_PADS:{len(brd_pad_nets)}")
    if not sch_parity_ok:
        errors.append("PATCH_SCH_BRD_MISMATCH")
    if mnt_mismatches:
        errors.append("PATCH_MNT_MISMATCH:" + ",".join(sorted(mnt_mismatches)))

    return {
        "sma_connectors": len(elements),
        "patch_columns": len(patch_col_centers),
        "board_connected_pads": len(brd_pad_nets),
        "schematic_connected_pads": sch_connected_pads,
        "sch_brd_parity": sch_parity_ok,
        "pitch_errors": pitch_errors,
        "coax_errors": coax_errors,
        "mnt_mismatches": mnt_mismatches,
        "errors": errors,
        "valid": len(errors) == 0,
    }


def scan_forbidden_terminology(root: Path = Path(".")) -> list[str]:
    """Scan markdown, text, yaml, and project-context docs for fabricated revision terms."""
    hits: list[str] = []
    check_paths: list[Path] = [
        root / "README.md",
        root / ".gitlab-ci.yml",
        root / "docs" / "POC_TO_MVP_ROADMAP.md",
        root / "docs" / "manufacturing" / "HF_HANDOFF.md",
        root / "docs" / "manufacturing" / "EMPIRICAL_UNBLOCK.md",
        root / "docs" / "manufacturing" / "ITERATION3_PRODUCTION_GATE.md",
        root / "docs" / "manufacturing" / "pcbway-requirements.md",
        root / "docs" / "manufacturing" / "CAD_DIFF_62D4C55_AND_PATCH_FIX.md",
    ]
    ctx_dir = root / "docs" / "project-context"
    if ctx_dir.exists():
        check_paths.extend(sorted(ctx_dir.glob("*")))

    seen: set[Path] = set()
    for p in check_paths:
        if p in seen or not p.is_file():
            continue
        seen.add(p)
        text = p.read_text(encoding="utf-8")
        if FORBIDDEN_TERM in text or "Rev-ECO1" in text:
            hits.append(str(p.relative_to(root)))
    return hits


def run_manufacturing_audit(
    state_path: Path = DEFAULT_STATE_PATH,
    repo_root: Path = Path("."),
) -> dict[str, Any]:
    """Execute manufacturing readiness audit and return structured report."""
    if not state_path.exists():
        raise FileNotFoundError(f"State file not found: {state_path}")

    state = json.loads(state_path.read_text(encoding="utf-8"))
    clocks_report = evaluate_fpga_clocks(state_path)
    forbidden_hits = scan_forbidden_terminology(repo_root)

    gates: dict[str, str] = state.get("gates", {})
    blockers: list[dict[str, str]] = []

    for gate_id, status in sorted(gates.items()):
        if status != "PASS":
            blockers.append({"gate": gate_id, "status": status})

    if forbidden_hits:
        blockers.append(
            {
                "gate": "G00_terminology_hygiene",
                "status": f"FAIL_FORBIDDEN_TERM:{','.join(forbidden_hits)}",
            }
        )

    open_inv = state.get("open_investigations", {})
    sequence_valid = (
        open_inv.get("first_wave") == [9, 10, 11]
        and open_inv.get("dependent_on_first_wave") == [12]
        and open_inv.get("independent_parallel") == [13, 14]
    )
    if not sequence_valid:
        blockers.append(
            {
                "gate": "G00_investigation_sequence",
                "status": "FAIL_INVALID_SEQUENCE",
            }
        )

    cad_xml_checks: dict[str, Any] = {}
    mb_brd = repo_root / MAINBOARD_BRD_REL
    if mb_brd.exists():
        mb_res = verify_mainboard_brd_xml(mb_brd)
        cad_xml_checks["mainboard_brd"] = mb_res
        if not mb_res["valid"]:
            blockers.append(
                {
                    "gate": "G03_mainboard_cad_xml",
                    "status": "FAIL:" + ";".join(mb_res["errors"]),
                }
            )

    patch_brd = repo_root / PATCH_BRD_REL
    if patch_brd.exists():
        patch_sch = repo_root / PATCH_SCH_REL
        patch_mnt = repo_root / PATCH_MNT_REL
        patch_res = verify_patch_antenna_xml(
            patch_brd,
            sch_path=patch_sch if patch_sch.exists() else None,
            mnt_path=patch_mnt if patch_mnt.exists() else None,
        )
        cad_xml_checks["patch_8x16_brd"] = patch_res
        if not patch_res["valid"]:
            blockers.append(
                {
                    "gate": "G03_patch_8x16_cad_xml",
                    "status": "FAIL:" + ";".join(patch_res["errors"]),
                }
            )

    boards_inventory: dict[str, Any] = {}
    fpga_clocks_pin_inventory: dict[str, Any] | None = None
    source_commit: str | None = None
    if (repo_root / BASE / "4_6_Schematics").exists():
        for name, spec in BOARDS.items():
            boards_inventory[name] = audit_board(repo_root, *spec)
        if (repo_root / "9_Firmware/9_2_FPGA/constraints/xc7a50t_ftg256.xdc").exists():
            fpga_clocks_pin_inventory = audit_fpga_clocks(repo_root)
        try:
            source_commit = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=repo_root, text=True
            ).strip()
        except (OSError, subprocess.SubprocessError):
            source_commit = None

    return {
        "schema_version": state.get("schema_version", "1.3.0"),
        "project": state.get("project", "PLFM_RADAR"),
        "variant": state.get("variant", "AERIS-10N Nexus R0.1"),
        "source_commit": source_commit,
        "checkpoint_branch": state.get("checkpoint_branch", "checkpoint/rnd-2026-10-24"),
        "checkpoint_commit": state.get("checkpoint_commit", "a4840b40"),
        "upstream_base_commit": state.get(
            "upstream_base_commit", "749bd0f86a07a28a86347d8ce9c141e601057c40"
        ),
        "readiness": state.get("readiness", "Draft"),
        "manufacturing_status": state.get("manufacturing_status", READINESS),
        "firmware_flash_status": state.get("firmware_flash_status", "NOT_FOR_FLASH"),
        "included_boards_count": len(state.get("included_boards", [])),
        "completed_iterations": state.get("completed_iterations", []),
        "open_investigations": open_inv,
        "sequence_valid": sequence_valid,
        "forbidden_term_hits": forbidden_hits,
        "fpga_clocks_summary": clocks_report,
        "cad_xml_checks": cad_xml_checks,
        "boards": boards_inventory,
        "fpga_clocks": fpga_clocks_pin_inventory,
        "active_blockers": blockers,
        "blocker_count": len(blockers),
        "release_ready": len(blockers) == 0,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run PLFM_RADAR AERIS-10N manufacturing and R&D readiness gate audit."
    )
    parser.add_argument(
        "--state",
        type=Path,
        default=None,
        help="Path to docs/project-context/state.json",
    )
    parser.add_argument(
        "--repo-root",
        "--repo",
        dest="repo_root",
        type=Path,
        default=REPO_ROOT,
        help="Repository root directory",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("plfm-audit-report.json"),
        help="Output JSON report path",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Return exit code 1 if any manufacturing or FPGA release blocker remains open",
    )
    args = parser.parse_args(argv)

    repo_root = args.repo_root.resolve()
    state_path = args.state if args.state is not None else (repo_root / DEFAULT_STATE_PATH)

    report = run_manufacturing_audit(state_path=state_path, repo_root=repo_root)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        encoded = json.dumps(report, indent=2, ensure_ascii=False)
        args.output.write_text(f"{encoded}\n", encoding="utf-8")

    msg = (
        f"[audit] status={report['manufacturing_status']} "
        f"blockers={report['blocker_count']} sequence_valid={report['sequence_valid']} "
        f"output={args.output}\n"
    )
    sys.stdout.write(msg)

    if args.strict and not report["release_ready"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
