"""Cloud-only contract tests with synthetic responses and temporary files."""

import hashlib
import json
import os
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest

from tools.pilot import MAX_BYTES, Job, Observation, prepare, read_artifact, read_json, tool_name


@pytest.fixture
def job(tmp_path):
    identity = "a" * 32
    return Job(
        identity, "b" * 40, str(tmp_path / identity), "dell_t3500", "scilab_batch_smoke_test"
    )


def response(**changes):
    data = {"exit_code": 0, "passed": True, "stdout": "\n 6.\n", "stderr": ""}
    data.update(changes)
    return {"isError": False, "content": [{"type": "text", "text": json.dumps(data)}]}


def finished(job, raw=None, elapsed=1):
    result = Observation(job)
    result.start()
    result.finish(response() if raw is None else raw, elapsed)
    return result


def test_semantic_success(job):
    report = finished(job).report()
    assert report["verdict"] == "PASS"
    assert report["remote_outcome"] == "RESPONSE_ACCEPTED"
    assert report["evidence_sha256"] == hashlib.sha256(json.dumps(response()).encode()).hexdigest()
    assert report["host_project_commit"] is None
    assert not report["limits_enforced_on_host"]


@pytest.mark.parametrize(
    "raw",
    [
        response(stdout="5"),
        response(stdout="nan"),
        response(stdout="6 7"),
        response(exit_code=False),
        response(exit_code=1),
        response(passed=False),
        {"isError": True},
        {},
        {"isError": False, "content": []},
        {"isError": False, "content": [{"type": "text", "text": "garbage"}]},
        {"isError": False, "structuredContent": []},
        {"isError": False, "structuredContent": {"exit_code": 0}},
    ],
)
def test_bad_evidence_fails(job, raw):
    assert finished(job, raw).report()["verdict"] == "FAIL"


def test_output_bound(job):
    assert finished(replace(job, max_output_bytes=10)).state == "FAILED"


@pytest.mark.parametrize("elapsed", [30, 31, 60])
def test_timeout_does_not_accept_late_success(job, elapsed):
    observation = finished(job, elapsed=elapsed)
    assert observation.state == "TIMED_OUT"
    assert observation.remote_outcome == "UNKNOWN"
    assert observation.evidence_sha256 is not None
    assert observation.report()["elapsed_seconds"] == elapsed


@pytest.mark.parametrize("elapsed", [-1, float("nan"), float("inf"), True])
def test_bad_elapsed(job, elapsed):
    with pytest.raises(ValueError):
        finished(job, elapsed=elapsed)


@pytest.mark.parametrize("state", ["CANCELLED", "TIMED_OUT", "UNKNOWN", "FAILED"])
def test_terminal_state_is_immutable_and_remote_unconfirmed(job, state):
    observation = Observation(job)
    observation.start()
    observation.stop(state, "client observation only")
    assert observation.report()["remote_outcome"] == "UNKNOWN"
    with pytest.raises(ValueError):
        observation.finish(response(), 1)
    with pytest.raises(ValueError):
        observation.start()


@pytest.mark.parametrize("state", ["BLOCKED", "NOT_RUN"])
def test_preflight_terminal(job, state):
    observation = Observation(job)
    observation.stop(state, "permission or tool missing")
    assert observation.report()["verdict"] == state
    assert observation.report()["remote_outcome"] == "NOT_STARTED"


def test_illegal_transitions(job):
    observation = Observation(job)
    with pytest.raises(ValueError):
        observation.finish(response(), 1)
    with pytest.raises(ValueError):
        observation.report()
    with pytest.raises(ValueError):
        observation.stop("SUCCEEDED", "no evidence")
    observation.start()
    with pytest.raises(ValueError):
        observation.stop("NOT_RUN", "already started")


@pytest.mark.parametrize(
    "change",
    [
        {"commit": "main"},
        {"commit": "b" * 39},
        {"host": "unknown"},
        {"operation": "run_shell"},
        {"timeout_seconds": 61},
        {"timeout_seconds": True},
        {"max_output_bytes": MAX_BYTES + 1},
        {"cpu_limit": 2},
        {"memory_mib": 513},
        {"max_parallel_jobs": 2},
        {"workspace": "/tmp/../escape"},
        {"workspace": "relative"},
    ],
)
def test_job_rejects_invalid_contract(job, change):
    with pytest.raises(ValueError):
        replace(job, **change)


def test_status_and_listing_contracts(job):
    inventory = {
        name: {"available": True, "version": {"exit_code": 0, "stdout": "version 1"}}
        for name in ("openscad", "scilab", "freecad")
    }
    status_job = replace(job, operation="cad_environment_status")
    raw = {"isError": False, "structuredContent": inventory}
    assert finished(status_job, raw).state == "SUCCEEDED"
    inventory["freecad"]["version"]["exit_code"] = 1
    assert finished(status_job, raw).state == "FAILED"
    listing = replace(job, operation="cad_list_artifacts")
    assert (
        finished(listing, {"isError": False, "structuredContent": {"result": ["demo.stl"]}}).state
        == "SUCCEEDED"
    )
    assert (
        finished(listing, {"isError": False, "structuredContent": {"result": [1]}}).state
        == "FAILED"
    )


def test_profile_matches_allowlist(job):
    profile = json.loads(Path("config/pilot.json").read_text())
    for route in profile["agent_routes"]:
        for operation, name in route["tools"].items():
            assert name == tool_name(route["host"], operation)
    assert profile["direct_client"]["enabled"] is False
    assert profile["host_deployment"] == "NOT_RUN"
    for key, value in profile["limits"].items():
        assert getattr(job, key) == value


def test_prepare_requires_clean_revision_and_unique_external_workspace(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", str(repo)], check=True, capture_output=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.invalid",
            "commit",
            "--allow-empty",
            "-m",
            "test",
        ],
        check=True,
        capture_output=True,
    )
    root = tmp_path / "jobs"
    root.mkdir()
    a = prepare(repo, root, "live", "cad_environment_status")
    b = prepare(repo, root, "live", "cad_environment_status")
    assert a.workspace != b.workspace
    assert a.commit == b.commit
    assert json.loads((Path(a.workspace) / "job.json").read_text())["commit"] == a.commit
    with pytest.raises(ValueError, match="outside"):
        prepare(repo, repo, "live", "cad_environment_status")
    (repo / "dirty.txt").write_text("dirty")
    with pytest.raises(ValueError, match="clean"):
        prepare(repo, root, "live", "cad_environment_status")


def test_artifact_bytes_and_independent_hash(tmp_path):
    data = b"solid demo\nendsolid demo\n"
    (tmp_path / "demo.stl").write_bytes(data)
    actual, manifest = read_artifact(tmp_path, "demo.stl", len(data))
    assert actual == data
    assert manifest["size_bytes"] == len(data)
    assert manifest["sha256"] == hashlib.sha256(data).hexdigest()


@pytest.mark.parametrize(
    "name",
    [
        "../demo.stl",
        "/tmp/demo.stl",
        "sub/demo.stl",
        ".env",
        "demo.stl/..",
        "demo.stl\x00",
        "demo.txt",
    ],
)
def test_artifact_name_escape_rejected(tmp_path, name):
    with pytest.raises(ValueError):
        read_artifact(tmp_path, name)


def test_artifact_symlink_hardlink_directory_and_fifo_rejected(tmp_path):
    outside = tmp_path / "outside.stl"
    outside.write_bytes(b"data")
    root = tmp_path / "root"
    root.mkdir()
    (root / "link.stl").symlink_to(outside)
    os.link(outside, root / "hard.stl")
    (root / "directory.stl").mkdir()
    os.mkfifo(root / "fifo.stl")
    for name in ("link.stl", "hard.stl", "directory.stl", "fifo.stl"):
        with pytest.raises((ValueError, OSError)):
            read_artifact(root, name)
    symlink_root = tmp_path / "rootlink"
    symlink_root.symlink_to(root, target_is_directory=True)
    with pytest.raises(OSError):
        read_artifact(symlink_root, "outside.stl")


def test_artifact_empty_oversized_and_limit_validation(tmp_path):
    target = tmp_path / "demo.stl"
    target.write_bytes(b"")
    with pytest.raises(ValueError):
        read_artifact(tmp_path, "demo.stl")
    target.write_bytes(b"12345")
    for limit in (4, 0, -1, MAX_BYTES + 1, True):
        with pytest.raises(ValueError):
            read_artifact(tmp_path, "demo.stl", limit)


def test_descriptor_survives_path_replacement(tmp_path, monkeypatch):
    target = tmp_path / "demo.stl"
    target.write_bytes(b"original")
    outside = tmp_path / "outside"
    outside.write_bytes(b"secret")
    original_read = os.read

    def swap(fd, count):
        if not target.is_symlink():
            target.rename(tmp_path / "old")
            target.symlink_to(outside)
        return original_read(fd, count)

    monkeypatch.setattr(os, "read", swap)
    # Renaming changes ctime on some filesystems: fail closed, or read the original descriptor.
    try:
        data, _ = read_artifact(tmp_path, "demo.stl")
    except ValueError:
        return
    assert data == b"original"


def test_growth_during_read_rejected(tmp_path, monkeypatch):
    target = tmp_path / "demo.stl"
    target.write_bytes(b"123")
    original_read = os.read

    def grow(fd, count):
        with target.open("ab") as stream:
            stream.write(b"more")
        return original_read(fd, count)

    monkeypatch.setattr(os, "read", grow)
    with pytest.raises(ValueError):
        read_artifact(tmp_path, "demo.stl", 4)


def test_failed_evidence_is_retained(job):
    observation = finished(job, response(stdout="5"))
    assert observation.state == "FAILED"
    assert observation.evidence_sha256 is not None
    assert observation.report()["execution_layer"] == "captured-response validation"
    assert observation.report()["transport_provenance_verified"] is False


def test_bounded_json_rejects_fifo_oversize_and_symlink(tmp_path):
    target = tmp_path / "raw.json"
    target.write_text('{"ok":true}')
    assert read_json(target, 20) == {"ok": True}
    with pytest.raises(ValueError):
        read_json(target, 2)
    fifo = tmp_path / "fifo.json"
    os.mkfifo(fifo)
    with pytest.raises(ValueError):
        read_json(fifo, 20)
    link = tmp_path / "link.json"
    link.symlink_to(target)
    with pytest.raises(OSError):
        read_json(link, 20)


def test_cli_nested_json_cannot_pass(job, tmp_path):
    import sys
    from dataclasses import asdict

    job_path = tmp_path / "job.json"
    job_path.write_text(json.dumps(asdict(job)))
    raw_path = tmp_path / "response.json"
    raw_path.write_text("[" * 2000 + "0" + "]" * 2000)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "tools.pilot",
            "check",
            "--job",
            str(job_path),
            "--response",
            str(raw_path),
            "--elapsed-seconds",
            "1",
        ],
        capture_output=True,
        text=True,
        timeout=5,
    )
    # Some Python decoders accept this depth; the semantic contract must still reject it.
    assert result.returncode in (1, 2)
    assert "Traceback" not in result.stderr


def test_status_missing_version_text_fails(job):
    inventory = {
        name: {"available": True, "version": {"exit_code": 0}}
        for name in ("openscad", "scilab", "freecad")
    }
    assert (
        finished(
            replace(job, operation="cad_environment_status"),
            {"isError": False, "structuredContent": inventory},
        ).state
        == "FAILED"
    )
