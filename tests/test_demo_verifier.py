"""Exercise restart endpoint discovery without requiring a real Docker daemon."""

import json
from contextlib import nullcontext
from types import SimpleNamespace
import urllib.error

import pytest

from scripts import check_demo_container as verifier


@pytest.mark.parametrize(
    "restart_port,restart_healthy", [(10001, True), (10002, True), (10002, False)]
)
def test_restart_uses_current_mapping_and_still_requires_readiness(
    tmp_path, monkeypatch, restart_port, restart_healthy
):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "deploy").mkdir()
    source = {"files": {}, "input_sha256": "synthetic-test-fixture"}
    (tmp_path / "deploy/image-source.json").write_text(json.dumps(source))
    output = tmp_path / "result.json"
    state = {"restarted": False, "readiness_urls": [], "cleanup": False}

    def docker(command, **kwargs):
        operation = command[1]
        if operation == "run":
            return "synthetic-container\n"
        if operation == "port":
            port = restart_port if state["restarted"] else 10001
            return f"127.0.0.1:{port}\n"
        if operation == "exec":
            return "10001\n" if "id" in command else json.dumps(source)
        if operation == "stats":
            return "100MiB / 512MiB\n"
        if operation == "inspect":
            return json.dumps(
                [
                    {
                        "Image": "synthetic-image",
                        "State": {"OOMKilled": False},
                        "HostConfig": {
                            "Memory": 536870912,
                            "NanoCpus": 500000000,
                            "PidsLimit": 128,
                            "ReadonlyRootfs": True,
                            "CapDrop": ["ALL"],
                            "SecurityOpt": ["no-new-privileges"],
                            "Tmpfs": {"/tmp": "rw,size=64m"},
                            "PortBindings": {"10000/tcp": [{"HostIp": "127.0.0.1"}]},
                        },
                    }
                ]
            )
        if operation == "restart":
            state["restarted"] = True
            return "synthetic-container\n"
        raise AssertionError(command)

    def run(command, **kwargs):
        if command[0] == "docker":
            state["cleanup"] = state["cleanup"] or command[1] == "rm"
        else:
            # Stand in for the already separate bounded HTTP protocol.
            output.with_suffix(".http.json").write_text(
                json.dumps({"first_transaction_id": "synthetic-replay-id"})
            )
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    def urlopen(request, **kwargs):
        url = request if isinstance(request, str) else request.full_url
        expected_port = restart_port if state["restarted"] else 10001
        if not url.startswith(f"http://127.0.0.1:{expected_port}/"):
            raise OSError("Stale host mapping")
        if url.endswith("/health/ready"):
            state["readiness_urls"].append(url)
            if state["restarted"] and not restart_healthy:
                raise OSError("Restarted application is not ready")
            return nullcontext()
        raise urllib.error.HTTPError(url, 404, "Synthetic ephemeral-ledger reset", {}, None)

    monkeypatch.setattr(verifier, "subprocess", SimpleNamespace(check_output=docker, run=run))
    monkeypatch.setattr(verifier.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(verifier.time, "sleep", lambda _: None)
    monkeypatch.setattr(
        "sys.argv", ["check_demo_container.py", "--image", "synthetic", "--output", str(output)]
    )
    with pytest.raises(SystemExit) as exit_info:
        verifier.main()
    result = json.loads(output.read_text())
    assert exit_info.value.code == (0 if restart_healthy else 1)
    assert result["passed"] is restart_healthy
    assert result["endpoint_before_restart"] == "http://127.0.0.1:10001"
    assert result["endpoint_after_restart"] == f"http://127.0.0.1:{restart_port}"
    assert result["host_port_changed_on_restart"] == (restart_port != 10001)
    assert state["readiness_urls"][-1] == f"http://127.0.0.1:{restart_port}/health/ready"
    assert state["cleanup"] is True
    if restart_healthy:
        assert result["ephemeral_ledger_reset"] is True
    else:
        assert result["error_type"] == "TimeoutError"
