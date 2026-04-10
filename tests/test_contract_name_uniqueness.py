"""Guardrails for contract naming hygiene across contract modules."""

# ruff: noqa: I001

import pathlib
import ast


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
CONTRACTS_DIR = PROJECT_ROOT / "src" / "contracts"


def _discover_contract_modules() -> list[pathlib.Path]:
    """Return all concrete contract modules except package bootstrap files."""
    return sorted(
        path for path in CONTRACTS_DIR.glob("*.py") if path.name != "__init__.py"
    )


def _collect_contract_type_names(module_path: pathlib.Path) -> set[str]:
    """Collect class and type alias names declared in a contract module."""
    module_tree = ast.parse(module_path.read_text(encoding="utf-8"))
    names: set[str] = set()

    for node in module_tree.body:
        if isinstance(node, ast.ClassDef):
            names.add(node.name)
            continue

        if isinstance(node, ast.TypeAlias) and isinstance(node.name, ast.Name):
            names.add(node.name.id)

    return names


def test_contract_type_names_are_unique_across_modules() -> None:
    """Contract class/type names should be unique across contract modules."""
    seen_by_name: dict[str, pathlib.Path] = {}
    duplicates: dict[str, set[pathlib.Path]] = {}

    for module_path in _discover_contract_modules():
        for name in _collect_contract_type_names(module_path):
            if name in seen_by_name:
                duplicates.setdefault(name, {seen_by_name[name]}).add(module_path)
                continue
            seen_by_name[name] = module_path

    if duplicates:
        duplicate_lines: list[str] = []
        for name, paths in sorted(duplicates.items()):
            relative_paths = sorted(
                str(path.relative_to(PROJECT_ROOT)) for path in paths
            )
            duplicate_lines.append(f"{name}: {', '.join(relative_paths)}")
        duplicate_report = "\n".join(duplicate_lines)
        msg = (
            "Duplicate contract type names found across modules. "
            "Use unique names per contracts module.\n"
            f"{duplicate_report}"
        )
        raise AssertionError(msg)
