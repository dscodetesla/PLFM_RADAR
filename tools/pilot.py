"""Offline contracts for agent-mediated MCP calls, not a host execution service."""

import argparse
import hashlib
import json
import math
import os
import re
import stat
import subprocess
import sys
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path

HOSTS = ("live", "x99mg", "dell_t3500")
OPERATIONS = ("cad_environment_status", "cad_list_artifacts", "scilab_batch_smoke_test")
MAX_BYTES = 1024 * 1024
TERMINAL = {"SUCCEEDED", "FAILED", "BLOCKED", "NOT_RUN", "TIMED_OUT", "CANCELLED", "UNKNOWN"}


def bounded_number(value, low, high):
    return type(value) in (int, float) and math.isfinite(value) and low <= value <= high


def tool_name(host, operation):
    if host not in HOSTS or operation not in OPERATIONS:
        raise ValueError("host/operation is outside the pilot allowlist")
    return f"mcp__codex_apps__cad_cae_{host}_{operation}"


@dataclass(frozen=True)
class Job:
    job_id: str
    commit: str
    workspace: str
    host: str
    operation: str
    timeout_seconds: int = 30
    max_output_bytes: int = MAX_BYTES
    max_parallel_jobs: int = 1
    cpu_limit: int = 1
    memory_mib: int = 512

    def __post_init__(self):
        if not re.fullmatch(r"[0-9a-f]{32}", self.job_id):
            raise ValueError("job_id must be a UUID hex string")
        if not re.fullmatch(r"[0-9a-f]{40}", self.commit):
            raise ValueError("commit must be a full git SHA-1")
        path = Path(self.workspace)
        if not path.is_absolute() or ".." in path.parts or path.name != self.job_id:
            raise ValueError("workspace must be absolute, unique per job, without traversal")
        tool_name(self.host, self.operation)
        limits = (
            (self.timeout_seconds, 1, 60),
            (self.max_output_bytes, 1, MAX_BYTES),
            (self.cpu_limit, 1, 1),
            (self.memory_mib, 1, 512),
            (self.max_parallel_jobs, 1, 1),
        )
        if any(type(v) is not int or not low <= v <= high for v, low, high in limits):
            raise ValueError("limits exceed the bounded pilot contract")


def prepare(repo, jobs_root, host, operation):
    """Pin a clean local revision; only create a new cloud job directory."""
    repo = Path(repo).resolve(strict=True)
    head = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip()
    dirty = subprocess.check_output(
        ["git", "-C", str(repo), "status", "--porcelain", "--untracked-files=normal"], text=True
    )
    if dirty:
        raise ValueError("commit identity requires a clean checkout (including untracked files)")
    root = Path(jobs_root).resolve(strict=True)
    if root == repo or repo in root.parents:
        raise ValueError("job output root must be outside the checkout")
    job_id = uuid.uuid4().hex
    job = Job(job_id, head, str(root / job_id), host, operation)
    Path(job.workspace).mkdir(mode=0o700)
    (Path(job.workspace) / "job.json").write_text(json.dumps(asdict(job), indent=2) + "\n")
    return job


def payload(response, max_bytes):
    """Validate the envelope before inspecting structured/text JSON evidence."""
    raw = json.dumps(response, allow_nan=False).encode()
    if len(raw) > max_bytes:
        raise ValueError("MCP response exceeds the byte limit")
    if not isinstance(response, dict) or response.get("isError") is not False:
        raise ValueError("MCP response is an error or lacks explicit isError=false")
    value = response.get("structuredContent")
    if value is None:
        blocks = response.get("content", [])
        if len(blocks) != 1 or blocks[0].get("type") != "text":
            raise ValueError("expected one JSON text block or structuredContent")
        value = json.loads(blocks[0]["text"])
    if not isinstance(value, dict):
        raise ValueError("MCP payload must be an object")
    return value, hashlib.sha256(raw).hexdigest()


def accept(job, response):
    value, digest = payload(response, job.max_output_bytes)
    if job.operation == "scilab_batch_smoke_test":
        if type(value.get("exit_code")) is not int or value["exit_code"] != 0:
            raise ValueError("Scilab exit_code must be integer zero")
        if value.get("passed") is not True or float(value.get("stdout", "nan")) != 6:
            raise ValueError("Scilab semantic acceptance requires passed=true and output 6")
    elif job.operation == "cad_environment_status":
        for name in ("openscad", "scilab", "freecad"):
            item = value.get(name, {})
            version = item.get("version", {})
            if (
                item.get("available") is not True
                or type(version.get("exit_code")) is not int
                or version["exit_code"] != 0
                or not any(
                    isinstance(version.get(k), str) and version[k].strip()
                    for k in ("stdout", "stderr")
                )
            ):
                raise ValueError(f"missing/failed version check: {name}")
    elif not isinstance(value.get("result"), list) or not all(
        isinstance(name, str) for name in value["result"]
    ):
        raise ValueError("artifact listing requires structured result names; not file bytes")
    return digest


@dataclass
class Observation:
    """State/evidence validation only. No dispatch, timer, lock or remote cancellation."""

    job: Job
    state: str = "PREPARED"
    remote_outcome: str = "NOT_STARTED"
    evidence_sha256: str | None = None
    reason: str | None = None
    elapsed_seconds: float | None = None

    def start(self):
        if self.state != "PREPARED":
            raise ValueError("only PREPARED may become RUNNING")
        self.state = "RUNNING"
        self.remote_outcome = "UNKNOWN"

    def finish(self, response, elapsed_seconds):
        if self.state != "RUNNING":
            raise ValueError("finish requires RUNNING; terminal states are immutable")
        if not bounded_number(elapsed_seconds, 0, 86400):
            raise ValueError("elapsed_seconds must be finite and nonnegative")
        self.elapsed_seconds = elapsed_seconds
        try:
            raw = json.dumps(response, allow_nan=False).encode()
            if len(raw) <= self.job.max_output_bytes:
                self.evidence_sha256 = hashlib.sha256(raw).hexdigest()
        except (ValueError, TypeError, OverflowError, RecursionError):
            pass
        if elapsed_seconds >= self.job.timeout_seconds:
            self.stop("TIMED_OUT", "deadline exceeded; reconcile before any retry")
            return
        try:
            self.evidence_sha256 = accept(self.job, response)
        except (ValueError, TypeError, KeyError, AttributeError, OverflowError, RecursionError):
            self.stop("FAILED", "MCP response failed the acceptance contract")
            return
        self.state = "SUCCEEDED"
        self.remote_outcome = "RESPONSE_ACCEPTED"

    def stop(self, state, reason):
        allowed = (
            {"BLOCKED", "NOT_RUN"}
            if self.state == "PREPARED"
            else {"FAILED", "TIMED_OUT", "CANCELLED", "UNKNOWN"}
        )
        if self.state in TERMINAL or state not in allowed or not reason:
            raise ValueError("invalid terminal transition or missing reason")
        self.state = state
        self.reason = reason
        # A client timeout/cancel/error never proves that a host operation stopped.

    def report(self):
        if self.state not in TERMINAL:
            raise ValueError("report requires terminal state")
        verdict = {"SUCCEEDED": "PASS", "BLOCKED": "BLOCKED", "NOT_RUN": "NOT_RUN"}.get(
            self.state, "FAIL"
        )
        return {
            "job": asdict(self.job),
            "tool": tool_name(self.job.host, self.job.operation),
            "arguments": {},
            "state": self.state,
            "verdict": verdict,
            "remote_outcome": self.remote_outcome,
            "reason": self.reason,
            "evidence_sha256": self.evidence_sha256,
            "elapsed_seconds": self.elapsed_seconds,
            "invocation_timestamps": "not supplied to validator; retain caller capture",
            "host_project_commit": None,
            "host_workspace_verified": False,
            "limits_enforced_on_host": False,
            "execution_layer": "captured-response validation",
            "transport_provenance_verified": False,
        }


def read_bounded(fd, max_bytes):
    """Read a regular descriptor once, with a hard byte cap and mutation checks."""
    before = os.fstat(fd)
    if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
        raise ValueError("artifact must be a regular file with one link")
    if not 0 < before.st_size <= max_bytes:
        raise ValueError("empty/oversized artifact")
    chunks = []
    count = 0
    while count <= max_bytes:
        chunk = os.read(fd, min(65536, max_bytes + 1 - count))
        if not chunk:
            break
        chunks.append(chunk)
        count += len(chunk)
    after = os.fstat(fd)
    if (
        count > max_bytes
        or count != before.st_size
        or (before.st_size, before.st_mtime_ns, before.st_ctime_ns)
        != (after.st_size, after.st_mtime_ns, after.st_ctime_ns)
    ):
        raise ValueError("artifact changed during read or exceeded bounds")
    return b"".join(chunks)


def read_json(path, max_bytes):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        return json.loads(read_bounded(fd, max_bytes))
    finally:
        os.close(fd)


def read_artifact(root, name, max_bytes=MAX_BYTES):
    """Linux prototype: bytes + hash of one regular demo file in a trusted root.

    Root is an administrator-selected directory, not a client parameter in a deployed API.
    No nested names, symlinks, hardlinks, special files, network, or shell execution.
    """
    if (
        not isinstance(name, str)
        or not re.fullmatch(r"[A-Za-z0-9_-]+\.(stl|scad)", name)
        or type(max_bytes) is not int
        or not 1 <= max_bytes <= MAX_BYTES
    ):
        raise ValueError("only bounded demo basenames are allowed")
    root_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=root_fd)
        try:
            data = read_bounded(fd, max_bytes)
            return data, {
                "name": name,
                "size_bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        finally:
            os.close(fd)
    finally:
        os.close(root_fd)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("prepare", help="pin clean checkout; no MCP call")
    create.add_argument("--repo", type=Path, default=Path.cwd())
    create.add_argument("--jobs-root", type=Path, required=True)
    create.add_argument("--host", choices=HOSTS, default="dell_t3500")
    create.add_argument("--operation", choices=OPERATIONS, default="cad_environment_status")
    check = commands.add_parser("check", help="validate an already captured response; no MCP call")
    check.add_argument("--job", type=Path, required=True)
    check.add_argument("--response", type=Path, required=True)
    check.add_argument("--elapsed-seconds", type=float, required=True)
    args = parser.parse_args()
    try:
        if args.command == "prepare":
            result = asdict(prepare(args.repo, args.jobs_root, args.host, args.operation))
        else:
            job = Job(**read_json(args.job, 16384))
            observation = Observation(job)
            observation.start()
            observation.finish(read_json(args.response, job.max_output_bytes), args.elapsed_seconds)
            result = observation.report()
        sys.stdout.write(json.dumps(result, indent=2) + "\n")
        return 0 if args.command == "prepare" or result["verdict"] == "PASS" else 1
    except (OSError, ValueError, TypeError, RecursionError, subprocess.CalledProcessError) as exc:
        sys.stderr.write(f"pilot: {type(exc).__name__}: invalid local input or checkout\n")
        return 2


if __name__ == "__main__":
    sys.exit(main())
