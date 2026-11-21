import hashlib
import json
import os
from pathlib import Path
from unittest.mock import Mock

import pytest

from tools import run_persons


@pytest.fixture
def preview(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    platform, service = tmp_path / "platform", tmp_path / "registro-personas"
    platform.mkdir()
    service.mkdir()
    (service / "pyproject.toml").write_text(
        '[project]\nname="registro-personas"\n', encoding="utf-8"
    )
    for root, rel in [
        (platform, "contracts/openapi/person-service.yaml"),
        (service, "docs/openapi.yaml"),
    ]:
        path = root / rel
        path.parent.mkdir(parents=True)
        path.write_bytes(b"synthetic coordinated contract")
    python = service / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    python.parent.mkdir(parents=True)
    python.touch()
    (service / ".venv/pyvenv.cfg").write_text("version_info = 3.12\n", encoding="utf-8")
    entry = service / "src/registro_personas/__main__.py"
    entry.parent.mkdir(parents=True)
    entry.touch()
    manifest = platform / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "implementation": "registro-personas",
                "python_version": "3.12",
                "private_api_activation": "PLATFORM_SIGNED_DELEGATION_RS256",
                "contract_path": "contracts/openapi/person-service.yaml",
                "source_contract_path": "docs/openapi.yaml",
                "contract_sha256": hashlib.sha256(b"synthetic coordinated contract").hexdigest(),
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(run_persons, "PLATFORM_ROOT", platform)
    monkeypatch.setattr(run_persons, "MANIFEST", manifest)
    return platform, service


def test_launch_uses_external_venv_and_module(preview: tuple[Path, Path]) -> None:
    _, service = preview
    command = run_persons.launch_command(service)
    assert Path(command[0]).is_relative_to(service)
    assert command[1:] == ["-m", "registro_personas", "--port", "8013"]
    assert not any("mes_person_service" in part for part in command)


@pytest.mark.parametrize("side", ["platform", "service"])
def test_contract_drift_blocks_launch(preview: tuple[Path, Path], side: str) -> None:
    platform, service = preview
    path = (
        platform / "contracts/openapi/person-service.yaml"
        if side == "platform"
        else service / "docs/openapi.yaml"
    )
    path.write_bytes(b"uncoordinated contract")
    with pytest.raises(ValueError, match="contract drift"):
        run_persons.launch_command(service)


def test_preflight_never_starts_process(
    preview: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    _, service = preview
    run = Mock()
    monkeypatch.setattr(run_persons.subprocess, "run", run)
    assert run_persons.main(["--service-root", str(service), "--check"]) == 0
    run.assert_not_called()


def test_preview_does_not_inherit_database_or_python_injection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in [
        "REGISTRY_DATABASE_URL",
        "REGISTRY_TEST_DATABASE_URL",
        "PGHOST",
        "PGSERVICE",
        "PGPASSWORD",
        "PYTHONPATH",
        "PYTHONHOME",
        "PYTHONSTARTUP",
        "OIDC_ISSUER_URL",
        "OIDC_JWKS_URL",
        "REGISTRY_OIDC_ISSUER",
        "REGISTRY_OIDC_JWKS_URL",
        "REGISTRY_DELEGATION_ISSUER",
        "REGISTRY_DELEGATION_PUBLIC_KEY_FILE",
        "PERSONS_DELEGATION_PRIVATE_KEY_FILE",
        "PERSONS_AUTHORIZATION_POLICY_FILE",
    ]:
        monkeypatch.setenv(name, "SYNTHETIC-DO-NOT-INHERIT")
    environment = run_persons.preview_environment()
    assert "SYNTHETIC-DO-NOT-INHERIT" not in environment.values()


@pytest.mark.parametrize(
    "mutation", ["missing", "wrong-project", "invalid-port", "enabled", "python-version"]
)
def test_invalid_configuration_never_starts(
    preview: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch, mutation: str
) -> None:
    _, service = preview
    port = "8003"
    if mutation == "missing":
        service = service / "missing"
    elif mutation == "wrong-project":
        (service / "pyproject.toml").write_text('[project]\nname="other"\n', encoding="utf-8")
    elif mutation == "invalid-port":
        port = "65536"
    elif mutation == "python-version":
        (service / ".venv/pyvenv.cfg").write_text("version = 3.13.2\n", encoding="utf-8")
    else:
        manifest = json.loads(run_persons.MANIFEST.read_text(encoding="utf-8"))
        manifest["private_api_activation"] = "ACTIVE"
        run_persons.MANIFEST.write_text(json.dumps(manifest), encoding="utf-8")
    run = Mock()
    monkeypatch.setattr(run_persons.subprocess, "run", run)
    assert run_persons.main(["--service-root", str(service), "--port", port]) == 2
    run.assert_not_called()
