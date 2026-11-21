"""Opt-in real HTTP check against a child local service, without DB or IAM access."""

from __future__ import annotations

import argparse
import json
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from tools.run_persons import launch_command, preview_environment


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Never follow redirects from loopback to institutional destinations.
        return None


def check(service_root: Path) -> None:
    # A free ephemeral loopback port avoids interrupting any manually started service.
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    command = launch_command(service_root, port)
    # Explicitly bypass any configured network proxy, even for loopback.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    child = subprocess.Popen(
        command,
        cwd=service_root.resolve(),
        env=preview_environment(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    base = f"http://127.0.0.1:{port}"
    try:
        for _ in range(100):
            if child.poll() is not None:
                raise RuntimeError("Local child failed before readiness check")
            try:
                with opener.open(base + "/health/live", timeout=1) as response:
                    assert response.status == 200
                    assert (
                        json.load(response)["private_api"] == "requires_trusted_platform_delegation"
                    )
                break
            except (urllib.error.URLError, ConnectionError):
                time.sleep(0.1)
        else:
            raise RuntimeError("Local startup timeout")
        with opener.open(base + "/openapi.json", timeout=2) as response:
            schema = json.load(response)
            assert "/v1/personas" in schema["paths"]
            assert "HTTPBearer" in schema.get("components", {}).get("securitySchemes", {})
        routes = [
            ("GET", "/health/ready", None),
            ("GET", "/v1/personas", None),
            ("GET", "/v1/personas/00000000-0000-4000-8000-000000000001", None),
            ("GET", "/v1/personas/00000000-0000-4000-8000-000000000001/referencias", None),
            ("GET", "/v1/revisiones", None),
            (
                "GET",
                "/v1/referencias/resolver?system=demo&entity=fixture&external_id=SYNTHETIC-PRIVATE-MARKER",
                None,
            ),
            ("POST", "/v1/personas", b"{}"),
            ("POST", "/v1/personas/00000000-0000-4000-8000-000000000001/cuentas", b"{}"),
        ]
        for method, path, body in routes:
            request = urllib.request.Request(
                base + path,
                method=method,
                data=body,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": "Bearer SYNTHETIC-NOT-A-TOKEN",
                },
            )
            try:
                opener.open(request, timeout=2)
            except urllib.error.HTTPError as response:
                assert response.code == 503
                content = response.read().decode()
                assert "SYNTHETIC-PRIVATE-MARKER" not in content
                if path.startswith("/v1/"):
                    assert response.headers["Content-Type"] == "application/problem+json"
            else:
                raise AssertionError("Private operations/readiness must remain blocked")
    finally:
        child.terminate()
        try:
            stdout, stderr = child.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            child.kill()
            child.communicate(timeout=5)
            raise RuntimeError("Child required forced termination") from None
        assert "SYNTHETIC-PRIVATE-MARKER" not in stdout + stderr
    print(
        "PASS: external service launched; liveness/OpenAPI=200; "
        "readiness/private=503 without isolated auth/database config; "
        "no URL data in logs; child stopped"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Check blocked Personas composition on loopback")
    parser.add_argument("--service-root", type=Path, required=True)
    args = parser.parse_args()
    try:
        check(args.service_root)
    except (AssertionError, ValueError, OSError, RuntimeError, KeyError):
        print(
            "FAIL: local Personas composition check; no production destination used",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
