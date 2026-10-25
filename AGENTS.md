# PLFM_RADAR cloud work

This repository contains radar firmware, host GUIs, hardware documentation and tests.
Check the actual git remote, full HEAD, branch and working tree before work; README
upstream links do not establish the current fork. Keep changes on a task branch.

For cloud/MCP integration use `.agents/skills/cloud-mcp-pilot/SKILL.md` and
`docs/cloud-mcp-pilot.md`. Use `.agents/skills/artifact-evidence/SKILL.md` for
artifact byte/hash work. Skills are instructions, not installed tools or credentials.

Use the existing `pyproject.toml` dev group and committed `uv.lock`, in an isolated
`.venv`; never install into the global interpreter. Inspect scripts and relevant
imports before executing them. Prefer focused tests; mock USB tests do not validate
hardware. Do not run GUI live modes, RF transmission, flash, Vivado/Vitis builds,
or host shell operations as part of cloud tests.

Discover tools in the current session. Agent plugin tools and a Python/shell MCP
client are separate routes. Never copy credentials or assume that connected devices
authorize host tasks. Keep tunnels, VPN, firewall and persistent access unchanged.
Do not push, merge or publish an environment template unless explicitly requested.

Record full commit, workspace, tool/arguments, measured elapsed time, actual outcome
and evidence hashes. Use PASS/FAIL/BLOCKED/NOT_RUN/SKIP for acceptance. A timeout or
cancel does not prove host termination; reconcile before retry. Never report a
names-only artifact listing as bytes, or a local prototype as host deployment.
