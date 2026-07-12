# Contributor Setup

This guide covers local development setup for `gps-time-sync-vk172`. See the [main README](../README.md) for device discovery, safe operation, privileges, automation, and troubleshooting.

## Supported Python

The project metadata requires Python 3.10 or newer. Use a currently supported Python release available on your Linux/Unix-like development system; do not rely on one hard-coded minor version.

## Create the development environment

From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[test]'
```

`python3` creates the virtual environment. Once it is active, `python`, `pip`, `pytest`, and `gps-time-sync` resolve within `.venv`.

## Validate changes

Run the Python and wrapper tests without GPS hardware or clock-setting privileges:

```bash
pytest
bash -n scripts/gps_sync.sh
python -m gps_time_sync_vk172
gps-time-sync --help
scripts/gps_sync.sh --help
```

The wrapper help path does not require `.venv`, but its normal execution does.

## Build distributions

The build frontend is not currently part of a development extra. Install it explicitly in the development environment when validating artifacts:

```bash
python -m pip install build
python -m build
```

This creates a wheel and source distribution under `dist/`.

## Recreate stale environments

Virtual environments contain absolute paths. If the checkout is moved or renamed, remove and recreate `.venv`, then reinstall the package. Do not use a stale editable installation as evidence that packaging works.

## Project scope and remaining work

Review [Known Issues and Remaining Work](../KNOWN_ISSUES_AND_TODO.md) before starting a release-oriented change. The repository does not currently claim GitHub Actions, configured Ruff, configured ShellCheck, or static type checking.
