# Copyright (c) 2026 Nordic Semiconductor ASA
#
# SPDX-License-Identifier: LicenseRef-Nordic-5-Clause

import time
from pathlib import Path
from typing import Any

import pytest
from pytest_plugins.adapters.builder import WestBuilder
from pytest_plugins.adapters.nrfutil import list_devices, reset_board
from twister_harness import DeviceAdapter, MCUmgr

KMU_ROOT: Path = Path(__file__).parents[1]


def get_available_ports(devices: list[dict[str, Any]], serial_number: str) -> list[str]:
    """Return list of UART ports."""
    for device in devices:
        if device["serialNumber"] == serial_number:
            return [serial_port["path"] for serial_port in device["serialPorts"]]

    raise ValueError(f"Cannot find a device with serial number: {serial_number}")


@pytest.fixture
def mcumgr(dut: DeviceAdapter) -> MCUmgr:
    devices = list_devices()["devices"]
    # we know that we need the first port for this board and sample
    serial_port = get_available_ports(devices, dut.device_config.id)[0]
    mcumgr = MCUmgr.create_for_serial(serial_port)
    return mcumgr


def test_if_uploading_too_large_softdevice_image_is_not_possible(
    dut: DeviceAdapter, request: pytest.FixtureRequest, mcumgr: MCUmgr
):
    """Uploading too large SoftDevice image.

    Should not be possible to upload an image which does not fit size of a partition.

    - Build updated SoftDevice image which is too large to fit partition size for SoftDevice
      (e.g. manipulate partition size to get such image).
    - Program the initial application to the device.
    - Reset the device.
    - Verify if booted correctly.
    - Enter DFU.
    - Upload SoftDevice, firmware loader and Installer.
    - Reset the device.
    - Verify that the device enters DFU mode due to it cannot upload SoftDevice
      because its size is too big to fit the SoftDevice partition size.
    """
    application_name = "dfu"
    source_dir = KMU_ROOT / dut.device_config.build_dir.parent.name
    build_dir = dut.device_config.build_dir.parent / f"{request.node.name}_s145_softdevice"
    testsuite = "boot.mcuboot_recovery_retention.uart"
    lines = dut.readlines_until(regex="Waiting...", timeout=5)
    lines += dut.readlines_until(regex="Jumping to the first image slot", timeout=5)

    # build a sample that does not fit a softdevice partion size
    board = dut.device_config.platform.replace("s115_softdevice", "s145_softdevice")
    builder = WestBuilder(
        source_dir=source_dir,
        build_dir=build_dir,
        board=board,
        testsuite=testsuite,
        timeout=120,
    )
    builder.build()

    time.sleep(1)
    assert mcumgr.get_image_list()

    mcumgr.image_upload(build_dir / "installer_softdevice_firmware_loader.bin")
    dut.clear_buffer()
    reset_board(dut.device_config.id)
    lines = dut.readlines_until(
        regex="Booting firmware loader due to missing application image", timeout=10
    )
    pytest.LineMatcher(lines).fnmatch_lines(["*Failed loading application/installer image header*"])

    # Uplaod again all images and verify it DUT boots correctly
    mcumgr.image_upload(dut.device_config.build_dir / "installer_softdevice_firmware_loader.bin")
    dut.clear_buffer()
    reset_board(dut.device_config.id)

    lines = dut.readlines_until(
        regex="Booting firmware loader due to missing application image", timeout=10
    )
    pytest.LineMatcher(lines).fnmatch_lines(
        ["*Booting firmware loader due to missing application image*"]
    )

    # upload application
    mcumgr.image_upload(
        dut.device_config.build_dir / f"{application_name}/zephyr/zephyr.signed.bin"
    )
    dut.clear_buffer()
    reset_board(dut.device_config.id)

    lines = dut.readlines_until(regex="Waiting...", timeout=10)
    pytest.LineMatcher(lines).fnmatch_lines(["*Booting main application*"])
