"""Cleanroom install test.

Verifies that the plugin loads cleanly when installed from scratch
(fresh copy, no .git, no caches, no fixture artifacts), via the same
mechanism Antigravity uses to load plugins from a marketplace.

This is the load-bearing test that prevents the v1.0.0/v1.0.1 regression
where the plugin shipped but never actually loaded in Cowork — those
versions passed unit tests + manifest validation, but the install path
itself was broken and the failure was only caught by a real
`Antigravity plugin list` against an isolated install.

This test runs `Antigravity --plugin-dir <tempdir> plugin list` to confirm
the loader recognizes the plugin and reports it as loaded.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent


def _project_files_to_copy() -> list[str]:
    """Top-level entries that constitute a shippable copy of the plugin."""
    return [
        ".Antigravity-plugin",
        "skills",
        "commands",
        "pipelines",
        "scripts",
        "hooks",
        "ARCHITECTURE.md",
        "CHANGELOG.md",
        "CONTRIBUTING.md",
        "LICENSE",
        "README.md",
        "USER-MANUAL.md",
    ]


def _copy_plugin_to(dest: Path) -> None:
    """Copy a clean snapshot of the plugin to dest.

    Deliberately excludes .git, .agent-runs (run artifacts from fixture
    exercises), .pytest_cache, __pycache__, and tests/fixtures/* nested
    runtime artifacts. Includes the tracked plugin payload only.
    """
    dest.mkdir(parents=True, exist_ok=True)
    for name in _project_files_to_copy():
        src = REPO_ROOT / name
        if not src.exists():
            continue
        dst = dest / name
        if src.is_dir():
            shutil.copytree(
                src,
                dst,
                ignore=shutil.ignore_patterns(
                    "__pycache__",
                    "*.pyc",
                    ".pytest_cache",
                    ".agent-runs",
                ),
            )
        else:
            shutil.copy2(src, dst)


def _Antigravity_bin() -> str:
    """Resolve the Antigravity CLI binary path."""
    return shutil.which("Antigravity") or "Antigravity"


def _supports_plugin_commands() -> bool:
    bin_path = _Antigravity_bin()
    if shutil.which(bin_path) is None:
        return False
    try:
        res = subprocess.run([bin_path, "--help"], capture_output=True, text=True, errors="replace", timeout=10)
        return "plugin" in res.stdout or "plugin" in res.stderr
    except Exception:
        return False


def test_cleanroom_install_loads_via_plugin_dir(tmp_path: Path) -> None:
    """Fresh copy of plugin → `Antigravity --plugin-dir <copy> plugin list` →
    plugin reports ✔ loaded with the manifest-declared version.

    This is a cleanroom test: no .git, no caches, no installed_plugins.json
    entries — just the plugin source on disk and the Antigravity CLI loading it.
    """
    if shutil.which("Antigravity") is None:
        pytest.skip("Antigravity CLI not on PATH; cleanroom load test requires it")
    if not _supports_plugin_commands():
        pytest.skip("Antigravity CLI does not support plugin subcommands/options")

    install_dir = tmp_path / "agent-pipeline-antigravity"
    _copy_plugin_to(install_dir)

    # Manifest must exist after copy
    manifest_path = install_dir / ".Antigravity-plugin" / "plugin.json"
    assert manifest_path.is_file(), f"manifest missing from copy: {manifest_path}"

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    declared_version = manifest["version"]
    plugin_name = manifest["name"]

    # Run Antigravity --plugin-dir <copy> plugin list and assert
    result = subprocess.run(
        [_Antigravity_bin(), "--plugin-dir", str(install_dir), "plugin", "list"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )
    combined_output = result.stdout + result.stderr

    assert plugin_name in combined_output, (
        f"plugin name {plugin_name!r} not found in `Antigravity plugin list` output.\n"
        f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
    )
    # Look for a loaded/enabled status line near the plugin name
    loaded_marker = re.search(
        rf"{re.escape(plugin_name)}.*?(Status:\s*[✔✓✅√]\s*(loaded|enabled))",
        combined_output,
        re.DOTALL | re.IGNORECASE,
    )
    assert loaded_marker is not None, (
        f"no '✔ loaded' or '✔ enabled' status found near {plugin_name!r}.\n"
        f"--- output ---\n{combined_output}"
    )
    assert declared_version in combined_output, (
        f"manifest version {declared_version!r} not in output (loader may be reading a different copy).\n"
        f"--- output ---\n{combined_output}"
    )


def test_cleanroom_install_validates(tmp_path: Path) -> None:
    """Fresh copy must pass `Antigravity plugin validate` on both manifests."""
    if shutil.which("Antigravity") is None:
        pytest.skip("Antigravity CLI not on PATH")
    if not _supports_plugin_commands():
        pytest.skip("Antigravity CLI does not support plugin subcommands/options")

    install_dir = tmp_path / "agent-pipeline-antigravity"
    _copy_plugin_to(install_dir)

    for manifest_rel in (".Antigravity-plugin/plugin.json", ".Antigravity-plugin/marketplace.json"):
        result = subprocess.run(
            [_Antigravity_bin(), "plugin", "validate", str(install_dir / manifest_rel)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
        out = result.stdout + result.stderr
        assert "Validation passed" in out or "✔" in out, (
            f"`Antigravity plugin validate {manifest_rel}` did not pass.\n"
            f"--- output ---\n{out}"
        )


def test_cleanroom_install_structure_check(tmp_path: Path) -> None:
    """Fresh copy must pass the structural check from inside it.

    This catches the case where a path-resolution bug in
    check_plugin_structure.py only manifests when the plugin lives
    outside the dev clone.
    """
    install_dir = tmp_path / "agent-pipeline-antigravity"
    _copy_plugin_to(install_dir)

    # Note: check_plugin_structure.py lives at tests/ in the source repo,
    # not in the shipped plugin payload. Run the source-repo copy against
    # the cleanroom install dir as its cwd to verify path resolution.
    # Use sys.executable (the current Python interpreter path) so this
    # works on systems where `python` isn't on PATH (Ubuntu 24.04 ships
    # only `python3` by default).
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "tests" / "check_plugin_structure.py")],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=install_dir,
        timeout=30,
    )
    out = result.stdout + result.stderr
    assert "ALL CHECKS PASSED" in out, (
        f"check_plugin_structure.py failed against cleanroom install.\n"
        f"--- output ---\n{out}"
    )
