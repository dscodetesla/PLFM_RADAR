# Workbench integration checkpoint

This branch preserves and integrates the engineering workbench into the active
PLFM_RADAR repository for review. It does not approve fabrication or claim a
working physical radar prototype.

## Provenance

- Target baseline: `dscodetesla/PLFM_RADAR` commit
  `749bd0f86a07a28a86347d8ce9c141e601057c40` (`main`).
- Source archive: private `dscodetesla/PLFM_RADAR-workbench`, commit
  `60bf8e6091a0db93ba0e52a6fbacf7a2e1355620` (`main`).
- Workbench manifest: all 53 listed files passed SHA256 verification before
  import. The original dated ZIP checkpoints, reports, evidence, and workbook
  previews are preserved under `workbench-archive/2026-10-20/`.
- The v2 cumulative source patch was checked against the target baseline and
  applied to this integration branch. The imported source changes are also
  available as normal project paths; the archived patch remains the historical
  record of the overlay.

## Checkpoints and rollback

The branch is `integration/workbench-2026-10-20`. Its history separates the
workbench archive from the applied source overlay. The import checkpoint is
marked by tag `checkpoint/workbench-2026-10-20` after integration.

To inspect the exact state, use the branch or tag. To return a local checkout
to the original upstream baseline, switch to `main` at the recorded baseline
commit. Do not reset a dirty working tree; preserve local edits before changing
branches. The workbench repository remains an unchanged private source archive.

## Readiness boundary

Status remains **NOT_FOR_MANUFACTURE**. Static audit/tests do not replace native
EAGLE ERC/DRC, FPGA implementation/timing, approved per-board stackups, fresh
CAM review, factory DFM/DFA, or measured hardware bring-up. The open blockers
and acceptance criteria are tracked in `EMPIRICAL_UNBLOCK.md` and
`HF_HANDOFF.md`. No vendor order or manufacturing submission was made.
