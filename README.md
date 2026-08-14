# iRig BlueBoard Macro Handler

> **Notice:** This independent, community-developed project is not affiliated
> with, sponsored by, or endorsed by IK Multimedia, iRig, or any manufacturer
> of referenced hardware or software. Product names and trademarks belong to
> their respective owners.

A Python 3.10+ command-line application that connects directly to an iRig
BlueBoard over BLE-MIDI, decodes its buttons, and routes them to configurable
Windows or Linux actions. The package provides scanning, reconnecting, dry-run,
packet replay, configuration validation, JSON logging, and run summaries.

The tested BlueBoard mode emits MIDI channel 1 Control Change messages:

| Button | Press | Release | Default action |
|---|---|---|---|
| A | CC20 value 127 | CC20 value 0 | `Ctrl+Shift+R` |
| B | CC21 value 127 | CC21 value 0 | `Alt+Tab` |
| C | CC22 value 127 | CC22 value 0 | Unmapped |
| D | CC23 value 127 | CC23 value 0 | Unmapped |

Actions are disabled unless `--execute-actions` is supplied.

## Connect the BlueBoard

1. Disconnect it from Android, a DAW, or any other active BLE client.
2. Hold button **C** while powering on the BlueBoard. Keep holding C until it
   has finished starting in BLE-MIDI mode.
3. Enable Bluetooth on the computer and keep the board nearby.
4. Scan, then run the client. If service discovery requires authentication,
   retry with `--pair`.

The client remembers the last successful device address. After a forced board
power-off, restart it while holding C; the reconnect loop will claim it when it
advertises again.

## Windows setup

From PowerShell in the repository root:

```powershell
.\setupBlueBoard.ps1
.\scanBlueBoard.ps1 --debug --scan-timeout 15
.\runBlueBoard.ps1 --debug --execute-actions
```

If local scripts are blocked for the current terminal only:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
```

Windows macros use the native `SendInput` API. They affect the foreground
application and cannot cross Windows integrity levels: controlling an elevated
application requires the handler to run at a compatible level.

The setup script defaults to a repository-local virtual environment. To install
into the selected machine-wide Python installation instead, run:

```powershell
.\setupBlueBoard.ps1 -Scope global
```

Use `-User` for a global per-user install without administrator privileges:

```powershell
.\setupBlueBoard.ps1 -Scope global -User
```

Linux supports the equivalent scopes:

```bash
./setupBlueBoard.sh --scope global
./setupBlueBoard.sh --scope global --user
```

Global installation uses the active `py -3` or `python3` interpreter. Its
Python `Scripts`/`bin` directory must be on `PATH`; otherwise invoke
`py -m blueboard_macro_handler` or `python3 -m blueboard_macro_handler`.

## Linux setup

Install the system Bluetooth and virtual-input prerequisites (package names
shown for Linux Mint/Ubuntu):

```bash
./setupBlueBoard.sh
./scanBlueBoard.sh --debug --scan-timeout 15
./runBlueBoard.sh --debug --execute-actions
```

The setup script automatically installs `bluez`, `python3-venv`,
`python3-dev`, `python3-pip`, and `kmod` on Debian/Ubuntu/Linux Mint systems
when `apt-get` is available. It also attempts to load the `uinput` kernel
module. Use `--skip-system` when those prerequisites are already installed or
when your distribution uses another package manager:

```bash
./setupBlueBoard.sh --skip-system
```

On non-Debian distributions, install the equivalent BlueZ, Python virtual
environment/development, pip, and uinput packages with the native package
manager before running the script.

The Linux keyboard backend uses `python-evdev` and `/dev/uinput`. Grant a
narrowly scoped group permission instead of running the application
permanently as root. A typical local rule is:

```text
KERNEL=="uinput", GROUP="input", MODE="0660"
```

Place it in `/etc/udev/rules.d/99-blueboard-uinput.rules`, add the user to the
`input` group, reload udev rules, and log out/in. Review this permission with
the machine's administrator because membership in `input` is security
sensitive. Bleak communicates with BlueZ through D-Bus; no kernel driver or raw
HCI replacement is used.

## Installed CLI

The project is a standard Python package. Install it from a checkout:

```powershell
py -m pip install .
blueboard scan --debug
blueboard run --execute-actions
```

On Linux, include its optional keyboard dependency:

```bash
python3 -m pip install '.[linux]'
blueboard run --execute-actions
```

Available commands:

```text
blueboard scan          Discover matching BLE devices
blueboard run           Connect, reconnect, decode, and route
blueboard replay FILE   Replay captured BLE-MIDI packets without hardware
blueboard validate      Validate and print normalized configuration
blueboard init-config   Create an editable configuration
```

Useful options include `--config`, `--debug`, `--json-logs`, `--log-file`,
`--address`, `--pair`, `--scan-timeout`, `--dry-run`, and
`--execute-actions`. `run` defaults to dry-run behavior unless execution is
explicitly enabled. Ctrl+C is the panic/shutdown control and releases managed
input state.

## Configuration

The repository launchers load [python/config/blueboard.json](python/config/blueboard.json).
Installed users can create a copy with:

```text
blueboard init-config blueboard.json
blueboard validate --config blueboard.json
```

Bindings support MIDI channel, press/release edge, cooldown, and an optional
typed action:

```json
{
  "cc": 20,
  "channel": 1,
  "edge": "press",
  "cooldownMs": 250,
  "action": {"type": "keyboard", "keys": ["CTRL", "SHIFT", "R"]}
}
```

Supported actions are:

- `keyboard`: an arbitrary supported key combination;
- `log`: record a message without another side effect;
- `udp`: send a UTF-8 datagram to a host and port;
- `launch`: start a program with an argument array and `shell=false`;
- `null`: leave the button intentionally unmapped.

Example UDP and application actions:

```json
{"type": "udp", "host": "127.0.0.1", "port": 9000, "message": "/preset/next"}
{"type": "launch", "program": "notepad.exe", "args": []}
```

Only use configurations you trust. `launch` deliberately accepts an argument
array and never invokes a command shell.

## Replay and logs

Test routing without the board or side effects:

```powershell
blueboard replay python\tests\fixtures\blueboardPackets.json --debug
```

For machine-readable diagnostics:

```powershell
blueboard run --json-logs --log-file blueboard.jsonl
```

Each run reports packet, event, action, failure, reconnect, runtime, and
connected-time counters at shutdown.

## Development and packaging

Run the complete test suite:

```powershell
.\python\.venv\Scripts\python.exe -m unittest discover -s python\tests -p "test*.py" -v
```

Build distributable artifacts after installing the development extra:

```powershell
py -m pip install -e ".[dev]"
py -m build
```

Outbound BLE writes and standards-valid BLE-MIDI encoding are available as
internal building blocks. LED feedback is not enabled by default because the
BlueBoard-specific outbound LED message semantics have not yet been confirmed
from hardware.

## Troubleshooting

- **Not discovered:** restart while holding C, disconnect other BLE clients,
  check batteries, move closer, and try `--scan-timeout 30`.
- **Saved address not found:** the client logs a warning and falls back to a
  matching BlueBoard name or BLE-MIDI service advertisement.
- **Connects without events:** confirm logs reach `state=subscribing` and
  `state=connected`, then verify the board was started in mode C.
- **Macros only appear in logs:** add `--execute-actions`.
- **Linux cannot open uinput:** load the module and verify the user's udev/group
  permission for `/dev/uinput`.
- **Action fails:** the failure is logged and BLE processing continues.
