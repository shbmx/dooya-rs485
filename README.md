<p align="center">
  <img src="images/logo.png" alt="Dooya Logo" width="150">
</p>

<h1 align="center">Dooya RS485 Home Assistant Integration</h1>

<p align="center">
  <a href="https://github.com/hacs/integration"><img src="https://img.shields.io/badge/HACS-Custom-41BDF5.svg" alt="HACS Badge"></a>
  <a href="https://github.com/shubham030/dooya-rs485/blob/main/LICENSE"><img src="https://img.shields.io/github/license/shubham030/dooya-rs485.svg" alt="License"></a>
</p>

<p align="center">
  A Home Assistant custom integration for controlling Dooya curtain motors via RS485 (through a TCP gateway).
</p>

---

## Features

- 🎛️ Control Dooya curtain motors (open, close, stop, toggle)
- 📍 Set specific positions (0-100%)
- 📊 Live position and motor status (opening / closing / stopped)
- ⚙️ Adjust device configuration from the UI (direction, hand-pull, switch types)
- 🔧 Program device addresses
- 📐 Calibrate motor direction and travel limits with the standalone script
- 🏠 Support for multiple curtains
- 🏃 Smooth position tracking — polls faster while the motor is moving
- 🩹 Guided calibration via a Home Assistant repair issue when the stroke isn't set
- 🔁 Automatic connection recovery and retry logic
- ⚡ Efficient polling with Home Assistant DataUpdateCoordinator
- 🔄 Auto-restart on failure (ConfigEntryNotReady)

## Prerequisites

- Home Assistant 2024.1.0 or newer
- RS485 to TCP gateway (configured and connected to your network)
- Dooya curtain motor with RS485 support

## Installation

### HACS (Recommended)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=shubham030&repository=dooya-rs485&category=integration)

1. Click the button above, or:
   - Open HACS in Home Assistant
   - Click on "Integrations"
   - Click the "+" button
   - Search for "Dooya RS485"
   - Click "Download"

2. Restart Home Assistant

3. Go to **Settings** → **Devices & Services** → **Add Integration** → Search for "Dooya RS485"

### Manual Installation

1. Download or clone this repository
2. Copy the `custom_components/dooya_rs485` folder to your Home Assistant's `custom_components` directory
3. Restart Home Assistant
4. Go to **Settings** → **Devices & Services** → **Add Integration** → Search for "Dooya RS485"

## Configuration

1. Go to Home Assistant **Settings** → **Devices & Services**
2. Click **Add Integration**
3. Search for "Dooya RS485"
4. Fill in the required information:

| Field | Description | Example |
|-------|-------------|---------|
| **Name** | A friendly name for your curtain | Living Room Curtain |
| **TCP Address** | IP address of your RS485 gateway | 192.168.1.100 |
| **TCP Port** | Port number of your RS485 gateway | 502 |
| **Device ID Low** | Low byte of the device address (0-255 or hex) | 0x02 |
| **Device ID High** | High byte of the device address (0-255 or hex) | 0xFE |

## Device Address Programming

The integration supports programming new device addresses. This is useful when you need to change the default factory address (0xFEFE) or assign unique addresses to multiple devices.

### Steps to Program a New Address

1. Press and hold the motor setting button for **5 seconds** until the LED flashes twice
2. Within **10 seconds**, call the `dooya_rs485.program_address` service:

```yaml
service: dooya_rs485.program_address
target:
  entity_id: cover.your_cover_name
data:
  address_low: 18   # New low byte (1-254)
  address_high: 52  # New high byte (1-254)
```

**Important Notes:**
- Address bytes cannot be `0x00` or `0xFF`
- Default factory address is `0xFEFE`
- LED will flash 5 times to confirm successful programming
- If programming fails, the device keeps its previous address

## Services

### `dooya_rs485.program_address`

Program a new device address.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `address_low` | int | Yes | Low byte of new address (1-254) |
| `address_high` | int | Yes | High byte of new address (1-254) |

### Standard Cover Services

All standard Home Assistant cover services are supported:

- `cover.open_cover` - Open the curtain fully
- `cover.close_cover` - Close the curtain fully
- `cover.stop_cover` - Stop the curtain at its current position
- `cover.set_cover_position` - Move the curtain to a specific position (0-100)
- `cover.toggle` - Toggle open/close using the motor's native negate command (`0x0F`)

## Attributes

The integration exposes several attributes. `motor_status` is read every poll
cycle; the remaining attributes are device *configuration* registers and are
read once when the integration loads.

| Attribute | Description | Values |
|-----------|-------------|--------|
| `current_position` | Current position | 0-100% |
| `motor_status` | Live motor status | stopped / opening / closing / setting |
| `direction` | Configured motor direction | default / reversed |
| `hand_pull_start` | Manual (hand-pull) start setting | enabled / disabled |
| `passive_switch_type` | Passive (weak current) switch type | double_bounce / non_bounce / dc246_electronic / single_key_cycle |
| `active_switch_type` | Active (high current) switch type | double_key_non_rebound / hotel_mode / double_key_rebound |

> **Note:** Opening/closing/stopped state is derived from the motor status
> register (`0x05`), per the Dooya protocol spec — `0x01` = opening, `0x02` =
> closing, `0x00` = stopped, `0x03` = setting. (There is no "error" status in
> the protocol.)

## Configuration Entities

Each curtain also creates writable configuration entities (grouped under the
device, in the **Configuration** category). These read their initial value once
at startup and write back to the motor when changed:

| Entity | Type | Register | Purpose |
|--------|------|----------|---------|
| **Reverse direction** | switch | `0x03` | Flip the motor direction if open/close are swapped — fix a reversed motor without re-wiring |
| **Hand-pull start** | switch | `0x04` | Enable/disable starting the motor by pulling the curtain by hand |
| **Passive switch type** | select | `0x27` | Weak-current external switch type (double bounce / non-bounce / DC246 / single-key cycle) |
| **Active switch type** | select | `0x28` | High-current external switch type (non-rebound / hotel mode / rebound) |

> These reflect the value read at startup; if you change a setting through the
> physical remote, reload the integration to refresh them.

## Auto-Recovery

The integration includes automatic recovery features:

| Scenario | Behavior |
|----------|----------|
| **Connection fails on startup** | Home Assistant retries automatically (30s, 60s, 120s...) |
| **Gateway not ready after reboot** | Keeps retrying until connection succeeds |
| **Connection lost while running** | Auto-reconnects on next poll cycle |
| **Multiple consecutive failures** | Logs warnings, continues trying |

## Troubleshooting

### Connection Issues

- ✅ Verify TCP gateway IP address and port
- ✅ Check physical RS485 connections (A/B wiring)
- ✅ Ensure correct device address is configured
- ✅ Check that no other application is using the TCP port

### Position Shows "Unknown" or 0xFF

This usually means the motor's stroke (travel limits) hasn't been set. When this
happens a **repair issue** appears under **Settings → System → Repairs** guiding
you through calibration:

1. Use the test script or Home Assistant to fully **open** the curtain
2. Then fully **close** the curtain
3. The stroke should now be calibrated, position will report 0-100%, and the
   repair issue clears automatically

### Communication Errors

- The integration automatically retries failed commands (up to 3 times)
- Connection will be automatically re-established if lost
- Check logs: **Settings** → **System** → **Logs**

### Address Programming Fails

- Ensure button is held until LED flashes **twice**
- Program address within **10 seconds** of LED signal
- Verify new address bytes are not `0x00` or `0xFF`

## Debug Logging

To enable debug logging, add this to your `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.dooya_rs485: debug
```

## Test Scripts

The repository includes standalone Python scripts for debugging and testing your setup outside of Home Assistant.

### test_connection.py

Tests the connection and reads device status (READ-ONLY, safe).

```bash
# Test with default address (0xFEFE)
python test_connection.py

# Test with custom address
python test_connection.py 0x02 0xFE
```

### test_set_stroke.py

Controls the curtain and monitors position in real-time.

```bash
# Open the curtain
python test_set_stroke.py open

# Close the curtain
python test_set_stroke.py close

# Stop immediately
python test_set_stroke.py stop

# Monitor position only (no movement)
python test_set_stroke.py monitor
```

### test_program_address.py

Programs a new RS485 address on a device. ⚠️ **This changes the device permanently!**

```bash
# Program address to 0xFE02
python test_program_address.py 0x02 0xFE

# Program address to 0x1234
python test_program_address.py 0x34 0x12
```

**Steps:**
1. Press and hold motor button for 5 seconds until LED flashes **twice**
2. Run the script within 10 seconds
3. LED flashes 5 times = success

**Note:** Edit the configuration section in each script to match your setup (IP, port, device ID).

### calibration.py

Calibrates motor direction and travel limits using the commands documented in
[the DM35EQX RS485 protocol reference](2_DM35EQX_codes_RS485.pdf).
The script runs independently of Home Assistant and uses only the Python standard library.

Set `TCP_ADDRESS`, `TCP_PORT`, `DEVICE_ID_L`, and `DEVICE_ID_H` before running it.
If you use `test_set_stroke.py` to move the motor, configure that script for the
same gateway and device address; their defaults differ.

| Action | Description |
|--------|-------------|
| `limits` | Read which of the four travel limits are set |
| `limit-up` | Save the current position as the upper limit |
| `limit-down` | Save the current position as the lower limit |
| `limit-3`, `limit-4` | Save the current position as the third or fourth limit |
| `settings` | Activate the motor's settings mode |
| `reverse` | Set motor direction to opposite (`0x01`; does not toggle) |
| `direction` | Restore the default motor direction (`0x00`) |
| `factory-reset` | Restore factory settings, clearing saved limits and settings |

Typical calibration workflow:

1. Run `python calibration.py limits` to inspect the existing limits.
2. If open/close are inverted, run `python calibration.py reverse`.
3. Move the motor to the desired upper position and stop it.
4. Run `python calibration.py limit-up`.
5. Move the motor to the desired lower position and stop it.
6. Run `python calibration.py limit-down`.
7. Run `python calibration.py limits` to check the saved limits.

⚠️ Commands other than `limits` change motor settings. Factory reset is optional;
it is not required for the workflow above. Running the script without an action
prints usage information without connecting to the gateway.

## Home Assistant Scripts & Automations

See the `examples/` folder for ready-to-use Home Assistant configurations:

- **`ha_scripts.yaml`** - Scripts for controlling curtains and programming addresses
- **`shell_commands.yaml`** - Shell commands to run test scripts from HA

### Example: Program Address from HA UI

Add to your `scripts.yaml`:

```yaml
program_dooya_address:
  alias: "Program Dooya Address"
  sequence:
    - service: dooya_rs485.program_address
      target:
        entity_id: cover.my_curtain
      data:
        address_low: 2    # 0x02
        address_high: 254 # 0xFE
```

### Example: Close Curtains at Sunset

```yaml
automation:
  - alias: "Close Curtains at Sunset"
    trigger:
      - platform: sun
        event: sunset
        offset: "+00:30:00"
    action:
      - service: cover.close_cover
        target:
          entity_id: cover.living_room_curtain
```

## Protocol Details

The integration uses the Dooya RS485 protocol:

| Parameter | Value |
|-----------|-------|
| Start Code | `0x55` |
| Read Command | `0x01` |
| Write Command | `0x02` |
| Control Command | `0x03` |
| Address Programming | `0x04` |
| CRC | CRC16 Modbus (little-endian) |
| Default Address | `0xFEFE` |

### Read Response Format (8 bytes)

```
[0] Start Code (0x55)
[1] Device ID Low
[2] Device ID High
[3] Function Code (0x01)
[4] Data Length (0x01)
[5] Data Value  ← Position / register value is here
[6] CRC Low
[7] CRC High
```

> Control-command replies (`0x03`) are **7 bytes** — they echo the data address
> at `[4]` and place the CRC at `[5:7]` (no data byte). Responses are validated
> for start byte, source device address, and CRC before use.

## Support

For bugs, feature requests, or support:

- 🐛 [Open an issue](https://github.com/shubham030/dooya-rs485/issues)
- 💻 [View source code](https://github.com/shubham030/dooya-rs485)
- 📖 [Discussions](https://github.com/shubham030/dooya-rs485/discussions)

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Credits

- Created and maintained by [@shubham030](https://github.com/shubham030)
- Dooya is a trademark of [Dooya](https://dooya.in/)

---

<p align="center">
  <a href="https://www.buymeacoffee.com/shubham030">
    <img src="https://img.buymeacoffee.com/button-api/?text=Buy me a coffee&emoji=☕&slug=shubham030&button_colour=FFDD00&font_colour=000000&font_family=Cookie&outline_colour=000000&coffee_colour=ffffff" />
  </a>
</p>
