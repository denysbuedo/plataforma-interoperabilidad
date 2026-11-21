import ast
from pathlib import Path

SERVICE_ROOT = Path("services")


def test_services_do_not_import_other_services() -> None:
    service_packages = {
        "mes_registry_api",
        "mes_institution_service",
        "mes_person_service",
    }
    violations: list[str] = []
    for source in SERVICE_ROOT.rglob("*.py"):
        own_package = next((part for part in source.parts if part in service_packages), None)
        tree = ast.parse(source.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module.split(".")[0]]
            for name in names:
                if name in service_packages and name != own_package:
                    violations.append(f"{source}: imports {name}")
    assert not violations, "\n".join(violations)
