# Copyright (c) 2025 Nordic Semiconductor ASA
#
# SPDX-License-Identifier: LicenseRef-Nordic-5-Clause

"""Pytest plugin to share common fixtures among the tests."""

import logging
import os
from pathlib import Path

import pytest
from pytest_plugins.adapters.west import west_build
from twister_harness.device.device_adapter import DeviceAdapter
from twister_harness.fixtures import determine_scope

logger = logging.getLogger(__name__)


def pytest_addoption(parser: pytest.Parser):
    parser.addoption("--build", action="store_true", help="Build sample before running test")


def pytest_configure(config):
    config.addinivalue_line(
        'markers', 'sample(path_to_sample_dir, scenario_name): sample used by test'
    )


def pytest_runtest_setup(item: pytest.Item):
    if (
        (marker := item.get_closest_marker(name="sample"))
        and item.config.option.build
        and (platform := item.config.option.platform)
    ):
        assert len(marker.args) == 2, "Not enough parameters in sample marker"
        source_dir, testsuite = marker.args
        source_dir = item.path.parent.joinpath(source_dir).resolve()
        logger.info("Building sample: %s::%s", source_dir, testsuite)
        west_build(
            source_dir=source_dir,
            board=platform,
            build_dir=Path(item.config.option.build_dir).resolve(),
            testsuite=testsuite,
        )


@pytest.fixture(scope="session")
def nrf_bm_path() -> Path:
    """Return path to sdk-bm repository."""
    return Path(__file__).parents[2]


@pytest.fixture(scope="session")
def zephyr_base() -> Path:
    """Return path to zephyr repository."""
    return Path(os.getenv("ZEPHYR_BASE", ""))


@pytest.fixture(scope=determine_scope)
def no_reset(device_object: DeviceAdapter):
    """Do not reset after flashing."""
    device_object.device_config.west_flash_extra_args.append("--no-reset")
    yield
    device_object.device_config.west_flash_extra_args.remove("--no-reset")
