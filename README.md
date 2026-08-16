# iRig BlueBoard Macro Handler

> **Notice:** This independent, community-developed project is not affiliated
> with, sponsored by, or endorsed by IK Multimedia, iRig, or any manufacturer
> of referenced hardware or software. Product names and trademarks belong to
> their respective owners.

A Python 3.10+ command-line application that connects directly to an iRig
BlueBoard over BLE-MIDI, decodes its buttons, and routes them to configurable
Windows or Linux actions. The package provides scanning, reconnecting, dry-run,
packet replay, configuration validation, JSON logging, run summaries, and
opt-in button-backlight feedback.

The tested board profile uses BlueBoard mode 2, selected by holding **C** while
powering on the pedal. It emits MIDI channel 1 Control Change messages:

| Button | Press | Release | Default action |
|---|---|---|---|
| A | CC20 value 127 | CC20 value 0 | `Ctrl+Shift+R` |
| B | CC21 value 127 | CC21 value 0 | `Alt+Tab` |
| C | CC22 value 127 | CC22 value 0 | Unmapped |
| D | CC23 value 127 | CC23 value 0 | Unmapped |

Actions are disabled unless `--execute-actions` is supplied. BlueBoard LED
feedback is a separate side effect and is disabled unless `--led-feedback` is
supplied. The source tree reports version `1.0.0` and has recorded physical
validation on Windows and Linux Mint for the tested board profile.

## Author

- Abraham Jhared Flores Azcona _(NotsoJharedtrollOx17)_ `abrahamjhared.flores@gmail.com`

## Detailed documentation

The files in [`agent-docs`](agent-docs/) expand this README without duplicating
its installation-first flow:

| Document | Purpose |
|---|---|
| [Architecture and extension guide](agent-docs/architecture-and-extension-guide.md) | Runtime boundaries, configuration model, invariants, tests, and safe extension points |
| [Platform operations and hardware findings](agent-docs/platform-operations-and-hardware-findings.md) | Windows/Linux procedures, BlueZ investigation, LED evidence, and hardware validation |
| [Release history and roadmap](agent-docs/release-history-and-roadmap.md) | Milestones, evidence, known limitations, release checklist, and future work |

## Connect the BlueBoard

1. Disconnect it from Android, a DAW, or any other active BLE client.
2. Hold button **C** while powering on the BlueBoard. Keep holding C until it
   has finished starting in mode 2.
3. Enable Bluetooth on the computer and keep the board nearby.
4. Scan, then run the client. If service discovery requires authentication,
   retry with `--pair`; pairing is not normally required by the tested board.

The client remembers the last successful device address. If that address is no
longer advertised, discovery falls back to the configured name substring or
the BLE-MIDI service UUID. After a forced board power-off, restart it while
holding C; the reconnect loop will claim it when it advertises again.

## Button backlights

In mode 2 the four switch backlights are controlled by the host. Add
`--led-feedback` to mirror every accepted physical press and release:

```powershell
.\runBlueBoard.ps1 --debug --led-feedback
```

```bash
./runBlueBoard.sh --debug --led-feedback
```

The handler echoes channel 1 CC20-CC23 with value 127 for on and value 0 for
off. It initializes all four LEDs off after each successful connection,
coalesces rapid changes through one bounded worker, serializes GATT writes, and
stops the worker without writing after disconnect. It uses acknowledged writes
when the characteristic supports them; otherwise the same queue is paced and
each release receives at most one delayed off retry. No idle reconciliation
traffic is emitted.

BlueBoard feedback packets deliberately use the fixed `80 80` BLE-MIDI
timestamp header observed on the physical device. The general encoder still
supports changing 13-bit timestamps. LED feedback is independent of macro
execution, so it works in the default dry-run mode and may be combined with
`--execute-actions`. It represents momentary button state, not persistent
amplifier, preset, or effect state.

If a legacy board has stopped responding to host LED commands, try one fresh,
paced clear sequence before power-cycling it:

```powershell
.\runBlueBoard.ps1 --led-feedback --reset-leds --debug
```

The command cannot prove that the pedal applied the clear because the tested
Windows characteristic exposes write-without-response and no LED-state
readback.

## Windows setup

From PowerShell in the repository root:

```powershell
.\setupBlueBoard.ps1
.\scanBlueBoard.ps1 --debug --scan-timeout 15
.\runBlueBoard.ps1 --debug --execute-actions --led-feedback
```

If local scripts are blocked for the current terminal only:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
```

Windows keyboard actions use the native `SendInput` API and affect the
foreground application. They cannot cross Windows integrity levels, so an
elevated destination application requires the handler to run at a compatible
level.

Setup defaults to `python\.venv`. To install a `blueboard` command outside the
repository environment, use either global form:

```powershell
.\setupBlueBoard.ps1 -Scope global
.\setupBlueBoard.ps1 -Scope global -User
```

On Windows, `global` means outside this repository's virtual environment; it
does not necessarily mean an administrator-wide installation. The second form
explicitly selects a per-user install. Setup locates the actual versioned
Python Scripts directory, adds it to the current PowerShell session, persists
it in the user `PATH`, and verifies `blueboard --version`. No reboot is
required, although terminals opened before setup must be restarted.

## Linux setup

The default Linux path creates an isolated repository environment and installs
the `evdev` keyboard dependency:

```bash
./setupBlueBoard.sh
./scanBlueBoard.sh --debug --scan-timeout 15
./runBlueBoard.sh --debug
```

Confirm BLE discovery and button logs in dry-run mode before enabling operating
system actions. Linux keyboard actions use `python-evdev` and `/dev/uinput`.
The verified permission sequence is:

```bash
./setupBlueBoard.sh --skip-system --add-input-group
# log out, then log back in
groups                         # confirm "input" is listed
./runBlueBoard.sh --debug --execute-actions --led-feedback
```

The group change is opt-in and the relogin is required. Membership in `input`
grants access to system input devices, so review it with the machine
administrator. The launcher checks `/dev/uinput` and active-session group
membership before starting BLE whenever `--execute-actions` is present. Dry-run
and LED-only operation do not require keyboard permissions.

On Debian, Ubuntu, and Linux Mint, setup uses `apt-get` when available to
install `bluez`, `python3-venv`, `python3-dev`, and `kmod`, loads `uinput`, and
installs a narrow udev rule when needed:

```text
KERNEL=="uinput", GROUP="input", MODE="0660", OPTIONS+="static_node=uinput"
```

Use `--skip-system` when those prerequisites are already present or the
distribution uses another package manager. Do not run the application
permanently as root.

Linux also provides isolated global installation scopes that avoid modifying
the protected system Python:

```bash
./setupBlueBoard.sh --scope global         # /opt venv; requires sudo
./setupBlueBoard.sh --scope global --user  # per-user pipx application
```

The system-wide form installs under `/opt/blueboard-macro-handler` and manages
`/usr/local/bin/blueboard`. The per-user form requires `pipx` and may require a
new terminal after `pipx ensurepath`.

To update a clean checkout and refresh its installation:

```bash
./updateBlueBoard.sh
./updateBlueBoard.sh --scope global
./updateBlueBoard.sh --scope global --user
```

The Windows equivalent is `.\updateBlueBoard.ps1`, with `-Scope global` and
`-User`. Both updaters refuse to run over uncommitted changes, then switch to
and fast-forward `origin/main` before reinstalling. Do not use an updater to
preserve a development branch; update that branch with Git and rerun setup
instead.

Some older BlueBoard firmware exposes BLE-MIDI as the final GATT service. On
the validated Linux Mint machine, BlueZ connected but omitted that advertised
service from its D-Bus object model. The client detects only this condition and
uses the installed `gatttool` utility with the tested BlueBoard handles. It
does not pair, bond, trust, or replace the normal BlueZ/Bleak path. This
fallback is hardware-specific and remains the principal Linux portability
limitation; see the detailed platform findings before adapting it to another
firmware revision.

## Installed CLI

The project is a standard Python package. A Windows checkout can be installed
directly:

```powershell
py -m pip install .
blueboard scan --debug
blueboard run --execute-actions --led-feedback
```

On Linux, prefer the setup script so the base package and Linux extra are
installed in an isolated environment.

Available commands:

```text
blueboard scan          Discover matching BLE devices
blueboard run           Connect, reconnect, decode, and route
blueboard replay FILE   Replay captured BLE-MIDI packets without hardware
blueboard validate      Validate and print normalized configuration
blueboard init-config   Create an editable configuration
```

Common options include `--config`, `--debug`, `--json-logs`, `--log-file`,
`--address`, `--pair`, and `--scan-timeout`. `run` adds `--execute-actions`,
`--dry-run`, `--led-feedback`, `--reset-leds`, and `--state-file`. Actions and
LED writes both default off and must be enabled independently. Ctrl+C is the
shutdown control and releases managed input state.

## Configuration

The repository launchers load
[`python/config/blueboard.json`](python/config/blueboard.json). Installed users
can create and validate a copy:

```text
blueboard init-config blueboard.json
blueboard validate --config blueboard.json
```

Each binding specifies a controller number, one-based MIDI channel,
press/release edge, optional cooldown, and optional typed action:

```json
{
  "cc": 20,
  "channel": 1,
  "edge": "press",
  "cooldownMs": 250,
  "action": {"type": "keyboard", "keys": ["CTRL", "SHIFT", "R"]}
}
```

Supported action types are:

- `keyboard`: a supported key combination;
- `log`: record a message without another side effect;
- `udp`: send a UTF-8 datagram to a host and port;
- `launch`: start a program with an argument array and `shell=false`.

Set `"action": null` to keep a binding intentionally unmapped. Legacy string
actions `ctrlShiftR` and `altTab` remain accepted for compatibility; other
strings are normalized to log actions.

Example UDP and application actions:

```json
{"type": "udp", "host": "127.0.0.1", "port": 9000, "message": "/preset/next"}
{"type": "launch", "program": "notepad.exe", "args": []}
```

Only use configurations you trust. `launch` accepts an argument array and
never invokes a command shell, but it still starts the named executable when
actions are enabled.

## Replay and logs

Test decoding and routing without the board or live side effects:

```powershell
blueboard replay python\tests\fixtures\blueboardPackets.json --debug
```

`replay` is dry-run by default; add `--execute-actions` only when intentional.
For machine-readable diagnostics:

```powershell
blueboard run --json-logs --log-file blueboard.jsonl
```

Each run reports packet, event, executed-action, action-failure, LED-write,
LED-failure, dropped-feedback, reconnect, runtime, and connected-time counters
at shutdown. A successful unacknowledged LED write means the host BLE stack
accepted the packet; it is not device-level acknowledgement.

## Development and packaging

The maintained runtime is the `blueboard_macro_handler` package under
`python/src/blueboard_macro_handler`. The adjacent camelCase modules under
`python/src` are retained milestone implementations and test fixtures; new
features should target the package namespace.

Run the complete test suite and lint the maintained package:

```powershell
.\python\.venv\Scripts\python.exe -m unittest discover -s python\tests -p "test*.py" -v
.\python\.venv\Scripts\python.exe -m ruff check python/src/blueboard_macro_handler python/tests
```

Build distributable artifacts after installing the development extra:

```powershell
py -m pip install -e ".[dev]"
py -m build
```

The current package metadata and runtime both report `1.0.0`. Physical
Windows and Linux Mint testing has confirmed macros and momentary LED feedback
on the documented board profile, while automated tests cover the decoder,
router, actions, configuration, BLE lifecycle, fallback parsing, and feedback
controller. Creating and publishing a `v1.0.0` Git tag or distribution remains
a separate maintainer release operation.

## Troubleshooting

- **Not discovered:** restart while holding C, disconnect other BLE clients,
  check batteries, move closer, and try `--scan-timeout 30`.
- **Saved address not found:** the client warns and falls back to a matching
  name or BLE-MIDI service advertisement.
- **Connects without events:** confirm logs reach `state=subscribing` and
  `state=connected`, then verify the board was started in mode 2.
- **Linux repeatedly connects and disconnects:** run with `--debug`. A
  `backend=bluez-gatttool` connection means the compatibility path handled the
  documented BlueZ service-omission case. Do not pair or trust the pedal as a
  workaround.
- **Macros only appear in logs:** add `--execute-actions`.
- **Button backlights remain off:** add `--led-feedback` and confirm mode 2.
  The flag is independent of `--execute-actions`.
- **A backlight remains stuck:** run once with `--led-feedback --reset-leds`;
  if the board still ignores the clear, power-cycle it.
- **Linux keyboard macros do not work:** rerun
  `./setupBlueBoard.sh --skip-system --add-input-group`, log out/in, and confirm
  `input` appears in `groups`.
- **Action fails:** the failure is logged and BLE notification processing
  continues.

## License

[MIT](LICENSE) © 2026 Abraham Jhared Flores Azcona.

## Citation

If you use this software in a project, publication, or technical report,
please cite it as:

```bibtex
@misc{
    floresazcona2026irigblueboard,
    title = {iRig BlueBoard Macro Handler},
    author = {Flores-Azcona, Abraham Jhared},
    year = {2026},
    month = {Aug},
    url = {https://github.com/NotsoJharedtrollOx17/iRigBlueBoard-Macro-Handler}
}
```
