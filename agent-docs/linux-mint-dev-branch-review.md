# Linux Mint `dev` Branch Review

Date: 2026-08-14  
Reviewed branch: `dev` at `796f4b6`  
Comparison base: `main` at `7737eba`

## Executive assessment

The Linux Mint work is a substantive platform implementation rather than a
documentation-only port. It addresses two distinct failures observed on real
hardware:

1. BlueZ 5.72 connected to the BlueBoard but omitted its advertised BLE-MIDI
   service from the D-Bus GATT model.
2. Linux macro injection required a usable `/dev/uinput` device plus permission
   for the active desktop user.

The branch adds a narrowly scoped BlueZ compatibility backend, prepares uinput
permissions, improves Linux installation scopes, protects macro startup with a
launcher guard, adds update scripts, records the machine investigation, and
bumps the development version to `0.3.0`.

The implementation is suitable for continued testing on `dev`. Before merging
to `main` or declaring `1.0.0`, the fixed-handle fallback, cross-platform test
collection, and branch behavior of the updater should be addressed or accepted
explicitly as release limitations.

## Commit inventory

- `487dc86`: consolidated Linux system packages into the setup script.
- `30db339`: corrected the initial Linux pipx installation path.
- `5012880` (`v0.2.1`): added installation-update behavior.
- `ce85efe`: investigated and corrected the Linux BLE connection loop.
- `88165a5`: aligned package/runtime versions to `0.3.0`.
- `796f4b6`: completed Linux keyboard/uinput setup and validation guidance.

Relative to `main`, the branch changes 14 files with approximately 631 added
lines and 38 removed lines.

## Verified improvements

### Linux BLE discovery and connection

The investigation isolated the failure to BlueZ's D-Bus service exposure, not
the radio, controller, advertisement, UUIDs, or the board's ATT table.

The client still uses Bleak first on both operating systems. Only when Linux
connects successfully and the BLE-MIDI service is absent does it raise
`BluezMidiServiceOmitted` and invoke the compatibility backend. Windows and
normal Linux service discovery remain on the existing Bleak path.

The fallback:

- enables notifications through CCC handle `0x0023`;
- listens for MIDI notifications on value handle `0x0022`;
- feeds notification bytes into the existing decoder/router;
- reuses metrics, state persistence, reconnect cleanup, and logging;
- does not pair, bond, or trust the pedal.

The Linux Mint test reached a stable
`state=connected ... backend=bluez-gatttool` state instead of the previous
connect/disconnect loop.

### Linux keyboard macros

The Linux action backend now turns low-level `evdev.UInput` failures into a
clear application error explaining that `/dev/uinput` and input-group access
are required.

`setupBlueBoard.sh` now:

- installs BlueZ, Python venv/development packages, kmod, and optionally pipx;
- loads the uinput driver;
- installs a persistent udev rule for `/dev/uinput`;
- repairs the node/group/mode when necessary;
- optionally adds the user to `input` with `--add-input-group`;
- explicitly warns that logout/login is required after group changes.

`runBlueBoard.sh` refuses to start `--execute-actions` unless `/dev/uinput` is a
character device and the current session belongs to `input`. Dry-run BLE
diagnostics remain available without those permissions.

### Installation scopes

The Linux setup now avoids modifying an externally managed system Python:

- default: repository-local virtual environment;
- global per-user: isolated pipx application;
- global system-wide: root-owned venv under `/opt/blueboard-macro-handler` with
  a managed `/usr/local/bin/blueboard` launcher.

The system installer refuses to overwrite an unrelated existing launcher.
Windows global installation now uses `--upgrade` so rerunning setup refreshes
the installed package. On Windows, the global scope is outside the repository
virtual environment; if the machine Python is not writable, pip may select a
per-user installation. The PowerShell setup script resolves the actual
versioned Scripts directory, updates the current and future user `PATH`, and
does not require a reboot.

### Documentation and evidence

The branch adds two durable records:

- `linux-blueboard-connection-investigation.md` documents the BlueZ evidence,
  pairing experiment, fallback, and bounded live test.
- `linux-keyboard-validation.md` documents the uinput permission model,
  security implication, logout requirement, and verified procedure.

The README now explains PEP 668, isolated installation scopes, uinput setup,
the BlueZ compatibility backend, and Linux-specific troubleshooting.

## Current validation

On the current Windows checkout:

- `pytest`: 35 tests and 2 parameterized subtests passed;
- Ruff: all packaged-source and package-test checks passed;
- worktree was clean before this review note was added.

On the Linux Mint machine, the repository notes report:

- BlueZ/Bleak discovery behavior reproduced and diagnosed;
- stable connection through the gatttool compatibility path;
- `/dev/uinput` setup and active-session group requirement validated;
- Linux BLE and keyboard macro procedure validated.

The Linux investigation also reports three Windows-specific test failures when
the complete suite is run on Linux. Those are test portability problems rather
than observed Linux runtime failures, but they prevent a clean cross-platform
CI result.

## Risks and limitations

### 1. Fixed GATT handles

The compatibility backend hard-codes value handle `0x0022` and CCC handle
`0x0023`. These match the tested BlueBoard firmware but are not guaranteed for
another hardware or firmware revision. A future version should discover the
handles dynamically or make them explicit configuration with validation.

### 2. `gatttool` dependency

`gatttool` is a legacy/deprecated BlueZ utility. It is present and functional
on the tested Linux Mint system, but its availability and output format are not
guaranteed on future BlueZ distributions. The fallback detects when the binary
is absent and fails clearly, but this remains the largest long-term Linux
maintenance risk.

### 3. Update scripts always target `main`

Both update scripts fetch and switch to `origin/main` unconditionally. Running
one from a clean `dev` checkout changes the user to `main` and reinstalls that
version, which currently excludes the Linux work under review. This is safe for
a production updater after `dev` is merged, but surprising during prerelease
testing. Add an explicit `--branch main|dev`/`-Branch` option or provide a
separate documented development update procedure.

### 4. Cross-platform test portability

Windows ctypes tests should skip on non-Windows hosts or assert ABI sizes based
on platform. A release candidate should produce a green test run on both
Windows and Linux rather than documenting expected failures.

### 5. Input-group permissions

Membership in `input` is security-sensitive. The branch handles this well by
making group modification opt-in, avoiding a permanently root-run daemon, and
documenting the risk. This should remain explicit in release documentation.

### 6. Compatibility-backend process tests

The pure gatttool notification parser is tested. The subprocess lifecycle,
subscription-success detection, termination, timeout, and reconnect behavior
are not yet fully mocked in automated tests. Those should be covered before the
fallback is treated as a stable public backend.

## Recommended next steps

1. Run and record the full `A`–`D` button sequence through the Linux fallback,
   including macro execution and release logs.
2. Make Windows-only tests skip or adapt on Linux, then require the full suite
   to pass on both platforms.
3. Add mocked tests for gatttool startup, notification streaming, process exit,
   Ctrl+C termination, and reconnect/backoff.
4. Decide whether update scripts are production-only (`main`) or should accept
   an explicit branch for `dev` validation.
5. Investigate dynamic ATT handle discovery or formalize the tested handles as
   a hardware-specific compatibility profile.
6. Repeat Linux validation after a reboot to confirm the udev rule, module
   loading, group membership, and launcher remain effective.
7. Merge `dev` to `main` only after the above release-blocking choices are
   resolved; retain `0.3.x` until both platforms have clean validation.

## Release judgment

The work materially advances Linux support and justifies the `0.3.0`
development version. It is not yet sufficient evidence for `1.0.0` because the
Linux compatibility path is firmware-handle-specific, the updater currently
targets `main` regardless of the active branch, and the full suite is not yet
green on Linux. None of these invalidate the implementation; they define the
remaining stabilization work.
