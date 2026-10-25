---
name: artifact-evidence
description: Verify actual bounded artifact bytes and provenance without broad host filesystem access.
---

Use only an existing scoped tool that returns bytes or an approved retrieval handle.
`cad_list_artifacts` returns names only. Do not fetch guessed URLs or use generic
host filesystem/shell tools to bypass a missing artifact API.

The Linux `tools.pilot.read_artifact` function is a local prototype. Its root must
be administrator-selected, isolated and not writable by an adversary; only simple
STL/SCAD basenames are accepted. It uses openat/no-follow, fstat and a byte bound.
It is not deployed, not an MCP endpoint, and not authorization to read host files.
Do not expose its root argument as an arbitrary client filesystem parameter.

Hash the bytes actually received and compare with the source hash if a trusted
source provides one. Record size, hash, tool/host provenance and commit association.
An ordinary digest provides integrity comparison, not authenticity. Missing bytes
means transport BLOCKED even if local adapter tests PASS. Host deployment and any
new scoped transfer capability need a separate concrete approval.
