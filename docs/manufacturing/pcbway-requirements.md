# PCBWay HF fabrication and assembly handoff requirements

2026-10-20. Configuration: Nexus, four boards. Status: DRAFT / NOT_FOR_MANUFACTURE.
This document is a review checklist, not a factory approval or RFQ sent to a vendor.

## Per-board decision needed before final CAM

| Board | Copper layers from CAD | Min CAD via drill | Requested manufacturing review |
|---|---:|---:|---|
| Main | 10 | 0.15 mm | Hybrid HF build-up, RF layer reference, fine drill process |
| Synth | 6 | 0.15 mm | Low-loss/clock layout stack, reference continuity, drill process |
| Power | 2 | 0.15 mm | Suitable material/copper for current/thermal duty; drill capability |
| Patch 8×16 | 4 | 0.6 mm | RF laminate thickness/Dk, antenna geometry, connector assembly |

No stackup has been approved in this session. For EACH board obtain: exact laminate
and bondply part numbers; ordered copper layer map; dielectric and finished copper
thicknesses/tolerances; overall thickness; Dk/Df model/frequency/test method; copper
roughness; mask and finish; plated/unplated hole classes; via spans/fill/tenting;
minimum track/space, annular ring and drill-to-copper; aspect ratios; route/outline
tolerance; board/panel dimensions, fiducials and assembly rails.

Controlled impedance must identify actual net classes and reference layers, target
and tolerance, coupon geometry, testing method and delivered report. The existing
`PCBWay_Impedance_Note_RO4350B_h0p102mm.pdf` proposes 50 ohm ±10%, differential
100 ohm ±8%, h=0.102 mm and starting widths. These are design inputs, NOT an approved
ten-layer stackup or measured values. Do not permit automatic CAM line-width changes
to antenna/feed/filter geometry without RF review. Any approved stack change
invalidates dependent geometry/impedance evidence until rechecked.

## Required submitted files after blockers close

- One board/revision per clearly named Gerber/drill archive: ordered copper,
  solder mask/paste, legend as required, single unambiguous outline, drill map and
  explicit PTH/NPTH handling. CAM units/origin/format and source revision recorded.
- Schematic PDF, native sources and libraries, exported netlist for reconciliation,
  fabrication drawing with dimensions/stackup/tolerances, signed exception list.
- BOM: unique refs, Qty equal to expanded refs, exact manufacturer/MPN/package,
  rating, explicit DNP, customer-supplied vs turnkey procurement and substitution policy.
- CPL: fitted automated placements only, units mm, origin and rotation convention;
  no DNP or artwork. Separate manual/THT/hybrid list and assembly drawing/pin1.
- Firmware/config/programming assets with exact board target and validation state;
  test procedure, fixture requirements and explicit acceptance limits.
- Input/export SHA256 manifest. Factory review tied to exact archive hash. Preserve
  previous revisions; no hand edits to Gerber/drill/CPL to hide CAD defects.

## Acceptance stages

Draft → native source/ERC/DRC verified → complete quote review → factory stackup/DFM
approved → PCBA sourcing/placement/test approved → first article accepted → system
validated. Quote request can precede physical validation, but cannot claim measured
system performance. Full-CI success also does not advance factory approval.

The current inventory checker is a prerequisite only. `--strict` currently fails
Power X36. Additional open gates G02–G10 in [HF_HANDOFF.md](HF_HANDOFF.md) must be
reviewed explicitly; the script does not evaluate them.

## Vendor sources, checked 2026-10-20

- https://www.pcbway.com/pcb_prototype/What_is_High_Frequency__HF__PCB_.html
- https://www.pcbway.com/advanced-pcb-capabilities.html
- https://www.pcbway.com/smt_ordering_guide.html
- https://jlcpcb.com/pcb-fabrication/high-frequency-pcb

JLCPCB's current public HF table lists two copper layers and 0.2 mm minimum drill.
Treat a custom multilayer offer as unconfirmed until received for these boards.
Do not silently select a standard two-layer Rogers stack or reduce the design scope
to make an online order form accept the files.
