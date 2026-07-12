# Known Issues and Remaining Work

## Project status notice

This project is functional and has been tested with a VK172 USB GPS receiver, but the repository is still undergoing cleanup and public-release preparation. The items below describe known defects, incomplete changes, reliability concerns, documentation gaps, and optional improvements. Prospective users should review the critical items before installing or deploying the project.

This review began at commit `4076c48`; the P0 packaging repairs were validated in the working tree on 2026-07-12. “Confirmed” means the behavior is directly visible in the repository or was reproduced during review. “Probable—validate” identifies a risk that needs a focused test. “Optional” identifies an improvement rather than a defect. No existing project virtual environment was used as evidence.

TLDR summary;
The P0 package rename and packaging-metadata blockers are resolved in the current working tree. Clean editable installation, tests, wheel and source-distribution builds, and wheel-only installation now succeed. The remaining P1, P2, and P3 items below still need review before a public release.


## Executive summary

The core implementation is substantial: it validates NMEA checksums, parses RMC/GGA/GSA/GSV messages, reports GPS status, avoids setting the clock in `--status` and `--no-set` modes, and has been used with VK172 hardware. The corrected `gps_time_sync_vk172` package now installs and builds cleanly, and the `gps-time-sync` entry point targets it. The canonical GPLv3 and Linux classifiers are accepted by current Hatchling.

The packaging, application behavior, shell wrapper, and user-facing documentation have now been consolidated and validated. Remaining work centers on hardened unattended deployment and release tooling.

## Confirmed strengths

- **Confirmed:** The distribution name is `gps-time-sync-vk172`; the project URLs reference the actual GitHub repository; the license metadata and classifier intend GPLv3; `LICENSE` contains GPLv3; and the OS classifier targets Unix/Linux.
- **Confirmed:** The primary README hardware examples use `/dev/ttyACM0`. Its `/home/rob/...` path is explicitly labeled as the author's example and is not itself a defect.
- **Confirmed:** The CLI distinguishes status display, display-only operation, serial errors, acquisition timeout, permission errors, and other clock-setting errors with separate paths.
- **Confirmed:** Parsing accepts alternate talker prefixes structurally, and representative `GN` RMC/GGA/GSA/GSV inputs are tested.
- **Confirmed:** The Bash wrapper uses strict shell mode, derives the repository path from its own location, quotes current expansions, and gives distinct errors for a missing virtual environment and executable.
- **Confirmed:** The current 102-test suite covers packaging-era smoke behavior, NMEA parsing, status collection, timing, serial failures, clock-setting paths, CLI behavior, and the shell wrapper.

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

### P1 — status collection can stop after only one detail metric (resolved 2026-07-12)

**Current behavior:** Detailed status mode captures the first valid RMC timestamp and then collects for at most `--status-window` seconds (default 2.0), capped by the overall acquisition deadline. It returns early when it has useful fix/satellite detail plus GGA and either GSA or every numbered part of an observed GSV group for a talker. Otherwise it returns available partial status when the short window or overall timeout expires. Non-status acquisition still returns immediately on the first valid timestamp.

**Why it matters:** Status output can omit useful information that would have arrived moments later, and its completeness depends on receiver sentence order.

**Recommended change:** Completed. Preserve the receiver-tolerant completeness rule and bounded partial-return behavior.

**Files likely affected:** `src/gps_time_sync_vk172/gps_time_sync.py`, CLI documentation, and acquisition/status tests.

**How it was verified:** Deterministic tests cover RMC/GGA/GSA in multiple orders, complete and incomplete multipart GSV, RMC+GGA partial return, and collection-window/overall-timeout bounds.

### P1 — misleading fix-mode formatting (resolved 2026-07-12)

**Current behavior:** Output is exactly `Fix mode: No fix`, `Fix mode: 2D`, `Fix mode: 3D`, or `Fix mode: Unknown`.

**Why it matters:** The output is redundant for 2D/3D and actively misleading for “No fix” and unknown modes.

**Recommended change:** Completed.

**Files likely affected:** `src/gps_time_sync_vk172/gps_time_sync.py` and status-format tests.

**How it was verified:** Parameterized tests cover `None`, 1, 2, 3, and unknown numeric value 9.

### P1 — serial decoding policy is internally inconsistent (resolved 2026-07-12)

**Current behavior:** Serial input uses strict ASCII decoding. `UnicodeDecodeError` is logged at debug level and the entire malformed read is skipped, so removing a bad byte cannot turn damaged input into a different valid-looking sentence.

**Why it matters:** Corrupt/non-ASCII bytes are silently removed and could transform a damaged sentence before checksum validation, while the code suggests errors are explicitly handled.

**Recommended change:** Completed with the strict policy.

**Files likely affected:** `src/gps_time_sync_vk172/gps_time_sync.py` and serial-input tests.

**How it was verified:** Tests inject a non-ASCII byte before, inside, and after otherwise valid sentence data, confirm the malformed read is skipped, and then acquire from the next valid ASCII sentence.

### P1 — timeout includes serial warmup without saying so (resolved 2026-07-12)

**Current behavior:** Serial warmup completes first; the monotonic acquisition deadline is then set. `timeout` therefore means GPS data-acquisition time after warmup. Timeout, warmup, and status-window values must be non-negative. Each serial read timeout is capped to the remaining active deadline, and the post-fix window can never extend the overall acquisition deadline.

**Why it matters:** Users may receive substantially less fix-acquisition time than requested, especially with large warmup values; documentation currently calls timeout the wait for a valid fix.

**Recommended change:** Completed using the post-warmup acquisition-time contract.

**Files likely affected:** `src/gps_time_sync_vk172/gps_time_sync.py`, `scripts/gps_sync.sh`, README/CLI help, and timeout tests.

**How it was verified:** Mocked monotonic time, sleep, and serial reads cover zero/positive warmup, zero/negative timeout, negative warmup/window, empty reads, missing fix, partial status, and the authoritative overall deadline without real sleeping.

### P1 — clock-setting fallback recognizes too narrow an availability signal (resolved 2026-07-12)

**Current behavior:** `set_system_time()` falls back to `date` only for `AttributeError`, `NotImplementedError`, or `OSError` with `ENOSYS`, `ENOTSUP`, or `EOPNOTSUPP`. Other `OSError` values propagate. `PermissionError` is translated to the existing privilege diagnostic and never falls back. Naive datetimes are rejected. Nonzero `date` results and failure to execute `date` retain useful diagnostics.

**Why it matters:** A supported fallback may never run on some Unix/Python combinations, while an overly broad fallback could hide permission, argument, or system failures. The `date` failure diagnostic is currently retained and should stay clear.

**Recommended change:** Completed with the narrow unsupported-function policy above.

**Files likely affected:** `src/gps_time_sync_vk172/gps_time_sync.py` and clock-setting tests.

**How it was verified:** Tests cover successful `clock_settime`, naive rejection, permission behavior, AttributeError/NotImplementedError/supported-errno fallbacks, unsupported `EIO` propagation, successful `date`, nonzero `date`, and missing `date` diagnostics.

### P1 — serial and CLI failure paths need validation (resolved for application paths 2026-07-12)

**Current behavior:** Deterministic tests now exercise serial-open/read failures, empty reads through a deadline, successful CLI operation, exit codes 2–5, and exact clock-set call counts. `--status` and `--no-set` never call the setter; normal mode calls it exactly once.

**Why it matters:** Hardware disconnects and permissions are normal deployment failures; untested behavior may hang, leak unclear diagnostics, or accidentally call the clock setter.

**Recommended change:** Completed for the Python application. Shell-wrapper failure tests remain open in the separate automation/test items.

**Files likely affected:** `tests/test_gps_time_sync.py`, possibly implementation after tests expose defects.

**How it was verified:** The expanded suite asserts exit codes, deadlines, error propagation, and setter call counts without hardware or privilege changes.

## Tests and validation

### P1 — release-critical coverage is incomplete (partially resolved)

**Current behavior:** Packaging validation demonstrates clean editable and wheel-only installs and both artifact builds. The suite covers the requested parser, acquisition, status, CLI, decoding, timeout, clock-fallback, and shell-wrapper cases. Later release/deployment concerns and captured hardware fixtures remain open.

**Why it matters:** The most failure-prone boundaries—packaging, serial input, NMEA edge cases, privileges, timeouts, and installed entry points—can regress without detection.

**Recommended change:** Completed in this stage for:

- clean editable installation; wheel and source-distribution builds; wheel-only installation and import;
- timeout before a valid fix; serial-port open/read failures; empty reads;
- malformed ASCII/non-ASCII input; malformed checksum fields; invalid checksums;
- missing RMC date/time; invalid calendar dates/times; fractional seconds; year-boundary behavior;
- alternate talker IDs such as `GN`;
- realistic RMC, GGA, GSA, and multipart GSV streams;
- partial status at the collection-window or overall-timeout boundary;
- every CLI exit-code path and exact clock-setter call counts for normal, `--no-set`, and `--status` modes;
- every recognized/unknown fix mode; naive datetime rejection; failed `date` fallback;
- Python application behavior listed above.

Captured, sanitized hardware NMEA fixtures remain a useful future complement to the deterministic in-test fixtures.

**Files likely affected:** `tests/`, new sanitized fixture files, CI configuration, and later shell-test files.

**How to verify the remaining work:** Retain the clean environment/artifact checks from P0 and the 102 deterministic tests now present; add later release checks without physical hardware, root, network access, or real sleeps.

## Documentation

### P2 — the main README is scaffold-first and operational guidance is fragmented (resolved 2026-07-12)

**Current behavior:** `README.md` is the authoritative, user-first guide. It leads with the practical purpose and tested hardware; separates installation, discovery, safe modes, clock setting, command reference, wrapper configuration, cron, troubleshooting, limitations, and development; explains the CLI/wrapper default-port difference; and contains one generic cron example.

**Why it matters:** A prospective user cannot quickly determine what the tool does, which device to select, or which command is safe versus privileged.

**Recommended change:** Completed. Preserve the current user-first flow and verify future option/default changes against generated help.

**Files affected:** `README.md`.

**How it was verified:** CLI and wrapper help were compared with documented options/defaults; relative links and target files were checked; the stale-name search found no active documentation matches; and the command/test validation below passed.

### P2 — supporting READMEs need a clear disposition (resolved 2026-07-12)

**Current behavior:** The former conversation notes are now `docs/development-notes.md`, clearly labeled as history and stripped of duplicate operations guidance and conversational filler. The former virtual-environment README is now `docs/contributor-setup.md`, focused on Python 3.10+ contributor setup, validation, builds, and stale-environment recovery. Both are linked from the main README.

**Why it matters:** Multiple overlapping setup narratives drift and make development history look like current user documentation.

**Recommended change:** Completed with Git-aware moves. Keep operational guidance authoritative in `README.md` and contributor-only material focused under `docs/`.

**Files affected:** `README.md`, `docs/development-notes.md`, and `docs/contributor-setup.md`.

**How it was verified:** File/link checks succeeded; the two documents have distinct stated audiences; no active documentation contains the old names or filler.

## Automation and deployment

### P1 — wrapper configuration is hardcoded (resolved 2026-07-12)

**Current behavior:** `scripts/gps_sync.sh` retains built-in defaults of `/dev/ttyACM0`, baud 9600, timeout 60, warmup 2, and status window 2. It accepts `GPS_PORT`, `GPS_BAUDRATE`, `GPS_TIMEOUT`, `GPS_WARMUP`, and `GPS_STATUS_WINDOW`, plus `--port`, `--baudrate`, `--timeout`, `--warmup`, `--status-window`, `--status`, `--no-set`, `--verbose`, and `--help`. Precedence is command-line options over environment variables over built-in defaults.

**Why it matters:** Local edits complicate upgrades, `/dev/ttyACM0` can change across boots, and unattended configuration cannot be managed externally.

**Recommended change:** Completed for configuration, help, validation, quoting, stable device paths, safe flag pass-through, and automated tests. Run ShellCheck later when it is available locally or in the deferred tooling/CI stage.

**Files affected:** `scripts/gps_sync.sh`, the narrow wrapper section in `README.md`, and `tests/test_gps_sync_script.py`.

**How it was verified:** Thirty-five pytest subprocess tests use a temporary fake repository and executable to cover defaults, precedence, by-id/spaced/metacharacter paths, flags, numeric boundaries, parse errors, missing `.venv`/executable exit codes, and child exit propagation. `bash -n` passes. ShellCheck was not installed and was not added during this stage.

### P1 — unattended deployment guidance is not release-ready (confirmed documentation gap)

**Current behavior:** The README now presents one generic root-cron example with a stable by-id path, explicit logging, managed-checkout caution, privilege boundaries, and network-time-service interaction. A reviewed systemd unit/timer, restart/failure policy, and service ordering are still not implemented.

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
2. **P1 — complete for application behavior:** Status completeness/window and timeout/warmup semantics are defined and tested.
3. **P1 — complete:** Fix-mode output, strict serial decoding, and narrow `set_system_time()` fallback behavior are corrected and tested.
4. **P1 — complete for current scope:** Deterministic NMEA, serial-failure, timeout, CLI exit-code/call-count, and shell-wrapper tests are present.
5. **P2 — complete:** User documentation is consolidated around actual workflows, device discovery, privilege boundaries, stable device paths, and time-service interaction.
6. **P1/P2 — wrapper complete, deployment open:** Wrapper configuration is external; a reviewed systemd service/timer deployment path remains future work.
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
- [x] Status collection, timeout, malformed input, serial failures, CLI paths, and clock setting are covered.
- [x] Shell-wrapper failures and external configurability are covered.
- [x] README instructions distinguish safe display modes from clock-setting mode and use current commands/options.
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

### P1 behavioral-correctness validation log (2026-07-12)

1. Initial `git status --short` confirmed the existing, uncommitted P0-stage changes. The literal `pytest` baseline command was unavailable in the shell (`pytest: command not found`), so the already-created disposable audit environment was used rather than the project `.venv`.
2. `/tmp/gps-time-sync-audit-venv/bin/pytest`
   - Baseline result: **14 passed in 0.04s** on Python 3.13.5.
3. `/tmp/gps-time-sync-audit-venv/bin/pytest -q`
   - First expanded result: **63 passed, 2 failed in 0.16s**. Both failures exposed an inconsistent synthetic fixture: GGA reported eight satellites while GSA listed six. The fixture was corrected to describe one consistent state.
4. `/tmp/gps-time-sync-audit-venv/bin/pytest -q`
   - Intermediate result after fixture correction: **65 passed in 0.15s**.
5. Multipart GSV tracking was then tightened to require every numbered part for a talker, and supported clock-fallback errno coverage was expanded.
6. `/tmp/gps-time-sync-audit-venv/bin/pytest -q`
   - Pre-documentation result: **67 passed in 0.14s**.
7. `source /tmp/gps-time-sync-audit-venv/bin/activate`, then `pytest`, `python -m gps_time_sync_vk172`, `gps-time-sync --help`, `git diff --check`, `git status --short`, `git diff --stat`, and `git diff --summary`.
   - Final result: **67 passed in 0.10s**; module execution succeeded; CLI help displayed the new `--status-window` option and post-warmup timeout wording; `git diff --check` produced no output; and only this issue document, the application module, and its main test module are modified in this stage.

### Shell-wrapper validation log (2026-07-12)

1. Before editing, `git status --short` showed the three expected uncommitted P1 behavioral-stage files, and `pytest` in the disposable audit environment reported **67 passed in 0.10s**.
2. `command -v shellcheck || true`
   - Result: no path was printed; ShellCheck is not installed, so no system package was installed during this stage.
3. `pytest -q tests/test_gps_sync_script.py`
   - Result: **35 passed in 0.30s** using temporary fake repository layouts and fake `gps-time-sync` executables.
4. `bash -n scripts/gps_sync.sh`
   - Result: exit code 0 with no output.
5. `scripts/gps_sync.sh --help`
   - Result: exit code 0 without requiring `.venv`; output lists every supported option/environment variable, built-in defaults, and `command-line options > environment variables > built-in defaults` precedence.
6. `pytest`
   - Result after implementation and narrow README edits: **102 passed in 0.37s** on Python 3.13.5.
7. A one-off Python invocation loaded the automated test fixture, created a temporary fake wrapper layout/executable, set environment port/timeout values, then supplied a spaced by-id path, decimal timeout, `--status`, and `--verbose` on the command line.
   - Result: child exit code 0 and exact recorded arguments `['--port', '/dev/serial/by-id/GPS receiver with spaces', '--baudrate', '9600', '--timeout', '12.5', '--warmup', '2', '--status-window', '2', '--status', '--verbose']`, demonstrating quoting and command-line precedence without GPS hardware.
8. Final commands: `pytest`, `bash -n scripts/gps_sync.sh`, `scripts/gps_sync.sh --help`, conditional local ShellCheck detection, `git diff --check`, `git status --short`, and `git diff --stat`.
   - Result: **102 passed in 0.38s**; Bash syntax and standalone help succeeded; ShellCheck was unavailable; `git diff --check` produced no output; and the status showed only this issue document, `README.md`, `scripts/gps_sync.sh`, and the new wrapper test module.

### Documentation consolidation validation log (2026-07-12)

1. Before editing, the current README, both supporting READMEs, this issue record, `pyproject.toml`, generated CLI help, and wrapper help were inspected. `pytest` reported **102 passed in 0.38s**, and `git status --short` captured the completed wrapper-stage changes.
2. Git-aware moves renamed `README_CHAT.md` to `docs/development-notes.md` and `README_VENV.md` to `docs/contributor-setup.md`.
3. Post-edit commands: `pytest`, `bash -n scripts/gps_sync.sh`, `gps-time-sync --help`, `scripts/gps_sync.sh --help`, and `python -m gps_time_sync_vk172`.
   - Result: **102 passed in 0.37s** on Python 3.13.5; Bash syntax passed; both help commands succeeded; and module execution printed the expected package message.
4. Relative targets `KNOWN_ISSUES_AND_TODO.md`, `docs/development-notes.md`, `docs/contributor-setup.md`, and `LICENSE` were checked with `test -f`; Markdown links in the three current guides were listed with `rg` and manually compared with those targets.
   - Result: all linked local files exist and paths resolve relative to their containing documents.
5. `grep -RIn --exclude-dir=.git --exclude-dir=.venv -e 'gps_time_syc_vk172' -e 'gps-time-syc-vk172' .`
   - Result: old spellings remain only in intentionally preserved commands/results in this document's historical audit logs; no active user-facing guide contains them.
6. `git diff --check`
   - Result: exit code 0 with no output.

The remaining implementation sequence is: systemd/deployment design and CI/tooling work, including GitHub Actions, Ruff, ShellCheck integration, and optional typing.
