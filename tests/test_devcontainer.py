"""Tests for GitHub Codespaces and VS Code Dev Container configuration (.devcontainer/)."""

from __future__ import annotations

import json
import os
import subprocess

from basketlens import PROJECT_ROOT


def test_devcontainer_json_structure_and_codespaces_requirements() -> None:
    """Verify .devcontainer/devcontainer.json defines image, DinD, Git LFS, ports, and VS Code config."""
    devcontainer_path = PROJECT_ROOT / ".devcontainer" / "devcontainer.json"
    assert devcontainer_path.is_file(), "Missing .devcontainer/devcontainer.json"

    config = json.loads(devcontainer_path.read_text(encoding="utf-8"))

    assert config.get("image") == "mcr.microsoft.com/devcontainers/python:1-3.12-bookworm"

    features = config.get("features", {})
    dind_cfg = features.get("ghcr.io/devcontainers/features/docker-in-docker:2")
    assert isinstance(dind_cfg, dict), "Missing docker-in-docker:2 feature"
    assert dind_cfg.get("moby") is True
    assert dind_cfg.get("dockerDashComposeVersion") == "v2"

    lfs_cfg = features.get("ghcr.io/devcontainers/features/git-lfs:1")
    assert isinstance(lfs_cfg, dict), "Missing git-lfs:1 feature"
    assert lfs_cfg.get("autoPull") is True

    host_reqs = config.get("hostRequirements", {})
    assert host_reqs.get("cpus", 0) >= 2
    assert host_reqs.get("memory") == "8gb"
    assert host_reqs.get("storage") == "32gb"

    forward_ports = set(config.get("forwardPorts", []))
    expected_ports = {8081, 3000, 8082, 27017, 9042, 6379}
    assert expected_ports.issubset(forward_ports)

    ports_attr = config.get("portsAttributes", {})
    assert "Mongo Express" in ports_attr.get("8081", {}).get("label", "")
    assert "Cassandra Web" in ports_attr.get("3000", {}).get("label", "")
    assert "Redis Commander" in ports_attr.get("8082", {}).get("label", "")
    assert "MongoDB" in ports_attr.get("27017", {}).get("label", "")
    assert "Apache Cassandra" in ports_attr.get("9042", {}).get("label", "")
    assert "Redis" in ports_attr.get("6379", {}).get("label", "")

    assert config.get("postCreateCommand") == "bash .devcontainer/post-create.sh"

    vscode_cfg = config.get("customizations", {}).get("vscode", {})
    extensions = set(vscode_cfg.get("extensions", []))
    for required_ext in (
        "ms-python.python",
        "ms-python.vscode-pylance",
        "ms-toolsai.jupyter",
        "ms-azuretools.vscode-docker",
    ):
        assert required_ext in extensions, f"Missing VS Code extension: {required_ext}"

    settings = vscode_cfg.get("settings", {})
    assert settings.get("python.defaultInterpreterPath") == "${containerWorkspaceFolder}/.venv/bin/python"


def test_post_create_script_is_executable_and_matches_readme_steps() -> None:
    """Verify .devcontainer/post-create.sh is executable, valid bash, and runs README setup steps."""
    script_path = PROJECT_ROOT / ".devcontainer" / "post-create.sh"
    assert script_path.is_file(), "Missing .devcontainer/post-create.sh"
    assert os.access(script_path, os.X_OK), ".devcontainer/post-create.sh must be executable (+x)"

    syntax_check = subprocess.run(
        ["bash", "-n", str(script_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert syntax_check.returncode == 0, f"Bash syntax error: {syntax_check.stderr}"

    content = script_path.read_text(encoding="utf-8")
    for expected_snippet in (
        "git lfs pull",
        "python3 -m venv .venv",
        'pip install -e ".[dev]"',
        'python -m ipykernel install --user --name basketlens --display-name "Python (.venv BasketLens)"',
        "cp .env.example .env",
    ):
        assert expected_snippet in content, f"Missing expected bootstrap step in post-create.sh: {expected_snippet}"
