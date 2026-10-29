#!/usr/bin/env python3
"""
Dooya RS485 Motor Calibration Script
=====================================

Handles motor calibration: direction, limits, and factory reset.

⚠️  WARNING: Some commands permanently change motor settings!

Usage:
    python calibration.py [action]

Actions:
    limits        - Read which limits are currently set (read-only)
    limit-up      - Set upper limit (limit 1) at current position
    limit-down    - Set lower limit (limit 2) at current position
    limit-3       - Set third limit at current position
    limit-4       - Set fourth limit at current position
    settings      - Activate settings mode (write motor status reg = 0x03)
    reverse       - Set motor direction to opposite (write dir reg = 0x01)
    direction     - Reset motor direction to default (write dir reg = 0x00)
    factory-reset - Reset to factory defaults (⚠️  clears ALL limits!)

Typical calibration workflow:
    1. python calibration.py limits          # inspect existing limits
    2. python calibration.py reverse         # if open/close are inverted
    3. Move motor to UP position manually or via test_set_stroke.py
    4. python calibration.py limit-up
    5. Move motor to DOWN position
    6. python calibration.py limit-down
    7. python calibration.py limits          # verify

Configuration:
    Edit the constants below to match your setup:
    - TCP_ADDRESS: IP address of your RS485-to-TCP gateway
    - TCP_PORT: Port number of the gateway
    - DEVICE_ID_L: Low byte of device address
    - DEVICE_ID_H: High byte of device address

Notes:
    - Use the same gateway and device address in test_set_stroke.py
    - Set each limit only after stopping at the desired position
    - Factory reset is optional and clears all saved limits and settings
    - See 2_DM35EQX_codes_RS485.pdf for the calibration registers and commands

Author: ogerman
License: MIT
"""

import asyncio
import binascii
import sys

# =============================================================================
# CONFIGURATION - Edit these values to match your setup
# =============================================================================
TCP_ADDRESS = "192.168.1.2"
TCP_PORT = 502
DEVICE_ID_L = 0xFE
DEVICE_ID_H = 0xFE

# =============================================================================
# PROTOCOL CONSTANTS - Do not modify unless you know the protocol
# =============================================================================
START_CODE = 0x55
CURTAIN_READ = 0x01
CURTAIN_WRITE = 0x02  # Write to register
CURTAIN_COMMAND = 0x03  # Control command

# Set limit sub-command (under CURTAIN_COMMAND)
CURTAIN_SET_LIMIT = 0x05
CURTAIN_LIMIT_UP = 0x01
CURTAIN_LIMIT_DOWN = 0x02
CURTAIN_LIMIT_3 = 0x03
CURTAIN_LIMIT_4 = 0x04

# Factory reset sub-command (under CURTAIN_COMMAND)
CURTAIN_FACTORY_RESET = 0x08

# Motor direction register (written via CURTAIN_WRITE)
CURTAIN_MOTOR_DIR_REG = 0x03
CURTAIN_DIR_DEFAULT = 0x00
CURTAIN_DIR_OPPOSITE = 0x01

# Settings mode: write 0x03 to motor status register 0x05
CURTAIN_MOTOR_STATUS_REG = 0x05
CURTAIN_SETTINGS_MODE = 0x03

# Limit status register (read via CURTAIN_READ)
CURTAIN_LIMIT_STATUS = 0x09
LIMIT_BIT1 = 0x01  # Limit 1 (up) is set
LIMIT_BIT2 = 0x02  # Limit 2 (down) is set
LIMIT_BIT3 = 0x04  # Limit 3 is set
LIMIT_BIT4 = 0x08  # Limit 4 is set

LIMIT_MAP = {
    "limit-up": (CURTAIN_LIMIT_UP, "up limit"),
    "limit-down": (CURTAIN_LIMIT_DOWN, "down limit"),
    "limit-3": (CURTAIN_LIMIT_3, "third limit"),
    "limit-4": (CURTAIN_LIMIT_4, "fourth limit"),
}

VALID_ACTIONS = [
    "limits",
    "limit-up",
    "limit-down",
    "limit-3",
    "limit-4",
    "settings",
    "reverse",
    "direction",
    "factory-reset",
]


def calculate_crc(data: bytes) -> bytes:
    """Calculate CRC16 Modbus checksum.

    Args:
        data: Bytes to calculate CRC for

    Returns:
        2-byte CRC in little-endian format
    """
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x0001:
                crc >>= 1
                crc ^= 0xA001
            else:
                crc >>= 1
    return crc.to_bytes(2, byteorder="little")


async def send_command(writer, reader, cmd_bytes: bytes, name: str) -> bytes | None:
    """Send a command and print request/response.

    Args:
        writer: Async stream writer
        reader: Async stream reader
        cmd_bytes: Command bytes (without START, ID, or CRC)
        name: Command name for logging

    Returns:
        Response bytes or None on timeout
    """
    command = bytes([START_CODE, DEVICE_ID_L, DEVICE_ID_H]) + cmd_bytes
    command += calculate_crc(command)
    print(f"📤 {name}: {binascii.hexlify(command).decode().upper()}")
    writer.write(command)
    await writer.drain()
    try:
        response = await asyncio.wait_for(reader.read(1024), timeout=3.0)
        print(f"📥 Response: {binascii.hexlify(response).decode().upper()}")
        return response
    except TimeoutError:
        print("   ⏱️  No response (timeout)")
        return None


async def read_limit_status(writer, reader) -> None:
    """Read and display which limits are set (register 0x09 bitmask)."""
    command = bytes(
        [START_CODE, DEVICE_ID_L, DEVICE_ID_H, CURTAIN_READ, CURTAIN_LIMIT_STATUS, 0x01]
    )
    command += calculate_crc(command)
    print(f"📤 READ LIMIT STATUS: {binascii.hexlify(command).decode().upper()}")
    writer.write(command)
    await writer.drain()
    try:
        response = await asyncio.wait_for(reader.read(1024), timeout=3.0)
        print(f"📥 Response: {binascii.hexlify(response).decode().upper()}")
        if len(response) >= 6:
            status = response[5]
            print("\nLimit status:")
            print(
                f"  Limit 1 (up):   {'✅ SET' if status & LIMIT_BIT1 else '❌ not set'}"
            )
            print(
                f"  Limit 2 (down): {'✅ SET' if status & LIMIT_BIT2 else '❌ not set'}"
            )
            print(
                f"  Limit 3:        {'✅ SET' if status & LIMIT_BIT3 else '❌ not set'}"
            )
            print(
                f"  Limit 4:        {'✅ SET' if status & LIMIT_BIT4 else '❌ not set'}"
            )
        else:
            print("⚠️  Unexpected response length")
    except TimeoutError:
        print("   ⏱️  No response (timeout)")


async def read_direction(writer, reader) -> int | None:
    """Read current motor direction register."""
    command = bytes(
        [
            START_CODE,
            DEVICE_ID_L,
            DEVICE_ID_H,
            CURTAIN_READ,
            CURTAIN_MOTOR_DIR_REG,
            0x01,
        ]
    )
    command += calculate_crc(command)
    writer.write(command)
    await writer.drain()
    try:
        response = await asyncio.wait_for(reader.read(1024), timeout=3.0)
        if len(response) >= 6:
            return response[5]
    except TimeoutError:
        pass
    return None


def print_usage():
    """Print usage information."""
    print("=" * 60)
    print("Dooya RS485 Motor Calibration")
    print("=" * 60)
    print()
    print("Usage: python calibration.py [action]")
    print()
    print("Actions:")
    print("  limits        - Read which limits are set (read-only)")
    print("  limit-up      - Set upper limit at current position")
    print("  limit-down    - Set lower limit at current position")
    print("  limit-3       - Set third limit at current position")
    print("  limit-4       - Set fourth limit at current position")
    print("  settings      - Activate settings mode")
    print("  reverse       - Set motor direction to opposite")
    print("  direction     - Reset motor direction to default")
    print("  factory-reset - ⚠️  Reset to factory defaults (clears limits!)")
    print()
    print("Current config:")
    print(f"  Address: {TCP_ADDRESS}:{TCP_PORT}")
    print(f"  Device:  0x{DEVICE_ID_H:02X}{DEVICE_ID_L:02X}")
    print()


async def main():
    """Main entry point."""
    action = sys.argv[1] if len(sys.argv) > 1 else None

    if not action or action not in VALID_ACTIONS:
        print_usage()
        if action:
            print(f"❌ Unknown action: {action}")
        return 1

    print_usage()
    print(f"Action: {action.upper()}")
    print("=" * 60)

    try:
        reader, writer = await asyncio.open_connection(TCP_ADDRESS, TCP_PORT)
        print("✅ Connected!\n")
    except OSError as e:
        print(f"❌ Connection failed: {e}")
        return 1

    try:
        if action == "limits":
            await read_limit_status(writer, reader)

        elif action in LIMIT_MAP:
            limit_num, label = LIMIT_MAP[action]
            print(f"📍 Setting {label} (limit {limit_num}) at current position...")
            await send_command(
                writer,
                reader,
                bytes([CURTAIN_COMMAND, CURTAIN_SET_LIMIT, limit_num]),
                f"SET LIMIT {limit_num} ({label})",
            )
            print()
            await read_limit_status(writer, reader)

        elif action == "settings":
            print("⚙️  Activating settings mode (write motor status reg 0x05 = 0x03)...")
            await send_command(
                writer,
                reader,
                bytes(
                    [
                        CURTAIN_WRITE,
                        CURTAIN_MOTOR_STATUS_REG,
                        0x01,
                        CURTAIN_SETTINGS_MODE,
                    ]
                ),
                "SETTINGS MODE",
            )

        elif action == "reverse":
            cur = await read_direction(writer, reader)
            print(
                f"Current direction register: 0x{cur:02X} ({'default' if cur == 0 else 'opposite'})"
                if cur is not None
                else "Could not read direction"
            )
            print("\n🔄 Setting direction to OPPOSITE (0x01)...")
            await send_command(
                writer,
                reader,
                bytes(
                    [CURTAIN_WRITE, CURTAIN_MOTOR_DIR_REG, 0x01, CURTAIN_DIR_OPPOSITE]
                ),
                "SET DIR OPPOSITE",
            )

        elif action == "direction":
            cur = await read_direction(writer, reader)
            print(
                f"Current direction register: 0x{cur:02X} ({'default' if cur == 0 else 'opposite'})"
                if cur is not None
                else "Could not read direction"
            )
            print("\n🔄 Setting direction to DEFAULT (0x00)...")
            await send_command(
                writer,
                reader,
                bytes(
                    [CURTAIN_WRITE, CURTAIN_MOTOR_DIR_REG, 0x01, CURTAIN_DIR_DEFAULT]
                ),
                "SET DIR DEFAULT",
            )

        elif action == "factory-reset":
            print("⚠️  Sending FACTORY RESET (clears all limits)...")
            await send_command(
                writer,
                reader,
                bytes([CURTAIN_COMMAND, CURTAIN_FACTORY_RESET]),
                "FACTORY RESET",
            )

    except KeyboardInterrupt:
        print("\n⚠️  Interrupted.")
    finally:
        writer.close()
        await writer.wait_closed()
        print("\n🔌 Disconnected.")

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
