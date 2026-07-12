# Development Notes

This document preserves a concise history of the repository's implementation. It is not an installation or operations guide; use the [main README](../README.md) for current user instructions and [Contributor Setup](contributor-setup.md) for development-environment details.

## Project evolution

### Initial scaffold

The project began as a Python package using `pyproject.toml`, Hatchling, a `src/` layout, and pytest. It later adopted the distribution name `gps-time-sync-vk172` and the import package `gps_time_sync_vk172`.

### GPS time acquisition

The utility grew from a package scaffold into a serial NMEA reader for VK172/GK172 receivers. It validates checksums, obtains UTC timestamps from RMC sentences, collects status from GGA/GSA/GSV messages, and exposes the `gps-time-sync` command.

### Safe reporting and clock updates

The CLI supports status-only and no-set modes that never alter the system clock. Normal mode can set the clock through Python's clock API, with a narrow fallback to the system `date` command when the primary API is genuinely unavailable.

### Packaging cleanup

The package and distribution naming were standardized, metadata classifiers were corrected, and clean editable installation, wheel/source-distribution builds, and wheel-only installation were validated in disposable environments.

### Behavioral hardening

Status collection became bounded after the first valid timestamp, timeout timing was defined to begin after serial warmup, serial decoding became strict ASCII, and time-setting fallback behavior was narrowed. Deterministic tests cover parsing, serial failures, timing, status ordering, CLI exit paths, and clock-setting behavior.

### Shell wrapper

`scripts/gps_sync.sh` now runs the repository-local virtual-environment executable directly. It supports validated command-line and environment configuration, preserves argument boundaries, and has subprocess tests based on a fake executable rather than GPS hardware or clock changes.

## Current sources of truth

- [README](../README.md): installation, use, troubleshooting, and current cron guidance.
- [Contributor Setup](contributor-setup.md): local development environment and validation commands.
- [Known Issues and Remaining Work](../KNOWN_ISSUES_AND_TODO.md): resolved audit findings and remaining release work.
- `gps-time-sync --help`: current application CLI options and defaults.
- `scripts/gps_sync.sh --help`: current wrapper options, environment variables, and defaults.

These notes intentionally omit duplicate operational command sequences so historical context cannot drift into a second user guide.
