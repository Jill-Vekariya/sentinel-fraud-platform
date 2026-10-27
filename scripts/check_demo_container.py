"""Check one owned container; never alter existing services or shared volumes."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
import uuid


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output).resolve()
    if output.exists():
        raise SystemExit("Choose a fresh output file")
    source = json.loads(Path("deploy/image-source.json").read_text())
    for path, digest in source["files"].items():
        if hashlib.sha256(Path(path).read_bytes()).hexdigest() != digest:
            raise SystemExit("Source changed; refreeze the deployment manifest before verification")
    name = "sentinel-check-" + uuid.uuid4().hex[:10]
    key = secrets.token_urlsafe(32)
    result = {"passed": False, "image": args.image, "source": source["input_sha256"]}

    def docker(*parts, timeout=30):
        return subprocess.check_output(["docker", *parts], text=True, timeout=timeout)

    def ready(url):
        for _ in range(120):
            try:
                with urllib.request.urlopen(url + "/health/ready", timeout=1):
                    return
            except (OSError, urllib.error.HTTPError):
                time.sleep(0.5)
        raise TimeoutError("Readiness failed within 60 seconds")

    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with tempfile.TemporaryDirectory(prefix="sentinel-env-") as directory:
            env_file = Path(directory) / "demo.env"
            env_file.write_text("API_KEY=" + key + "\n")
            docker(
                "run",
                "--detach",
                "--name",
                name,
                "--read-only",
                "--tmpfs",
                "/tmp:rw,noexec,nosuid,size=64m",
                "--memory",
                "512m",
                "--cpus",
                "0.5",
                "--pids-limit",
                "128",
                "--cap-drop",
                "ALL",
                "--security-opt",
                "no-new-privileges",
                "--env-file",
                str(env_file),
                "--publish",
                "127.0.0.1::10000",
                args.image,
            )
        port = docker("port", name, "10000/tcp").strip().rsplit(":", 1)[1]
        url = "http://127.0.0.1:" + port
        ready(url)
        assert docker("exec", name, "id", "-u").strip() == "10001"
        baked = json.loads(docker("exec", name, "cat", "/app/image-source.json"))
        assert baked == source
        env = os.environ.copy()
        env["API_KEY"] = key
        client = subprocess.run(
            [
                os.sys.executable,
                "scripts/verify_demo_deployment.py",
                "--url",
                url,
                "--count",
                "200",
                "--output",
                str(output.with_suffix(".http.json")),
            ],
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )
        output.with_suffix(".client.log").write_text(client.stdout + client.stderr)
        assert client.returncode == 0, "Bounded HTTP verification failed; see retained HTTP result"
        http = json.loads(output.with_suffix(".http.json").read_text())
        result["memory_sample"] = docker(
            "stats", "--no-stream", "--format", "{{.MemUsage}}", name
        ).strip()
        state = json.loads(docker("inspect", name))[0]
        assert state["HostConfig"]["Memory"] == 536870912
        assert not state["State"]["OOMKilled"]
        host = state["HostConfig"]
        assert host["NanoCpus"] == 500000000 and host["PidsLimit"] == 128
        assert host["ReadonlyRootfs"] is True and "ALL" in host["CapDrop"]
        assert any(x.startswith("no-new-privileges") for x in host["SecurityOpt"])
        assert "size=64m" in host["Tmpfs"]["/tmp"]
        assert all(p["HostIp"] == "127.0.0.1" for p in host["PortBindings"]["10000/tcp"])
        result.update(
            image_id=state["Image"],
            nonroot_uid=10001,
            memory_limit_bytes=536870912,
            cpu_limit=0.5,
            tmpfs_limit_bytes=67108864,
            read_only_root=True,
            pids_limit=128,
            capabilities_dropped=True,
            http=http,
        )
        before_restart_url = url
        docker("restart", name)
        # Docker may allocate a different host port when an ephemeral mapping restarts.
        port = docker("port", name, "10000/tcp").strip().rsplit(":", 1)[1]
        url = "http://127.0.0.1:" + port
        result.update(
            endpoint_before_restart=before_restart_url,
            endpoint_after_restart=url,
            host_port_changed_on_restart=url != before_restart_url,
        )
        ready(url)
        req = urllib.request.Request(
            url + "/v1/decisions/" + http["first_transaction_id"], headers={"X-API-Key": key}
        )
        try:
            urllib.request.urlopen(req, timeout=5)
            raise AssertionError("Expected ephemeral ledger to reset on restart")
        except urllib.error.HTTPError as exc:
            assert exc.code == 404
        result.update(passed=True, restart_ready=True, ephemeral_ledger_reset=True)
    except Exception as exc:
        result.update(error_type=type(exc).__name__, error=str(exc))
    finally:
        logs = subprocess.run(["docker", "logs", name], capture_output=True, text=True, timeout=15)
        output.with_suffix(".server.log").write_text(logs.stdout + logs.stderr)
        cleanup = subprocess.run(
            ["docker", "rm", "--force", name], capture_output=True, text=True, timeout=30
        )
        result["owned_container_cleanup_exit_code"] = cleanup.returncode
        result["passed"] = result["passed"] and cleanup.returncode == 0
        with output.open("x") as handle:
            json.dump(result, handle, indent=2)
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
