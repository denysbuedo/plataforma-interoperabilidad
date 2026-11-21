"""Local composition of the independent Person Registry; never installs or deploys it."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tomllib
from pathlib import Path

PLATFORM_ROOT = Path(__file__).resolve().parents[1]
MANIFEST = PLATFORM_ROOT / "services/person-service/external-service.json"


def launch_command(service_root: Path, port: int = 8013) -> list[str]:
    if not 1 <= port <= 65535:
        raise ValueError("Invalid local port")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if manifest["private_api_activation"] != "PLATFORM_SIGNED_DELEGATION_RS256":
        raise ValueError("Unexpected Person service authentication mode")
    root = service_root.resolve(strict=True)
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    if project.get("project", {}).get("name") != manifest["implementation"]:
        raise ValueError("Expected the independent registro-personas repository")
    for contract in [
        PLATFORM_ROOT / manifest["contract_path"],
        root / manifest["source_contract_path"],
    ]:
        if hashlib.sha256(contract.read_bytes()).hexdigest() != manifest["contract_sha256"]:
            raise ValueError(
                "Personas contract drift: coordinate both repositories before launching"
            )
    python = root / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not python.is_file() or not (root / "src/registro_personas/__main__.py").is_file():
        raise ValueError("Prepare the service Python 3.12 virtualenv using its README first")
    venv = dict(
        line.split("=", 1)
        for line in (root / ".venv/pyvenv.cfg").read_text(encoding="utf-8").splitlines()
        if "=" in line
    )
    metadata = {key.strip(): value.strip() for key, value in venv.items()}
    version = metadata.get("version_info", metadata.get("version", ""))
    if version.split(".")[:2] != manifest["python_version"].split("."):
        raise ValueError("The independent service requires its own Python 3.12 environment")
    return [str(python), "-m", "registro_personas", "--port", str(port)]


def preview_environment() -> dict[str, str]:
    # No inheritance of database destinations, module injection or Python startup hooks.
    excluded = {
        "REGISTRY_DATABASE_URL",
        "REGISTRY_TEST_DATABASE_URL",
        "PYTHONPATH",
        "PYTHONHOME",
        "PYTHONSTARTUP",
        "OIDC_ISSUER_URL",
        "OIDC_JWKS_URL",
        "OIDC_PUBLIC_KEY_FILE",
        "REGISTRY_OIDC_ISSUER",
        "REGISTRY_OIDC_JWKS_URL",
        "REGISTRY_OIDC_PUBLIC_KEY_FILE",
        "REGISTRY_OIDC_AUDIENCE",
        "REGISTRY_DELEGATION_ISSUER",
        "REGISTRY_DELEGATION_AUDIENCE",
        "REGISTRY_DELEGATION_KEY_ID",
        "REGISTRY_DELEGATION_JWKS_URL",
        "REGISTRY_DELEGATION_PUBLIC_KEY_FILE",
        "PERSONS_AUTHORIZATION_POLICY_FILE",
    }
    return {
        key: value
        for key, value in os.environ.items()
        if key.upper() not in excluded
        and not key.upper().startswith("PG")
        and not key.upper().startswith("REGISTRY_OIDC_")
        and not key.upper().startswith("REGISTRY_DELEGATION_")
        and not key.upper().startswith("PERSONS_OIDC_")
        and not key.upper().startswith("PERSONS_DELEGATION_")
        and not key.upper().startswith("OIDC_")
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Start the external Person Registry locally; private API requires platform delegation"
        )
    )
    parser.add_argument("--service-root", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8013)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate local files/contracts only; no process or network",
    )
    args = parser.parse_args(argv)
    try:
        command = launch_command(args.service_root, args.port)
    except (ValueError, OSError, KeyError):
        print(
            "Personas preflight failed: verify repository, virtualenv and coordinated contract.",
            file=sys.stderr,
        )
        return 2
    if args.check:
        print(
            "person-service: external implementation ready for isolated local preview; "
            "OIDC and database config removed"
        )
        return 0
    try:
        return subprocess.run(
            command, cwd=args.service_root.resolve(), env=preview_environment(), check=False
        ).returncode
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
