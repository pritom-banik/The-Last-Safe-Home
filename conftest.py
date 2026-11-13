"""Shared test fixtures: one synthetic demo site generated per test session into a temp DATA_DIR."""

import dataclasses

import pytest

from pipeline import cli
from pipeline.lsh.config import get_settings


@pytest.fixture(scope="session")
def demo_data_dir(tmp_path_factory):
    """`python -m pipeline.cli all --site demo` into a temp data dir; returns that DATA_DIR."""
    data = tmp_path_factory.mktemp("data")
    mp = pytest.MonkeyPatch()
    mp.setenv("DATA_DIR", str(data))
    try:
        assert cli.main(["all", "--site", "demo"]) == 0
    finally:
        mp.undo()
    return data


@pytest.fixture(scope="session")
def demo_settings(demo_data_dir):
    return dataclasses.replace(get_settings(), data_dir=demo_data_dir, sites=["demo", "manpura"])
