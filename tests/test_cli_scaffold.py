"""Scaffold, CLI tracer, and active-phase boundary tests for ets2v2."""

from __future__ import annotations

import argparse
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
    deferred_phase_dirs = {"fetch", "normalize", "merge"}
    allowed_phase2_entries = {
        "__init__.py",
        "py.typed",
        "cli.py",
        "vfs",
        "sii",
        "baseline",
        "registry",
        "package",
        "validate",
        "publish",
    }

    assert entries.isdisjoint(deferred_phase_dirs)
    assert entries <= allowed_phase2_entries
    assert {"__init__.py", "py.typed", "cli.py"} <= entries


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
        "pydantic",
        "tzdata",
        "pillow",
        "basedpyright",
        "pytest",
        "pytest-cov",
        "ruff",
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
