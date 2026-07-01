"""Shared fixtures. The Orchestrator writes its audit DB to a path from
device.yaml; tests get an isolated copy of configs/ with an absolute temp DB
path so a test run never touches the repo's var/xray.db."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def config_dir(tmp_path: Path) -> Path:
    """A throwaway copy of configs/ with the audit DB redirected into tmp."""
    dst = tmp_path / "configs"
    shutil.copytree(_REPO_ROOT / "configs", dst)
    device = yaml.safe_load((dst / "device.yaml").read_text())
    device["storage"]["database_path"] = str(tmp_path / "xray.db")
    (dst / "device.yaml").write_text(yaml.safe_dump(device))
    return dst


@pytest.fixture
def orch(config_dir: Path):
    """A started Orchestrator on the mock camera with an isolated audit DB."""
    from xray_assist.app import Orchestrator

    o = Orchestrator(config_dir=config_dir)
    o.start()
    yield o
    o.stop()
