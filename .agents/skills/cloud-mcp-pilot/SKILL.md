---
name: cloud-mcp-pilot
description: Prepare and audit bounded agent-mediated CAD MCP inventory jobs from this repository.
---

Read `docs/cloud-mcp-pilot.md`, `config/pilot.json`, and `tools/pilot.py`.
Verify clean commit identity with the prepare command. Keep its job workspace
outside the checkout. Discover the exact configured tool in the current session.
Only invoke a tool authorized for this task; missing tool/auth means BLOCKED, not
fallback to generic host shell. Status and artifact listing are read-only. Scilab
smoke is a fixed arithmetic operation and requires task scope covering a smoke.

The profile is an agent routing contract, not a tool installer or live dispatcher.
Capture raw MCP response only for these reviewed non-secret tools, actual elapsed
time, and invocation timestamps in the job workspace. Use the check command to
validate response semantics; do not pass historical responses off as a new call.
If deadline expires, mark TIMED_OUT with remote outcome UNKNOWN. No auto-retries.
Resource fields are requested ceilings, not host enforcement. Keep heavy jobs disabled.

Separate cloud tests, actual plugin calls, artifact transport, host deployment,
EDA discovery and Vitis acceptance. Current inventory success never implies the
other layers passed. Preserve failures and report exact missing action/permission.
