# gps-time-sync-vk172

This repository contains a Python 3 project managed via `pyproject.toml` and [Hatchling](https://hatch.pypa.io/latest/). It provides a utility that synchronizes the system clock using a GK172/G-Mouse VK172 USB GPS receiver.

## Features
- Modern `pyproject.toml` configuration.
- Source code under `src/` using the `gps_time_sync_vk172` package name, including a GPS time sync CLI.
- Pytest-based test structure under `tests/`.

## Getting Started
Create a virtual environment and install the project in editable mode:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e .[test]
```

Run the sample package entry point:

```bash
python -m gps_time_sync_vk172
```

Run tests:

```bash
pytest
```

## Synchronize the System Clock with GPS

Use the bundled `gps-time-sync` CLI to read the current UTC time from the GK172 G-Mouse USB receiver and (optionally) apply it to the system clock.

```bash
sudo gps-time-sync --port /dev/ttyACM0
```

Key flags:
- `--status` prints the detected GPS UTC time, your local time equivalent, fix quality, and satellite counts without touching the system clock (waits briefly to gather satellite data).
- `--no-set` prints the detected GPS time without adjusting the clock.
- `--baudrate` changes the serial speed (defaults to 9600 baud).
- `--timeout` controls how long to wait for a valid fix.
- `--verbose` enables debug logging useful for troubleshooting.

> **Note:** Adjusting the system clock requires root privileges or the `CAP_SYS_TIME` capability. Make sure your user has access to the GPS serial device (often by joining the `dialout` group).

## Automated Sync Script

The repository includes a helper script that runs the repository virtual environment's `gps-time-sync` executable directly:

```bash
scripts/gps_sync.sh
```

Built-in defaults:

- Port: `/dev/ttyACM0`
- Baud rate: 9600
- Timeout: 60 seconds
- Warmup: 2 seconds before parsing sentences
- Status collection window: 2 seconds

Override settings with command-line options:

```bash
scripts/gps_sync.sh --port /dev/ttyACM1 --baudrate 9600 --timeout 90 --warmup 1 --status-window 3 --status
```

For unattended use, prefer a stable device path:

```bash
scripts/gps_sync.sh --port /dev/serial/by-id/usb-u-blox_GPS-if00 --no-set
```

Environment variables provide another configuration layer:

```bash
GPS_PORT=/dev/ttyACM1 GPS_TIMEOUT=90 GPS_WARMUP=1 scripts/gps_sync.sh --status
```

Supported variables are `GPS_PORT`, `GPS_BAUDRATE`, `GPS_TIMEOUT`, `GPS_WARMUP`, and `GPS_STATUS_WINDOW`. Precedence is command-line options, then environment variables, then built-in defaults. See the complete usage without requiring a virtual environment:

```bash
scripts/gps_sync.sh --help
```

> **Tip:** Run the script as root (or grant the executable `CAP_SYS_TIME`) if you want the system clock updated automatically.
When invoking manually with elevation, call it with an absolute path so `sudo` can find the virtualenv binary, e.g.

Using my username `rob` as an example:

```bash
sudo /home/rob/gps-time-sync-vk172/scripts/gps_sync.sh
```

### Cron Example
Using the above example, you can schedule the script to run every 15 minutes via cron. Edit root’s crontab with `sudo crontab -e` and add the following line:

```
*/15 * * * * /home/rob/gps-time-sync-vk172/scripts/gps_sync.sh >> /var/log/gps-sync.log 2>&1
```
Schedule the sync every 15 minutes by adding the following to root’s crontab:

```
*/15 * * * * /home/rob/gps-time-sync-vk172/scripts/gps_sync.sh >> /var/log/gps-sync.log 2>&1
```

Make sure the script is executable (`chmod +x scripts/gps_sync.sh`) and that `/var/log/gps-sync.log` is writable by root. Adjust frequency, port, or timeout directly in the script as needed.
