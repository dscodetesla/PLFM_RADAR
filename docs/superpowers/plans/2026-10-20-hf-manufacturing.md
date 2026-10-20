# HF manufacturing recovery implementation plan

> Execute inline using superpowers:executing-plans and test-driven-development. Final independent review follows the executable changes.

Goal: repair demonstrated assembly inventory defects and make manufacturing gaps reproducible for AERIS-10N Nexus.
Architecture: immutable upstream CAD baseline plus deterministic read-only EAGLE/XLSX audit, narrowly corrected existing BOM/CPL, and explicit native/factory gates. Static evidence never implies a production release.
Tech stack: Python 3.12 standard library, EAGLE XML, XLSX, GitHub Actions.
Spec: user request of 2026-10-20 and `docs/manufacturing/HF_HANDOFF.md` (written with the evidence).

## Constraints and rulings
- Baseline main 749bd0f86a07a28a86347d8ce9c141e601057c40; develop 2a9f7161a07c6cde6dc3faa033381d684aac41ab has older CAD and divergent firmware. Do not import an unrelated branch wholesale.
- Four boards: Main, Frequency Synthesizer, Power, Patch 8x16. PA and waveguide excluded from this procurement configuration; originals retained.
- No inferred MPN, no CAM editing, no fabricated native DRC or test results.
- CONTRIBUTING requires complete local CI before commit. Missing tools are a gate, not a waiver. Preserve a review patch if that gate cannot be met.
- Existing clone was clean; separate worktree isolates edits. Execute the user's authorized fixes without an extra approval pause.

## Review focus
Duplicates vs missing refs; DNP vs artwork/THT; schematic symbols without packages; mismatching footprint/value; absent/corrupt inputs and misleading success status.

## Task 1: Reproducible evidence
- [x] Add `tools/manufacturing/audit.py` and `tools/manufacturing/tests/test_audit.py` with standard-library unittest; watch adversarial fixtures fail first.
- [x] Audit physical schematic devices, board element identity, grouped BOM quantities/unique refs, DNP intersection, CPL refs/coordinates, layer/via inventory.
- [x] Run baseline audit and preserve JSON evidence with input SHA256 and Git revision.

## Task 2: Inventory corrections
- [x] Assert expected Main C352/C353 cardinality, counts 73/8, no DNP placements, Patch count 16. Observe baseline failure.
- [x] Correct only Main BOM A13/A15/E15, Patch BOM A2 and three DNP CPL rows. Do not approve electrical/mechanical fit by changing these inventories.
- [x] Run regression; compare all workbook values/formulas against baseline, allowing only named changes.

## Task 3: Gate and handoff
- [x] Add CI audit/tests and strict manual manufacturing gate; failures remain visible.
- [x] Write dated manufacturer requirements, per-board profile, GAP ownership/evidence and bring-up sequence; link from README.
- [x] Run available suites and explicitly record missing gates. Independent read-only review of changes.
- [ ] Commit/push after the repository's full-CI gate passes (blocked: ruff/Icarus/sfw unavailable). Review artifacts delivered separately.

## Execution ledger

Task 1: complete. TDD red→green; physical devices resolved through library package mapping. Omitted EAGLE value uses library default and is not falsely compared to empty text.
Task 2: complete. Three workbooks changed; allowed cell/row preservation verified. Empty shared-string import defect caught by independent comparison and corrected before delivery.
Task 3: review/report complete; remote integration blocked by CONTRIBUTING full-CI requirement. No waiver inferred. Independent reviewer found two CPL validation gaps; both reproduced and fixed, 10 audit tests pass.
Ruling: no speculative CAD edits without native validation; remaining hardware findings stay OPEN. No manufacturing archive or approval fabricated.

## Iteration 2 — empirical unblock

- [x] Re-run quick selftest; recover exact pin/net mapping and official AMD clock pin classes.
- [x] TDD connectivity audit, Power X36 source repair, unchanged-original-XML proof.
- [x] TDD clock mismatch check; fail-fast 50T build guard; run available Python suite.
- [x] Final fresh-context review; versioned delivery prepared after fix pass.

Ruling: narrow the previous no-CAD-edits ruling: restore X36 as a source-level recovery candidate, because PCB/BOM/device mapping agree and every other saved pad/net already matches. Native validation still required; risk if wrong: EAGLE interpretation/layout issue caught before manufacturing.
Ruling: retain physical clock source and XDC as an explicit blocker; do not claim a native routing solution without native tools. Cost: fabrication remains blocked until the ECO is implemented and validated.
Task 4: connectivity tests RED (X36 pads missing) → GREEN after only part + second sheet addition. 16 manufacturing tests pass; 226 Python tests pass, 9 skipped. Tcl preflight exercised with embedded Tcl, not Vivado.
Task 5: bounded read-only PATH check on three online Linux hosts finds no required sfw/ruff/Icarus/EAGLE/Vivado tools. No remote writes or dependency installation. Full CI gate retained.

Final: fixed parser false-pass — alternative XDC overrides and unsupported syntax tests RED→GREEN; 18 manufacturing tests / 228 Python tests pass, 9 skipped. Fresh reviewer found no additional important defects. No deferred minor findings.
