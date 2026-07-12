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
python -m pip install -e '.[dev]'
```

`python3` creates the virtual environment. Once it is active, `python`, `pip`, `pytest`, `ruff`, and `gps-time-sync` resolve within `.venv`. The `dev` extra contains pytest, Ruff, and the Python build frontend. The smaller `test` extra remains available when only pytest is needed.

## Validate changes

Run the Python and wrapper tests without GPS hardware or clock-setting privileges:

```bash
pytest
ruff check .
ruff format --check .
bash -n scripts/gps_sync.sh
python -m gps_time_sync_vk172
gps-time-sync --help
scripts/gps_sync.sh --help
```

Apply Ruff formatting when needed, then rerun lint and tests:

```bash
ruff format .
ruff check .
pytest
```

If ShellCheck is installed on the host, also run:

```bash
shellcheck scripts/gps_sync.sh
```

ShellCheck is a system executable rather than a Python dependency. The wrapper help path does not require `.venv`, but its normal execution does.

## Build distributions

The build frontend is included in the `dev` extra. Create both distributions from a clean artifact directory and inspect their contents:

```bash
rm -rf dist build
python -m build
ls -l dist/
python -m zipfile -l dist/*.whl
tar -tf dist/*.tar.gz
```

Smoke-test the generated wheel independently of the editable source tree:

```bash
rm -rf /tmp/gps-time-sync-wheel-check
python3 -m venv /tmp/gps-time-sync-wheel-check
/tmp/gps-time-sync-wheel-check/bin/python -m pip install --upgrade pip
/tmp/gps-time-sync-wheel-check/bin/python -m pip install dist/*.whl
/tmp/gps-time-sync-wheel-check/bin/python -c 'import gps_time_sync_vk172; print(gps_time_sync_vk172.__version__)'
/tmp/gps-time-sync-wheel-check/bin/python -m gps_time_sync_vk172
/tmp/gps-time-sync-wheel-check/bin/gps-time-sync --help
```

This second environment installs only the built wheel and its runtime dependency; it does not install the checkout in editable mode.

## Continuous integration

`.github/workflows/ci.yml` runs on pushes to `main`, pull requests targeting `main`, and manual dispatch. It:

- runs pytest plus Ruff lint/format checks on Python 3.10, 3.11, 3.12, and 3.13;
- validates the wrapper with `bash -n` and ShellCheck;
- builds and inspects the wheel and source distribution; and
- passes the generated artifacts to a separate clean wheel-install smoke job.

CI uses read-only repository permissions and does not publish packages or releases. Local checks remain useful before pushing; the hosted workflow itself can only be proven after the workflow is pushed to GitHub.

## Recreate stale environments

Virtual environments contain absolute paths. If the checkout is moved or renamed, remove and recreate `.venv`, then reinstall the package. Do not use a stale editable installation as evidence that packaging works.

## Project scope and remaining work

Review [Known Issues and Remaining Work](../KNOWN_ISSUES_AND_TODO.md) before starting a release-oriented change. Static type checking remains optional and is not configured.
