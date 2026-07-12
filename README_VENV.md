# Virtual Environment Setup (gps-time-sync-vk172)

Follow these steps to create and activate the Python virtual environment for the project.

## 1. Create the Environment

From the project root (`/home/rob/gps-time-sync-vk172`):

```bash
python3 -m venv .venv
```

## 2. Activate the Environment

```bash
source .venv/bin/activate
```

You should see `(.venv)` prefixed in your shell prompt. To deactivate later, run `deactivate`.

## 3. Upgrade pip (Optional but recommended)

```bash
pip install --upgrade pip
```

## 4. Install Project Dependencies

```bash
pip install -e .[test]
```

This installs the project in editable mode along with the testing extra (pytest, etc.).

## 5. Verify Installation

```bash
python -V          # Expect Python 3.11.x
pytest             # Test suite should pass
gps-time-sync --help
```

If you need to run commands without activating the environment, you can call binaries directly, e.g.:

```bash
./.venv/bin/gps-time-sync --status --port /dev/ttyACM0
```

## Notes

- Re-create the virtual environment whenever the project path changes (e.g., after renaming the folder) to ensure paths inside `.venv` stay valid.
- When using `sudo`, specify full paths to the venv executables (e.g., `/home/rob/gps-time-sync-vk172/.venv/bin/gps-time-sync`) to avoid “command not found” errors.
- For automation, the helper script `scripts/gps_sync.sh` already sources the virtual environment before running the CLI.
