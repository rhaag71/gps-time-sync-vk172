# Known Issues and Remaining Work

## Project status notice

This project is functional and has been tested with a VK172 USB GPS receiver, but the repository is still undergoing cleanup and public-release preparation. The items below describe known defects, incomplete changes, reliability concerns, documentation gaps, and optional improvements. Prospective users should review the critical items before installing or deploying the project.

This review began at commit `4076c48`; the P0 packaging repairs were validated in the working tree on 2026-07-12. “Confirmed” means the behavior is directly visible in the repository or was reproduced during review. “Probable—validate” identifies a risk that needs a focused test. “Optional” identifies an improvement rather than a defect. No existing project virtual environment was used as evidence.

TLDR summary;
The P0 package rename and packaging-metadata blockers are resolved in the current working tree. Clean editable installation, tests, wheel and source-distribution builds, and wheel-only installation now succeed. The remaining P1, P2, and P3 items below still need review before a public release.


## Executive summary

The core implementation is substantial: it validates NMEA checksums, parses RMC/GGA/GSA/GSV messages, reports GPS status, avoids setting the clock in `--status` and `--no-set` modes, and has been used with VK172 hardware. The corrected `gps_time_sync_vk172` package now installs and builds cleanly, and the `gps-time-sync` entry point targets it. The canonical GPLv3 and Linux classifiers are accepted by current Hatchling.

The highest-value remaining work is to define status-collection and timeout semantics, harden clock-setting and serial-error behavior, expand deterministic tests, reorganize the user documentation, and provide a safer unattended deployment path.

## Confirmed strengths

- **Confirmed:** The distribution name is `gps-time-sync-vk172`; the project URLs reference the actual GitHub repository; the license metadata and classifier intend GPLv3; `LICENSE` contains GPLv3; and the OS classifier targets Unix/Linux.
- **Confirmed:** The primary README hardware examples use `/dev/ttyACM0`. Its `/home/rob/...` path is explicitly labeled as the author's example and is not itself a defect.
- **Confirmed:** The CLI distinguishes status display, display-only operation, serial errors, acquisition timeout, permission errors, and other clock-setting errors with separate paths.
- **Confirmed:** Parsing accepts alternate talker prefixes structurally by checking sentence types with `endswith()` or the final three characters, although representative `GN` streams are not tested.
- **Confirmed:** The Bash wrapper uses strict shell mode, derives the repository path from its own location, quotes current expansions, and gives distinct errors for a missing virtual environment and executable.
- **Confirmed:** Existing unit tests cover basic valid/invalid RMC parsing, one GGA/GSA/GSV example, a status summary, three clock-setting paths, basic acquisition, and one CLI status path. All 14 tests passed from the clean editable installation during P0 validation.

## Known critical issues

### P0 — incomplete package rename (resolved 2026-07-12)

**Current behavior:** Resolved. Git now tracks `src/gps_time_sync_vk172/`; source, tests, configuration, and active README references use the corrected name. The distribution lookup uses `gps-time-sync-vk172`, and the console entry point targets `gps_time_sync_vk172.gps_time_sync:cli`.

**Why it matters:** The inconsistency previously broke clean packaging workflows even when an older editable installation appeared to work.

**Recommended change:** Completed with a Git-aware directory rename and corrected imports, module references, metadata lookup, tests, and active documentation references. Keep the corrected spelling in future changes.

**Files affected:** The package directory and its `__init__.py`/`__main__.py`, both test modules, `README.md`, `README_CHAT.md`, and `README_VENV.md`. `pyproject.toml` retains the corrected wheel path and entry point.

**How it was verified:** A disposable environment installed `.[test]`; all 14 tests passed; corrected import, module execution, and console help succeeded. Both artifacts built, and the wheel installed and passed the same smoke checks in a second clean environment. Archive inspection found only the corrected package path.

### P0 — invalid GPL classifier (resolved 2026-07-12)

**Current behavior:** Resolved. Metadata uses the accepted `License :: OSI Approved :: GNU General Public License v3 (GPLv3)` classifier while retaining the GPLv3 license metadata and `LICENSE` file. Validation also revealed and corrected the invalid OS classifier to `Operating System :: POSIX :: Linux`.

**Why it matters:** Invalid Trove classifier strings blocked all clean metadata generation, installation, and builds.

**Recommended change:** Completed. Keep the canonical GPLv3 and POSIX/Linux classifier strings and preserve the GPLv3 license.

**Files likely affected:** `pyproject.toml` only.

**How it was verified:** Clean editable installation and `python -m build` succeeded with Hatchling 1.31.0. Wheel metadata reports distribution `gps-time-sync-vk172`, license `GNU General Public License v3 (GPLv3)`, the canonical GPLv3 classifier, and `Operating System :: POSIX :: Linux`.

## Packaging and naming

### P2 — verify all rename surfaces and clean artifacts (resolved with P0)

**Current behavior:** Active physical paths, Python imports/messages, README commands, conversation notes, virtual-environment instructions, and author-specific project paths now use the corrected spelling.

**Why it matters:** A partial textual correction can leave stale entry points, metadata lookups, documentation, cached bytecode, or editable-install links that mask the defect.

**Recommended change:** The rename and clean validation are complete. Continue to exclude disposable/generated artifacts from source-name audits and do not use an old `.venv` as release evidence. Adding a generic path example remains part of the later documentation work.

**Files affected:** Same files as the resolved P0 rename plus regenerated, untracked build artifacts.

**How it was verified:** The search below found no stale active source, test, configuration, script, or README references; occurrences retained in this document are audit/search history rather than active package references.

```bash
grep -RIn --exclude-dir=.git --exclude-dir=.venv -e 'gps_time_syc_vk172' -e 'gps-time-syc-vk172' .
```

Expect no matches, then inspect wheel contents and installed entry-point metadata.

## Code correctness and behavior

### P1 — status collection can stop after only one detail metric (confirmed)

**Current behavior:** `GPSStatus.has_detail_metrics()` uses `any(...)`. In status mode, acquisition can return after a valid RMC timestamp plus the first single metric received from a GGA, GSA, or GSV sentence. Multipart GSV completeness is not tracked.

**Why it matters:** Status output can omit useful information that would have arrived moments later, and its completeness depends on receiver sentence order.

**Recommended change:** Use bounded post-fix collection: capture the first valid RMC timestamp; continue for a short configurable collection window; return early only after a documented useful set has been collected; never exceed the overall timeout; and return partial status cleanly when the window expires. “Complete enough” should be receiver-tolerant—for example, timestamp plus one fix indication and useful satellite/fix detail, or a completed observed GSV group—not a requirement that every receiver emit every possible sentence. Receivers that emit only RMC/GGA must remain supported.

**Files likely affected:** `src/gps_time_sync_vk172/gps_time_sync.py`, CLI documentation, and acquisition/status tests.

**How to verify the eventual fix:** Replay differently ordered RMC/GGA/GSA/multipart-GSV fixtures, receivers omitting sentence types, and a mocked deadline; assert early return only at the documented threshold and partial return at the collection window/overall timeout.

### P1 — misleading fix-mode formatting (confirmed)

**Current behavior:** Known values are formatted as the numeric value plus `D` and then their description. This produces `Fix mode: 3D (3D)` and `Fix mode: 1D (No fix)`; unknown numeric values similarly become a fabricated dimensional label.

**Why it matters:** The output is redundant for 2D/3D and actively misleading for “No fix” and unknown modes.

**Recommended change:** Emit exactly `Fix mode: No fix`, `Fix mode: 2D`, `Fix mode: 3D`, or `Fix mode: Unknown`.

**Files likely affected:** `src/gps_time_sync_vk172/gps_time_sync.py` and status-format tests.

**How to verify the eventual fix:** Parameterize tests for recognized values 1, 2, and 3, `None`, and arbitrary unknown numeric/string-derived values.

### P1 — serial decoding policy is internally inconsistent (confirmed)

**Current behavior:** Serial bytes are decoded with `raw.decode("ascii", errors="ignore")`, inside a `try` that catches `UnicodeDecodeError`. Ignoring errors prevents that exception path from being reached.

**Why it matters:** Corrupt/non-ASCII bytes are silently removed and could transform a damaged sentence before checksum validation, while the code suggests errors are explicitly handled.

**Recommended change:** Choose one policy: strict ASCII decoding with a real exception-and-skip path, or deliberately tolerant decoding with the unreachable handler removed and the behavior documented. Strict decoding is easier to reason about for checksum-protected NMEA.

**Files likely affected:** `src/gps_time_sync_vk172/gps_time_sync.py` and serial-input tests.

**How to verify the eventual fix:** Feed malformed bytes and non-ASCII bytes before, within, and after sentences; assert deterministic rejection or documented tolerant behavior without a crash.

### P1 — timeout includes serial warmup without saying so (confirmed)

**Current behavior:** `deadline = time.monotonic() + timeout` is calculated before opening/warming the serial stream, and `time.sleep(warmup)` occurs afterward. Warmup therefore consumes the advertised acquisition timeout and can exhaust it entirely.

**Why it matters:** Users may receive substantially less fix-acquisition time than requested, especially with large warmup values; documentation currently calls timeout the wait for a valid fix.

**Recommended change:** Deliberately select and document one contract: timeout covers the entire operation including open/warmup, or acquisition timeout begins after warmup. Validate non-negative numeric values and make the overall bound explicit.

**Files likely affected:** `src/gps_time_sync_vk172/gps_time_sync.py`, `scripts/gps_sync.sh`, README/CLI help, and timeout tests.

**How to verify the eventual fix:** Use a mocked monotonic clock and mocked sleep/serial reads—never real sleeps—to assert boundary behavior, including warmup equal to or greater than timeout.

### P1 — clock-setting fallback recognizes too narrow an availability signal (confirmed implementation; additional signals require validation)

**Current behavior:** `set_system_time()` falls back to `date` only for `AttributeError`. `PermissionError` is kept distinct, which is good. Unsupported implementations may instead raise `NotImplementedError` or selected `OSError` values; exact platform behavior needs validation.

**Why it matters:** A supported fallback may never run on some Unix/Python combinations, while an overly broad fallback could hide permission, argument, or system failures. The `date` failure diagnostic is currently retained and should stay clear.

**Recommended change:** Define a deliberately narrow fallback policy for genuinely unavailable clock-setting functionality. Consider `NotImplementedError` and only specifically justified `OSError.errno` values. Never turn permission errors into a fallback attempt.

**Files likely affected:** `src/gps_time_sync_vk172/gps_time_sync.py` and clock-setting tests.

**How to verify the eventual fix:** Test naive datetime rejection, successful `clock_settime`, permission failure, successful `date` fallback, failed `date` fallback with its diagnostic, `NotImplementedError`, and each selected unsupported `OSError` value.

### P1 — serial and CLI failure paths need validation (probable—validate)

**Current behavior:** The CLI catches `serial.SerialException` and `TimeoutError`, but tests do not exercise serial-open failures, read failures, empty reads through a deadline, most CLI exit codes, or all clock-set call-count guarantees.

**Why it matters:** Hardware disconnects and permissions are normal deployment failures; untested behavior may hang, leak unclear diagnostics, or accidentally call the clock setter.

**Recommended change:** Add deterministic mocks for open/read/empty-read cases and cover every CLI return path. Explicitly assert that `--no-set` and `--status` never call the setter and normal mode calls it exactly once.

**Files likely affected:** `tests/test_gps_time_sync.py`, possibly implementation after tests expose defects.

**How to verify the eventual fix:** Run the parameterized failure tests and assert exit codes, diagnostics, deadlines, and setter call counts.

## Tests and validation

### P1 — release-critical coverage is incomplete (confirmed)

**Current behavior:** The two small test modules use the old package imports. Coverage does not currently demonstrate a clean install/build/wheel install, and many parser, acquisition, status, CLI, fallback, and wrapper edge cases are absent. This review could not run the suite from a clean install because packaging failed.

**Why it matters:** The most failure-prone boundaries—packaging, serial input, NMEA edge cases, privileges, timeouts, and installed entry points—can regress without detection.

**Recommended change:** Complete the package rename and add coverage for:

- clean editable installation; wheel and source-distribution builds; wheel-only installation and import;
- timeout before a valid fix; serial-port open/read failures; empty reads;
- malformed ASCII/non-ASCII input; malformed checksum fields; invalid checksums;
- missing RMC date/time; invalid calendar dates/times; fractional seconds; year-boundary behavior;
- alternate talker IDs such as `GN`;
- realistic RMC, GGA, GSA, and multipart GSV streams;
- partial status at the collection-window or overall-timeout boundary;
- every CLI exit-code path and exact clock-setter call counts for normal, `--no-set`, and `--status` modes;
- every recognized/unknown fix mode; naive datetime rejection; failed `date` fallback;
- wrapper behavior when `.venv` or `gps-time-sync` is missing, plus option/override behavior once added.

Use captured, sanitized NMEA fixtures so realistic receiver streams can be replayed deterministically.

**Files likely affected:** `tests/`, new sanitized fixture files, CI configuration, and later shell-test files.

**How to verify the eventual fix:** Run the suite in a newly created environment, then install only the produced wheel in another environment and run import/module/CLI smoke tests. Ensure tests do not depend on physical GPS hardware, root, network access, or real sleeps.

## Documentation

### P2 — the main README is scaffold-first and operational guidance is fragmented (confirmed)

**Current behavior:** The opening emphasizes `pyproject.toml`, Hatchling, and layout before clearly presenting the utility's practical purpose. The feature list and `python -m` example use the misspelled package. The cron example is duplicated. Installation, status-only use, display-only use, actual clock synchronization, automation, and troubleshooting are not cleanly separated. Device discovery is not explained. The default CLI port (`/dev/ttyUSB0`) also differs from README/script examples (`/dev/ttyACM0`) without explanation.

**Why it matters:** A prospective user cannot quickly determine what the tool does, which device to select, or which command is safe versus privileged.

**Recommended change:** Lead with purpose and tested hardware, then organize installation, device discovery, status, no-set display, clock-setting, automation, and troubleshooting separately. Document `dmesg --follow` and `ls -l /dev/serial/by-id/`; recommend a stable `/dev/serial/by-id/...` path for unattended use instead of relying only on `/dev/ttyACM0`. Explain that `--status` gathers detail and never sets time, `--no-set` reports the acquired time without setting it, and normal mode sets the clock after acquisition. Explain that `dialout` permits serial access but does not grant clock-setting permission. Discuss root versus carefully scoped `CAP_SYS_TIME`, and possible Chrony, NTP, or `systemd-timesyncd` interaction/conflict. Keep the labeled `/home/rob` example if desired, correct its project spelling, and add a generic `/path/to/gps-time-sync-vk172/...` example.

**Files likely affected:** `README.md` (later work only).

**How to verify the eventual fix:** Follow the README from a clean clone as an unprivileged user, confirm safe status/no-set flows are obvious, device discovery works, privilege boundaries are accurate, and the cron example appears once.

### P2 — supporting READMEs need a clear disposition (confirmed)

**Current behavior:** `README_CHAT.md` reads as conversation-derived development history, retains old names and author paths, claims comprehensive test coverage without current clean-install evidence, and ends with “Feel free to update this file.” `README_VENV.md` duplicates basic setup from the main README, retains old project paths, and expects a specific Python 3.11 version despite `requires-python = ">=3.10"`.

**Why it matters:** Multiple overlapping setup narratives drift and make development history look like current user documentation.

**Recommended change:** Move useful history from `README_CHAT.md` to a clearly named file such as `docs/development-notes.md`, or retain it explicitly as development history; remove conversational filler and unsupported/current claims. Merge `README_VENV.md` into the main README or rename it as a focused contributor setup guide under `docs/`. Correct every old package and directory spelling in retained content.

**Files likely affected:** `README_CHAT.md`, `README_VENV.md`, `README.md`, and a future `docs/` directory.

**How to verify the eventual fix:** Search for old names and filler, follow every setup command from a clean clone, and ensure each document has a distinct audience and purpose.

## Automation and deployment

### P1 — wrapper configuration is hardcoded (confirmed) and extensibility needs hardening (optional aspects)

**Current behavior:** `scripts/gps_sync.sh` hardcodes `/dev/ttyACM0`, timeout `60`, and warmup `2`. Current variable expansions and executable arguments are quoted, but users must edit the tracked script to change settings; it cannot accept a stable by-id path or safely pass extra CLI arguments.

**Why it matters:** Local edits complicate upgrades, `/dev/ttyACM0` can change across boots, and unattended configuration cannot be managed externally.

**Recommended change:** Preserve current defaults while allowing command-line options and/or documented environment overrides. If parsing is added, provide useful `--help`; support `/dev/serial/by-id/...`; validate numeric baud-rate, timeout, and warmup; preserve proper quoting; and safely pass explicitly supported additional CLI arguments. Run ShellCheck and add automated shell tests or documented manual cases.

**Files likely affected:** `scripts/gps_sync.sh`, `README.md`, and shell tests/CI.

**How to verify the eventual fix:** Exercise defaults, every override, spaces/metacharacters in paths/arguments, invalid/negative numerics, `--help`, missing `.venv`, missing executable, and ShellCheck.

### P1 — unattended deployment guidance is not release-ready (confirmed documentation gap)

**Current behavior:** The README recommends a root cron job executing a mutable user checkout; no systemd unit/timer design is provided. Logging, restart/failure behavior, ordering, and time-service interaction are largely unspecified.

**Why it matters:** Broad root execution from a development tree and unstable device names increase operational and security risk; competing time services can immediately counteract GPS adjustments.

**Recommended change:** Later provide a systemd service and timer as the preferred Linux deployment method, retaining cron as a simpler alternative. Cover a stable serial path, dedicated installation directory or managed virtual environment, avoiding root execution from a casually mutable checkout, careful use of `CAP_SYS_TIME` where appropriate instead of broad root, minimal serial permissions, logging, restart/failure policy, service ordering, and interaction with `systemd-timesyncd`, Chrony, or another NTP service. Do not create service files until that design is reviewed.

**Files likely affected:** Future service/timer examples and deployment documentation.

**How to verify the eventual fix:** Test install/start/stop/restart, boot ordering, missing/disconnected GPS, permission boundaries, logs and failure status, timer execution, and coexistence or deliberate exclusion with the selected network time service.

## Development tooling and CI

### P2 — no release-quality CI/tooling configuration is present (confirmed)

**Current behavior:** The tracked repository contains no GitHub Actions workflow, Ruff configuration, type-check configuration, ShellCheck workflow, or artifact-install smoke test. The `test` extra includes only pytest. `python -m build` is a requested release command but the `build` frontend is not declared in a development extra; in the disposable clean environment it failed with `No module named build`.

**Why it matters:** Supported Python versions, style, shell safety, buildability, wheel contents, and installed entry points are not continuously checked. Contributors cannot infer all release dependencies from project metadata.

**Recommended change:** Add a focused GitHub Actions workflow that tests supported Python versions; uses Ruff for linting/formatting; optionally adds static type checking; runs ShellCheck; builds wheel and sdist; installs the generated wheel into a clean environment; and smoke-tests import, `python -m gps_time_sync_vk172`, and `gps-time-sync --help`. Declare `build` in a documented development/release extra or contributor requirements rather than silently installing unrelated tooling.

**Files likely affected:** `pyproject.toml`, future `.github/workflows/` files, and contributor documentation.

**How to verify the eventual fix:** Run the documented local commands and require the CI matrix, lint/format, ShellCheck, build, artifact-install, and installed-command jobs to pass on a clean checkout.

### P3 — optional static typing and broader quality checks (optional)

**Current behavior:** Type hints exist, but no static checker is configured.

**Why it matters:** Static checking could catch interface drift, but it should not delay the P0 packaging repair or essential behavioral tests.

**Recommended change:** After the release path is stable, evaluate a lightweight type-checking configuration and incrementally enforce it.

**Files likely affected:** `pyproject.toml`, CI, and annotations exposed by the checker.

**How to verify the eventual fix:** Run the documented checker locally and in CI with a clearly defined baseline.

## Prioritized implementation plan

1. **P0 — complete:** The Git-aware package rename, accepted GPLv3/Linux classifiers, clean editable installation, imports, tests, module/console entry points, wheel/sdist builds, and wheel-only installation were restored and validated.
2. **P1:** Define and test status-collection completeness and timeout/warmup semantics.
3. **P1:** Correct fix-mode output, choose a consistent serial-decoding policy, and narrowly harden `set_system_time()` fallback behavior.
4. **P1:** Add realistic deterministic NMEA, serial-failure, timeout, CLI exit-code/call-count, and shell-wrapper tests.
5. **P2:** Rewrite and consolidate documentation around actual user workflows, device discovery, privilege boundaries, stable device paths, and time-service interaction.
6. **P1/P2:** Make wrapper configuration external and design a reviewed systemd service/timer deployment path.
7. **P2/P3:** Add focused CI, Ruff, ShellCheck, build/artifact smoke checks, and optionally static type checking.

## Release-readiness checklist

- [x] No old package/project spelling remains outside intentionally quoted audit/search history.
- [x] The license remains GPLv3 and Hatchling accepts all metadata/classifiers.
- [x] A new virtual environment can install `.[test]` without using prior artifacts.
- [x] All 14 tests pass from the clean editable install.
- [x] The corrected module runs and the installed console script exposes help.
- [x] `python -m build` produces both a wheel and source distribution; the disposable installation of `build` is recorded below.
- [x] The generated wheel installs and imports in a second clean environment.
- [x] Wheel/sdist contents contain the intended package and no misspelled package path.
- [ ] Status collection, timeout, malformed input, serial failures, CLI paths, clock setting, and shell-wrapper failures are covered.
- [ ] README instructions work from a clean clone and distinguish safe display modes from clock-setting mode.
- [ ] CI checks supported Python versions, Ruff, ShellCheck, artifacts, and installed-package smoke tests.
- [ ] Unattended deployment documents stable device naming, least privilege, logs, failure behavior, ordering, and competing time services.

Suggested post-fix validation sequence:

```bash
grep -RIn --exclude-dir=.git --exclude-dir=.venv -e 'gps_time_syc_vk172' -e 'gps-time-syc-vk172' .
rm -rf .venv
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[test]'
pytest
python -m gps_time_sync_vk172
gps-time-sync --help
python -m build
```

After `python -m build`, create another clean environment, install the generated wheel (not the source tree), and repeat the import/module/console-script smoke tests. If `python -m build` is not available, install the project’s documented development/release extra after it declares the build frontend; do not silently depend on undeclared global tooling.

### Audit command log (2026-07-12)

Every shell invocation used for this review is recorded below. Several invocations contained multiple read-only commands separated by semicolons or `&&`; results are summarized in execution order.

1. `pwd && git status --short && rg --files -g '!KNOWN_ISSUES_AND_TODO.md' && rg -n --hidden -g '!.git/**' -g '!.venv/**' -e 'gps_time_syc_vk172|gps-time-syc-vk172|gps_time_sync_vk172|gps-time-sync-vk172' .`
   - Result: working directory was `/home/rob/Projects/gps-time-syc-vk172`; `git status --short` printed nothing (clean before this document); 12 tracked project files were listed; the spelling search confirmed the mismatches described above.
2. `sed -n ...` over `pyproject.toml`, all three READMEs, `scripts/gps_sync.sh`, all source modules, and both test modules.
   - Result: files were read successfully; the combined output limit ended partway through the long source/test display, so subsequent ranged reads completed the inspection.
3. `wc -l src/gps_time_syc_vk172/gps_time_sync.py tests/test_gps_time_sync.py; sed -n ...; git log -1 --oneline; git ls-files`
   - Result: source was 577 lines and the main test file 212 lines; remaining implementation/tests were inspected; HEAD was `4076c48`; Git confirmed the physical old-name package directory and the tracked file set.
4. `sed -n ...` for the remaining source/test ranges, followed by `find . -maxdepth 3 -type f -not -path './.git/*' -not -path './.venv/*' -print | sort`
   - Result: inspection completed. `find` also showed untracked pytest cache/bytecode artifacts, but no additional source/configuration files relevant to the rename.
5. `rm -rf /tmp/gps-time-sync-audit-venv /tmp/gps-time-sync-wheel-venv /tmp/gps-time-sync-dist && python3 -m venv /tmp/gps-time-sync-audit-venv && /tmp/gps-time-sync-audit-venv/bin/python -m pip install -e '.[test]'`
   - Result: disposable environment creation succeeded. The first install attempt failed because the sandbox could not resolve/download Hatchling; no repository `.venv` was removed or used.
6. `/tmp/gps-time-sync-audit-venv/bin/python -m pip install -e '.[test]'` (repeated with approved network access)
   - Result: dependencies became reachable, but editable metadata generation failed with exit code 1 and exact root error `ValueError: Unknown classifier in field project.classifiers: License :: GNU General Public License v3 (GPLv3)`. Installation did not reach the later package-directory validation.
7. `/tmp/gps-time-sync-audit-venv/bin/python -m build; /tmp/gps-time-sync-audit-venv/bin/python -m gps_time_sync_vk172; /tmp/gps-time-sync-audit-venv/bin/python -m gps_time_syc_vk172; /tmp/gps-time-sync-audit-venv/bin/gps-time-sync --help; /tmp/gps-time-sync-audit-venv/bin/pytest`
   - Result: respectively: `No module named build`; no corrected-name module; no old-name module; no console-script file; no pytest file. These are consequences of the failed clean install, not independent test-suite failures. Tests were therefore **not run**, and this document does not claim they pass.
8. `git status --short && git diff -- KNOWN_ISSUES_AND_TODO.md && rg -n '^## (...)$' KNOWN_ISSUES_AND_TODO.md`
   - Result: only the requested new file was untracked; `git diff` had no output because ordinary diff does not display untracked content; all 12 required section headings were present.

The original audit established the P0 baseline above. The P0 repair was completed and validated in a later working-tree pass recorded next.

### P0 repair validation log (2026-07-12)

1. `git mv src/gps_time_syc_vk172 src/gps_time_sync_vk172`
   - Result: the sandboxed attempt could not write `.git/index.lock`; the approved retry succeeded and Git records the package move as renames.
2. Active-reference search: `grep -RIn --exclude-dir=.git --exclude-dir=.venv --exclude=KNOWN_ISSUES_AND_TODO.md -e 'gps_time_syc_vk172' -e 'gps-time-syc-vk172' .`
   - Result: no active source, test, configuration, script, or README matches after the edits.
3. `rm -rf /tmp/gps-time-sync-audit-venv && python3 -m venv /tmp/gps-time-sync-audit-venv`
   - Result: a fresh disposable Python 3.13 environment was created outside the repository.
4. `/tmp/gps-time-sync-audit-venv/bin/python -m pip install --upgrade pip && /tmp/gps-time-sync-audit-venv/bin/python -m pip install -e '.[test]'`
   - Result: pip upgraded to 26.1.2. The first editable-install attempt showed that `Operating System :: Unix/Linux` was also invalid after the GPL classifier was fixed. It was narrowly corrected to `Operating System :: POSIX :: Linux`; the repeated editable install then succeeded with `gps-time-sync-vk172==0.1.0`, pyserial 3.5, and pytest 9.1.1.
5. `/tmp/gps-time-sync-audit-venv/bin/pytest`
   - Result: **14 passed in 0.06s** on Python 3.13.5.
6. `/tmp/gps-time-sync-audit-venv/bin/python -c 'import gps_time_sync_vk172; print(gps_time_sync_vk172.__version__)'`
   - Result: import succeeded and printed `0.1.0`.
7. `/tmp/gps-time-sync-audit-venv/bin/python -m gps_time_sync_vk172`
   - Result: succeeded and printed the corrected package-loaded message.
8. `/tmp/gps-time-sync-audit-venv/bin/gps-time-sync --help`
   - Result: exited successfully and displayed the complete CLI usage/options.
9. `/tmp/gps-time-sync-audit-venv/bin/python -m pip install build`
   - Result: explicitly installed build 1.5.1 and pyproject-hooks 1.2.0 in the disposable audit environment; no project dependency was added.
10. `rm -rf dist build && /tmp/gps-time-sync-audit-venv/bin/python -m build && ls -lh dist`
    - Result: with Hatchling 1.31.0 in isolated build environments, successfully produced `gps_time_sync_vk172-0.1.0.tar.gz` and `gps_time_sync_vk172-0.1.0-py3-none-any.whl` (approximately 31 KiB and 21 KiB in that build).
11. `rm -rf /tmp/gps-time-sync-wheel-venv && python3 -m venv /tmp/gps-time-sync-wheel-venv`
    - Result: a second clean Python 3.13 environment was created outside the repository.
12. `/tmp/gps-time-sync-wheel-venv/bin/python -m pip install --upgrade pip && /tmp/gps-time-sync-wheel-venv/bin/python -m pip install dist/*.whl`
    - Result: pip upgraded to 26.1.2; the generated wheel and only its runtime dependency, pyserial 3.5, installed successfully.
13. Wheel-only smoke commands: corrected-package import/version, `python -m gps_time_sync_vk172`, and `gps-time-sync --help` using `/tmp/gps-time-sync-wheel-venv/bin/`.
    - Result: all succeeded; version was `0.1.0`, the corrected package-loaded message printed, and CLI help displayed.
14. `unzip -l` on the wheel, `tar -tzf` on the sdist, `unzip -p` for wheel `entry_points.txt` and `METADATA`, and an installed `importlib.metadata` inspection.
    - Result: both archives contained `gps_time_sync_vk172` and no misspelled package path. The entry point is `gps-time-sync = gps_time_sync_vk172.gps_time_sync:cli`. Metadata reports `Name: gps-time-sync-vk172`, GPLv3 license text/file and canonical classifier, and `Operating System :: POSIX :: Linux`.
15. After updating this document, the artifacts were rebuilt with `rm -rf dist build && /tmp/gps-time-sync-audit-venv/bin/python -m build`; the final wheel was reinstalled with `--force-reinstall --no-deps` in the second environment, followed by the version import, module, console-help, `unzip -l`, and `tar -tzf` checks.
    - Result: both final artifacts rebuilt successfully; the final wheel reinstalled as version `0.1.0`; corrected import/module/console smoke checks succeeded; and both final archive listings contain only the corrected package path.

The ordered remaining implementation sequence is: address collection/timeout/clock/decoding behavior and tests; then finish documentation, deployment, and CI work.
