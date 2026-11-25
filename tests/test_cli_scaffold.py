"""Scaffold, CLI tracer, and active-phase boundary tests for ets2v2."""

from __future__ import annotations

import argparse
import ast
import importlib.metadata
import pathlib
import tomllib
from typing import cast

import pydantic
import pytest

import ets2v2
from ets2v2.cli import build_parser, main

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent


def _as_table(value: object) -> dict[str, object]:
    assert isinstance(value, dict)
    return cast(dict[str, object], value)


def _as_str_list(value: object) -> list[str]:
    assert isinstance(value, list)
    items = cast(list[object], value)
    result: list[str] = []
    for item in items:
        assert isinstance(item, str)
        result.append(item)
    return result


def test_package_version() -> None:
    assert ets2v2.__version__ == "0.1.0"


def test_cli_version(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main(["--version"])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out.strip() == "ets2v2 0.1.0"


def test_cli_help(capsys: pytest.CaptureFixture[str]) -> None:
    parser = build_parser()
    assert isinstance(parser, argparse.ArgumentParser)
    exit_code = main(["--help"])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "ets2v2" in captured.out
    assert "--version" in captured.out


def test_pydantic_available() -> None:
    parts = pydantic.__version__.split(".")
    major = int(parts[0])
    minor = int(parts[1])
    assert (major, minor) >= (2, 14)


def test_active_phase_only_package_layout() -> None:
    pkg_root = REPO_ROOT / "src" / "ets2v2"
    assert pkg_root.is_dir()

    entries = {entry.name for entry in pkg_root.iterdir() if entry.name != "__pycache__"}
    deferred_phase_dirs: set[str] = set()
    allowed_phase4_entries = {
        "__init__.py",
        "py.typed",
        "cli.py",
        "vfs",
        "sii",
        "baseline",
        "normalize",
        "registry",
        "fetch",
        "package",
        "validate",
        "merge",
        "publish",
    }

    assert entries.isdisjoint(deferred_phase_dirs)
    assert entries <= allowed_phase4_entries
    assert {"__init__.py", "py.typed", "cli.py", "merge"} <= entries


def test_pyproject_metadata_and_quality_gates() -> None:
    raw: dict[str, object] = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text("utf-8"))

    build_system = _as_table(raw["build-system"])
    assert "hatchling>=1.27,<2" in _as_str_list(build_system["requires"])
    assert build_system["build-backend"] == "hatchling.build"

    project = _as_table(raw["project"])
    assert project["name"] == "ets2-world-realism"
    assert project["version"] == "0.1.0"
    assert project["requires-python"] == ">=3.12"
    assert project["license"] == "MIT"
    assert sorted(_as_str_list(project["dependencies"])) == [
        "httpx>=0.28,<0.29",
        "openpyxl>=3.1,<4",
        "pillow>=12,<14",
        "pydantic>=2.14,<3",
        "tzdata>=2025.2",
    ]

    scripts = _as_table(project["scripts"])
    assert scripts["ets2v2"] == "ets2v2.cli:main"

    dep_groups = _as_table(raw["dependency-groups"])
    dev_deps = _as_str_list(dep_groups["dev"])
    for expected_dep in (
        "basedpyright>=1.40,<2",
        "pytest>=9.2,<9.3",
        "pytest-cov>=6,<8",
        "ruff>=0.16",
        "types-openpyxl>=3.1",
    ):
        assert expected_dep in dev_deps

    tool = _as_table(raw["tool"])
    basedpyright = _as_table(tool["basedpyright"])
    assert basedpyright["typeCheckingMode"] == "strict"
    assert basedpyright["pythonVersion"] == "3.12"

    ruff = _as_table(tool["ruff"])
    assert ruff["target-version"] == "py312"
    ruff_lint = _as_table(ruff["lint"])
    assert _as_str_list(ruff_lint["select"]) == ["E", "F", "I", "UP", "B", "SIM", "RUF"]

    pytest_cfg = _as_table(_as_table(tool["pytest"])["ini_options"])
    assert _as_str_list(pytest_cfg["testpaths"]) == ["tests"]
    assert _as_str_list(pytest_cfg["pythonpath"]) == ["src"]


def test_uv_lock_contains_verified_packages() -> None:
    lock_path = REPO_ROOT / "uv.lock"
    assert lock_path.is_file(), "uv.lock must exist"

    lock_data: dict[str, object] = tomllib.loads(lock_path.read_text("utf-8"))
    raw_packages = lock_data.get("package")
    assert isinstance(raw_packages, list)

    package_names: set[str] = set()
    for entry in cast(list[object], raw_packages):
        table = _as_table(entry)
        name = table.get("name")
        if isinstance(name, str):
            package_names.add(name)

    expected = {
        "httpx",
        "openpyxl",
        "pydantic",
        "tzdata",
        "pillow",
        "basedpyright",
        "pytest",
        "pytest-cov",
        "ruff",
        "types-openpyxl",
    }
    assert expected <= package_names


def test_ci_workflow_configuration() -> None:
    ci_path = REPO_ROOT / ".github" / "workflows" / "ci.yml"
    assert ci_path.is_file(), ".github/workflows/ci.yml must exist"

    raw_bytes = ci_path.read_bytes()
    assert not raw_bytes.startswith(b"\xef\xbb\xbf")
    assert b"\r\n" not in raw_bytes

    ci_text = raw_bytes.decode("utf-8")
    required_fragments = (
        "permissions:",
        "contents: read",
        "ubuntu-latest",
        "timeout-minutes: 15",
        "actions/checkout@v4",
        "astral-sh/setup-uv@v5",
        "uv sync --locked",
        "uv run ruff check",
        "uv run ruff format --check",
        "uv run basedpyright",
        "uv run pytest",
    )
    for fragment in required_fragments:
        assert fragment in ci_text


def test_pydantic_distribution_metadata() -> None:
    version_str = importlib.metadata.version("pydantic")
    parts = version_str.split(".")
    major = int(parts[0])
    minor = int(parts[1])
    assert (major, minor) >= (2, 14)


def test_phase2_runtime_distribution_metadata() -> None:
    tzdata_version = importlib.metadata.version("tzdata")
    tz_parts = [int(p) for p in tzdata_version.split(".")[:2]]
    assert tuple(tz_parts) >= (2025, 2)

    pillow_version = importlib.metadata.version("pillow")
    pil_major = int(pillow_version.split(".")[0])
    assert 12 <= pil_major < 14


def test_phase3_runtime_distribution_metadata() -> None:
    httpx_version = importlib.metadata.version("httpx")
    httpx_parts = [int(p) for p in httpx_version.split(".")[:2]]
    assert tuple(httpx_parts) == (0, 28)

    openpyxl_version = importlib.metadata.version("openpyxl")
    openpyxl_parts = [int(p) for p in openpyxl_version.split(".")[:2]]
    assert (3, 1) <= tuple(openpyxl_parts) < (4, 0)


def _scan_forbidden_imports(
    pkg_dir: pathlib.Path,
    *,
    forbidden_roots: frozenset[str],
    forbidden_ets2v2_subpackages: frozenset[str],
) -> list[str]:
    violations: list[str] = []
    for py_file in sorted(pkg_dir.rglob("*.py")):
        tree = ast.parse(py_file.read_text("utf-8"), filename=str(py_file))
        rel = py_file.relative_to(REPO_ROOT).as_posix()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.name
                    root = name.split(".", 1)[0]
                    if root in forbidden_roots:
                        violations.append(f"{rel}: import {name}")
                    for subpkg in forbidden_ets2v2_subpackages:
                        if name == f"ets2v2.{subpkg}" or name.startswith(f"ets2v2.{subpkg}."):
                            violations.append(f"{rel}: import {name}")
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if node.level > 0:
                    top_rel = module.split(".", 1)[0] if module else ""
                    if top_rel in forbidden_ets2v2_subpackages:
                        violations.append(f"{rel}: from {'.' * node.level}{module} import ...")
                    elif not module:
                        for alias in node.names:
                            if alias.name in forbidden_ets2v2_subpackages:
                                violations.append(
                                    f"{rel}: from {'.' * node.level} import {alias.name}"
                                )
                    continue

                root = module.split(".", 1)[0] if module else ""
                if root in forbidden_roots:
                    violations.append(f"{rel}: from {module} import ...")
                for subpkg in forbidden_ets2v2_subpackages:
                    if module == f"ets2v2.{subpkg}" or module.startswith(f"ets2v2.{subpkg}."):
                        violations.append(f"{rel}: from {module} import ...")
                if module == "ets2v2":
                    for alias in node.names:
                        if alias.name in forbidden_ets2v2_subpackages:
                            violations.append(f"{rel}: from ets2v2 import {alias.name}")
    return violations


def test_phase4_ast_dag_isolation_walls() -> None:
    """Enforce all 6 AST-scanned offline DAG isolation walls (04-PATTERNS.md §1)."""
    src_root = REPO_ROOT / "src" / "ets2v2"
    online_third_party = frozenset({"httpx", "openpyxl"})

    wall_specs: dict[str, frozenset[str]] = {
        "validate": frozenset({"package", "merge", "normalize", "fetch", "publish"}),
        "merge": frozenset({"fetch", "publish"}),
        "package": frozenset({"fetch", "merge", "validate", "publish"}),
        "publish": frozenset({"fetch", "merge"}),
        "normalize": frozenset({"fetch", "registry", "package", "validate", "merge", "publish"}),
        "registry": frozenset({"fetch", "package", "validate", "merge", "publish"}),
    }

    for subpkg, forbidden_subpkgs in wall_specs.items():
        pkg_dir = src_root / subpkg
        assert pkg_dir.is_dir(), f"Expected subpackage directory {pkg_dir}"
        violations = _scan_forbidden_imports(
            pkg_dir,
            forbidden_roots=online_third_party,
            forbidden_ets2v2_subpackages=forbidden_subpkgs,
        )
        assert violations == [], f"AST DAG isolation violation in {subpkg}/: {violations}"
