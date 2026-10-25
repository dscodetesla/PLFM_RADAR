# Cloud and existing MCP pilot

This is a small **agent-mediated workflow**, not a scheduler or a new MCP service.
It reuses `pyproject.toml`, the existing Python CI job and the already connected CAD
plugins. `config/pilot.json` names the exact host tools and requested job limits.
No URL, token, host shell command, tunnel or access change is configured.

## Reproducible cloud setup

From the repository root, with uv available (validated with uv 0.12.19):

```bash
UV_CACHE_DIR=/workspace/.cache/uv uv sync --locked --group dev --no-install-project --no-python-downloads
.venv/bin/python -m pytest tests/test_pilot.py -q
.venv/bin/ruff check tools tests/test_pilot.py
```

`.python-version` records the tested Python 3.12.14. If it is absent on another
machine, provision Python through that environment's approved setup rather than
removing the lock guard. `uv.lock` was resolved from `https://pypi.org/simple` and
includes registry URLs and SHA256 wheel/sdist hashes. Initial versions: numpy
2.5.4, h5py 3.16.0, pytest 9.1.1, ruff 0.17.2; the lock is authoritative.
The new `.venv` does not inherit global site packages. No GUI, USB or FPGA tools
are needed for the pilot. Updating versions requires re-resolving and testing the
lock, not editing pins or hashes by hand.

Existing headless tests were reviewed (including imports). Their connections use
`mock=True`; exclude the one actual USB enumeration test regardless of dependencies:

```bash
.venv/bin/python -m pytest 9_Firmware/9_3_GUI/test_v7.py 9_Firmware/9_3_GUI/test_GUI_V65_Tk.py --deselect=9_Firmware/9_3_GUI/test_v7.py::TestHardwareReExports::test_stm32_list_devices_no_crash -q
```

Optional Qt workers and absent co-sim fixtures may skip; report those explicitly.
The existing acquisition test can pass without a frame after a mock timeout; its
success is not hardware acquisition acceptance. No existing build scripts are part
of this setup. Existing whole-repository lint/FPGA jobs remain separate gates.

## Agent route and job observation

1. Check the actual remote, full HEAD and clean working tree. Keep task changes on
   a local task branch. `prepare` rejects tracked or untracked changes and creates
   a unique cloud workspace outside the checkout:

   ```bash
   mkdir -p /workspace/plfm-pilot-jobs
   .venv/bin/python -m tools.pilot prepare --jobs-root /workspace/plfm-pilot-jobs --host dell_t3500 --operation cad_environment_status
   ```

2. Discover the exact tool from the profile in the current agent session. Only
   invoke task-authorized operations, with `{}` arguments. Example runtime call:
   `tools.mcp__codex_apps__cad_cae_dell_t3500_cad_environment_status({})`.
   This is an agent tool expression, **not a Python function or shell command**.
   Missing tool or authentication means BLOCKED; no generic-host fallback.
3. Save the exact response as `response.json` in that job directory. Record UTC
   invocation start/end, elapsed seconds and actual tool name separately in
   `capture.json`. Preserve all failure/late responses without automatic retries.
   Only the reviewed non-secret inventory/smoke tools are allowed in this profile.
4. Validate the already captured response using actual paths/time from step 3:

   ```bash
   .venv/bin/python -m tools.pilot check --job /workspace/plfm-pilot-jobs/JOB_ID/job.json --response /workspace/plfm-pilot-jobs/JOB_ID/response.json --elapsed-seconds MEASURED_SECONDS
   ```

   Replace placeholders; redirect stdout to that job's report file if wanted.
   `check` never invokes a tool. Exit 0 means accepted captured evidence, 1 means
   failed/late evidence, 2 means invalid local input. It cannot authenticate a
   captured file or prove an actual MCP call. Preserve `capture.json` and raw
   response with the report. `evidence_sha256` hashes Python `json.dumps(response,
   allow_nan=False).encode()`; this normalized-object digest is not the raw file
   hash. Hash raw files separately for transfer integrity.

The commit identifies the clean **cloud source**; fixed host status/smoke tools do
not run that checkout. `host_project_commit=null`, `host_workspace_verified=false`
and `limits_enforced_on_host=false` are intentional. Preparing a job does not
checkout a host revision. Do not concurrently mutate the trusted cloud checkout
while preparing/observing a job; this is not an immutable filesystem sandbox.

Status acceptance requires all three CAD executables available, integer version
exit codes 0 and nonempty version output. Scilab acceptance requires integer exit
0, `passed=true` and numeric stdout 6. Artifact listing accepts structured names
only; it never asserts that bytes exist in cloud. Runtime schemas remain authoritative.

## State and limit contract

`PREPARED → RUNNING → SUCCEEDED/FAILED/TIMED_OUT/CANCELLED/UNKNOWN`;
`PREPARED → BLOCKED/NOT_RUN`. Terminal observations cannot be restarted or
completed again through the transition methods. Reports use the acceptance
vocabulary PASS/FAIL/BLOCKED/NOT_RUN; test-level SKIP is recorded separately.

Deadline equality counts as timeout; a late successful response cannot turn that
observation into success. Failed or timed-out bounded serializable responses retain
their digest. Unknown/oversized/unserializable evidence has no digest. Elapsed time
is supplied by the capturing agent and retained; invocation timestamps belong in
the caller capture. Cancellation/timeout/error leaves remote outcome UNKNOWN:
**no host termination or safe retry is implied**. Reconcile externally before retry.

Ceilings: timeout 1–60 s (default 30), response/artifact at most 1 MiB, CPU request
1, memory request at most 512 MiB, one job at a time. These are validated metadata,
not OS-enforced host limits. The code has no process runner, timer, lock manager,
PID cancellation, descendant termination or distributed concurrency enforcement.
It does enforce byte limits for its local reads. Heavy builds remain disabled;
do not claim resource isolation or restart recovery.

## Artifact bytes/hash gap

The advertised CAD tools currently provide names-only `cad_list_artifacts`, with
no byte download, signed retrieval handle or hash tool. Generic remote file tools
are outside this pilot's authorization. Existing demo filenames do not establish
new output provenance. Agent plugin access works independently of this gap.

`tools.pilot.read_artifact(root, name)` is a **Linux cloud-tested prototype** for a
possible future scoped reader. The root is a trusted administrator-selected
directory with trusted ancestors, not a client-selected arbitrary path. The reader
allows only a simple STL/SCAD basename; opens relative to a held directory descriptor;
rejects symlinks, hardlinks, nonregular/empty/oversized files; caps bytes; checks fstat
metadata for concurrent changes; returns actual bytes and their SHA256.

Tests include traversal, absolute paths, symlink escape, directory/FIFO, limits,
growth and replacement races, and an independent digest of known fixture bytes.
This does not defend against a privileged malicious producer controlling the
trusted filesystem or authenticate content. It does not expose a network service,
authorize reading existing host files, or close the **remote transport** gap.

To deploy later: explicitly approve one named host and trusted demo output root,
a read-only basename/byte-bounded tool using existing auth, and its discovery
through the existing plugin. Validate real returned bytes/hash separately after
deployment. That changes the host tool surface and is outside this local task.

## Acceptance layers and remaining permissions

| Layer | Required evidence | Current baseline |
|---|---|---|
| Cloud contracts / adapter | Actual unit and negative tests, versions, exit codes | Locally testable |
| Agent-tool CAD inventory | Actual tool response and semantic checks | Prior real calls PASS |
| Agent-tool Scilab smoke | Actual exit 0, output 6 | One prior real call PASS on dell |
| Host artifact transport | Actual received bytes, size, independent SHA256 | BLOCKED: no scoped tool |
| Host adapter deployment | Approved installation + live negative tests | NOT_RUN |
| Local EDA discovery | Advertised authorized local EDA tools + read-only call | BLOCKED: not advertised here |
| Vitis RPC/create-platform | Separate approved bounded job + resulting artifacts | NOT_RUN |

Tool-name/description searches found no local EDA/Vivado/Vitis tool. Flux EDA is
a different service; CAD success is not EDA acceptance or evidence that an EDA
server is offline. Do not repair discovery through generic shell or new credentials.
Need existing EDA plugin/tool exposure by its owner before a scoped read-only call.
The historical Vitis RPC create-platform issue remains unverified.

The optional direct Python/shell MCP route is disabled, not a blocker for the
agent route. No published cloud template, tunnel, VPN, firewall or credential
changes are part of this patch. No push/merge or host deployment is authorized.
