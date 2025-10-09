# gps-time-syc-vk172

This repository contains a Python 3 project managed via `pyproject.toml` and [Hatchling](https://hatch.pypa.io/latest/). It provides a utility that synchronizes the system clock using a GK172/G-Mouse VK172 USB GPS receiver.

## Features
- Modern `pyproject.toml` configuration.
- Source code under `src/` using the `gps_time_syc_vk172` package name, including a GPS time sync CLI.
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
python -m gps_time_syc_vk172
```

Run tests:

```bash
pytest
```

## Synchronize the System Clock with GPS

Use the bundled `gps-time-sync` CLI to read the current UTC time from the GK172 G-Mouse USB receiver and (optionally) apply it to the system clock.

```bash
sudo gps-time-sync --port /dev/ttyUSB0
```

Key flags:
- `--status` prints the detected GPS UTC time, your local time equivalent, fix quality, and satellite counts without touching the system clock (waits briefly to gather satellite data).
- `--no-set` prints the detected GPS time without adjusting the clock.
- `--baudrate` changes the serial speed (defaults to 9600 baud).
- `--timeout` controls how long to wait for a valid fix.
- `--verbose` enables debug logging useful for troubleshooting.

> **Note:** Adjusting the system clock requires root privileges or the `CAP_SYS_TIME` capability. Make sure your user has access to the GPS serial device (often by joining the `dialout` group).

## Automated Sync Script

The repository includes a helper script that activates the bundled virtual environment and runs the GPS sync command with configurable timing parameters:

```bash
scripts/gps_sync.sh
```

Script defaults (edit `scripts/gps_sync.sh` to adjust):
- Port: `/dev/ttyACM0`
- Timeout: 60 seconds
- Warmup: 2 seconds before parsing sentences

> **Tip:** Run the script as root (or grant the executable `CAP_SYS_TIME`) if you want the system clock updated automatically.
When invoking manually with elevation, call it with an absolute path so `sudo` can find the virtualenv binary, e.g.

```bash
sudo /home/rob/gps-time-syc-vk172/scripts/gps_sync.sh
```

### Cron Example

Schedule the sync every 15 minutes by adding the following to root’s crontab:

```
*/15 * * * * /home/rob/gps-time-syc-vk172/scripts/gps_sync.sh >> /var/log/gps-sync.log 2>&1
```

Make sure the script is executable (`chmod +x scripts/gps_sync.sh`) and that `/var/log/gps-sync.log` is writable by root. Adjust frequency, port, or timeout directly in the script as needed.
