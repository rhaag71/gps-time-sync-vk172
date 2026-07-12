# gps-time-sync-vk172

`gps-time-sync-vk172` reads UTC time from a VK172/GK172 USB GPS receiver, validates its NMEA data, and can either report GPS time and fix information safely or set the Linux system clock when given sufficient privileges. It is intended for Linux and similar Unix-like systems.

## Project status

The utility is functional and has been tested with a VK172 USB GPS receiver. Packaging, core parsing and clock behavior, CLI paths, the shell wrapper, and deployment artifacts have automated tests. A reviewed systemd deployment path is available, while advanced site-specific privilege and time-service integration still require deliberate administration. Review [Known Issues and Remaining Work](KNOWN_ISSUES_AND_TODO.md) before relying on the project in an important deployment.

## Supported hardware and platform

- VK172/GK172 USB GPS receivers that expose NMEA data over a serial device.
- Linux or a similar Unix-like system with Python 3.10 or newer.
- Common device names include `/dev/ttyACM0` and `/dev/ttyUSB0`.
- For unattended use, prefer a stable `/dev/serial/by-id/...` symlink.
- The user running the tool must be able to open the serial device. On many Linux distributions this is controlled by membership in `dialout` or an equivalent group.

Other NMEA receivers may work, but the VK172 is the hardware tested by the project owner.

## Features

- Validates NMEA checksums before using receiver data.
- Reads UTC date and time from RMC sentences.
- Collects fix quality, fix mode, dilution, and satellite information from GGA, GSA, and GSV sentences.
- Accepts common GPS and multi-constellation talker IDs, including `GP` and `GN`.
- Provides read-only status and time-display modes.
- Sets the system clock in normal mode when permitted.
- Includes a configurable Bash wrapper for repository-local virtual environments.

## Requirements

- Python 3.10 or newer.
- A working Python virtual-environment module (`python3 -m venv`).
- Serial access to the receiver.
- Root or the narrowly scoped `CAP_SYS_TIME` capability only when setting the system clock.

The Python package installs `pyserial` automatically.

## Installation

Clone the repository and create an isolated environment:

```bash
git clone https://github.com/rhaag71/gps-time-sync-vk172.git
cd gps-time-sync-vk172
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[test]'
```

`python3` creates the environment. After activation, `python`, `pip`, `pytest`, and `gps-time-sync` refer to programs installed in that environment. Contributors should install the `test` extra as shown above.

For a runtime-only editable installation without pytest:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

See [Contributor Setup](docs/contributor-setup.md) for development-environment maintenance and build commands.

## Finding the GPS device

Connect the receiver and watch kernel device messages:

```bash
dmesg --follow
```

In another terminal, inspect stable serial-device links:

```bash
ls -l /dev/serial/by-id/
```

Depending on the adapter, kernel driver, and connection order, the receiver may appear as `/dev/ttyACM0`, `/dev/ttyUSB0`, or another numbered device. A `/dev/serial/by-id/...` link remains more stable across reboots and connection-order changes, so use it for cron and future service-based deployment when available.

## Quick start

With the virtual environment active, inspect time and receiver status without changing the clock:

```bash
gps-time-sync --status --port /dev/ttyACM0
```

Display the acquired time without extended status collection or a clock change:

```bash
gps-time-sync --no-set --port /dev/ttyACM0
```

Set the system clock from the repository virtual environment:

```bash
sudo .venv/bin/gps-time-sync --port /dev/ttyACM0
```

Replace `/dev/ttyACM0` with the device found on your system.

## Safe read-only modes

### Status mode

`--status` never sets the system clock. It prints GPS UTC time, the corresponding local time, fix state, and available satellite metrics. After receiving a valid RMC timestamp, it continues collecting details for up to `--status-window` seconds. The overall acquisition timeout still caps this collection.

```bash
gps-time-sync --status --port /dev/ttyACM0 --status-window 2
```

### No-set mode

`--no-set` never sets the system clock. It reports the first valid acquired GPS time and does not request extended status collection.

```bash
gps-time-sync --no-set --port /dev/ttyACM0
```

These modes need serial-device permission, but they do not need clock-setting permission.

## Synchronizing the system clock

Without `--status` or `--no-set`, the command attempts to set the system clock exactly once after acquiring valid GPS time:

```bash
sudo .venv/bin/gps-time-sync --port /dev/ttyACM0
```

Serial access and clock-setting authority are separate permissions:

- Membership in `dialout` or an equivalent group commonly permits access to the serial device.
- Root or `CAP_SYS_TIME` permits changing the system clock.
- Serial-group membership alone does not permit clock changes.

Grant capabilities only after considering the security implications for the executable and interpreter involved. Read-only modes are preferable while identifying the device and confirming reception.

## Command reference

Run `gps-time-sync --help` for the authoritative generated help.

| Option | Current behavior and default |
| --- | --- |
| `--port PATH` | Serial device; default `/dev/ttyUSB0`. |
| `--baudrate RATE` | Serial baud rate; default `9600`. |
| `--timeout SECONDS` | Non-negative time allowed for GPS data acquisition after warmup; default `60.0`. |
| `--warmup SECONDS` | Non-negative delay after opening the serial device and before acquisition timing begins; default `2.0`. |
| `--status-window SECONDS` | Non-negative detail-collection window after the first valid timestamp in status mode; default `2.0`. |
| `--status` | Print time and detailed receiver status without setting the clock. |
| `--no-set` | Print acquired time without setting the clock or requesting detailed status. |
| `--verbose` | Enable debug logging. |
| `--help` | Show CLI help and exit. |

Warmup happens first. The acquisition timeout starts afterward. When status mode receives a valid timestamp, its status window is bounded by the time remaining in the overall acquisition timeout; status collection never extends that deadline.

## Using `scripts/gps_sync.sh`

The wrapper locates `.venv/bin/gps-time-sync` relative to its own repository and supplies useful defaults. It does not activate or depend on the caller's shell environment.

Show its help without requiring `.venv`:

```bash
scripts/gps_sync.sh --help
```

Run with wrapper defaults (`/dev/ttyACM0`, 9600 baud, 60-second timeout, 2-second warmup, and 2-second status window):

```bash
scripts/gps_sync.sh
```

Override selected values on the command line:

```bash
scripts/gps_sync.sh \
  --port /dev/serial/by-id/usb-example \
  --timeout 90 \
  --status
```

The wrapper supports `--port`, `--baudrate`, `--timeout`, `--warmup`, `--status-window`, `--status`, `--no-set`, `--verbose`, and `--help`. See its help rather than duplicating the complete parser details here.

## Environment-variable configuration

The wrapper recognizes:

- `GPS_PORT`
- `GPS_BAUDRATE`
- `GPS_TIMEOUT`
- `GPS_WARMUP`
- `GPS_STATUS_WINDOW`

For example:

```bash
GPS_PORT=/dev/serial/by-id/usb-example \
GPS_TIMEOUT=90 \
scripts/gps_sync.sh --status
```

Precedence is exactly:

```text
command-line options > environment variables > built-in defaults
```

## Automation with systemd

For unattended Linux deployment, the preferred path is the supplied root-run oneshot service and 15-minute timer. Install it from a controlled, system-owned location such as `/opt/gps-time-sync-vk172`, configure a stable `/dev/serial/by-id/...` device, and let output go to journald.

See [systemd Deployment](docs/systemd-deployment.md) for installation, environment configuration, privilege boundaries, timer behavior, logs, failure handling, removal, and interaction with `systemd-timesyncd`, Chrony, or `ntpd`. The units do not disable competing time services automatically.

## Automation with cron

Cron remains a simpler alternative. If clock setting is required, edit root's crontab with `sudo crontab -e`. Use an absolute repository path, a stable serial-device path, and explicit logging:

```cron
*/15 * * * * GPS_PORT=/dev/serial/by-id/usb-example /path/to/gps-time-sync-vk172/scripts/gps_sync.sh >> /var/log/gps-sync.log 2>&1
```

Confirm that the checkout and virtual environment are managed appropriately and not casually mutable by unrelated users. Do not enable both cron and the systemd timer for the same installation.

Before automating clock changes, decide how this utility should interact with any existing network time service.

## Troubleshooting

### No serial device appears

Reconnect the receiver while running `dmesg --follow`, then compare:

```bash
ls -l /dev/ttyACM0
ls -l /dev/serial/by-id/
```

The device may be named `ttyUSB` rather than `ttyACM`, or its numeric suffix may differ.

### Permission denied opening the serial device

Inspect ownership and your current groups:

```bash
ls -l /dev/ttyACM0
groups
```

Many distributions grant access through `dialout`; group names and device rules vary. Log out and back in after an administrator changes group membership.

### Timeout waiting for a GPS fix

Move the receiver near a window or outdoors with a clear view of the sky, increase `--timeout`, and use `--verbose` for diagnostics. Initial acquisition and poor indoor reception can take longer. Confirm the selected port and baud rate.

### `gps-time-sync` is not found

Activate the intended environment and inspect the installation:

```bash
source .venv/bin/activate
which gps-time-sync
python -m pip show gps-time-sync-vk172
```

Alternatively, call `.venv/bin/gps-time-sync` explicitly.

### The project or virtual environment was moved

Virtual environments contain absolute paths. Recreate `.venv` after moving or renaming the checkout, then reinstall the project rather than relying on stale entry points.

### Normal mode reports a permission error

First verify that `--status` or `--no-set` works. Normal mode additionally needs root or suitable `CAP_SYS_TIME` authority; `dialout` access alone is insufficient.

### The clock changes again after a successful sync

`systemd-timesyncd`, Chrony, or another NTP daemon may subsequently adjust the clock. Deliberately choose which time source should be authoritative and configure the relevant service for that policy; there is no universal configuration suitable for every host.

### Malformed receiver input is skipped

The reader strictly decodes ASCII and validates checksums. A read containing non-ASCII bytes or an invalid checksum is skipped rather than silently altered. Use `--verbose` to see debug diagnostics and check the serial connection if this happens repeatedly.

## Limitations and operational notes

- The project has been hardware-tested with a VK172 receiver; compatibility with other NMEA devices is not guaranteed.
- The tool sets the system clock from a point-in-time GPS reading. It is not a continuous disciplining daemon.
- `systemd-timesyncd`, Chrony, and NTP daemons can compete with manual GPS clock updates. Choose one authoritative policy deliberately.
- systemd is the preferred unattended path; cron remains a simpler alternative.
- Unattended operation should use stable device naming, controlled installation ownership, least privilege, and monitored logs.

## Development and testing

Contributors should install the development extra and run the focused local checks:

```bash
python -m pip install -e '.[dev]'
pytest
ruff check .
ruff format --check .
bash -n scripts/gps_sync.sh
python -m build
```

Do not assume global development tools; run these commands from the activated environment. GitHub Actions checks Python 3.10–3.13, Ruff, Bash/ShellCheck, distribution contents, and wheel-only installation. See [Contributor Setup](docs/contributor-setup.md) for the complete local release-validation and installed-wheel smoke sequence. Historical implementation notes are in [Development Notes](docs/development-notes.md).

## License

This project is licensed under the GNU General Public License version 3. See [LICENSE](LICENSE).
