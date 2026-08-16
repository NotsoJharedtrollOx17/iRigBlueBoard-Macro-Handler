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

The tested BlueBoard mode emits MIDI channel 1 Control Change messages:

| Button | Press | Release | Default action |
|---|---|---|---|
| A | CC20 value 127 | CC20 value 0 | `Ctrl+Shift+R` |
| B | CC21 value 127 | CC21 value 0 | `Alt+Tab` |
| C | CC22 value 127 | CC22 value 0 | Unmapped |
| D | CC23 value 127 | CC23 value 0 | Unmapped |

Actions are disabled unless `--execute-actions` is supplied. BlueBoard LED
feedback is a separate side effect and is disabled unless `--led-feedback` is
supplied.

## Author

- Abraham Jhared Flores Azcona _(NotsoJharedtrollOx17)_ `abrahamjhared.flores@gmail.com`

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

## Button backlights

In BLE-MIDI mode C, the four switch backlights are controlled by the host. Add
`--led-feedback` to mirror every physical press and release:

```powershell
.\runBlueBoard.ps1 --debug --led-feedback
```

```bash
./runBlueBoard.sh --debug --led-feedback
```

The handler sends channel 1 CC20-CC23 with value 127 on press and value 0 on
release. It initializes all four LEDs off after each successful connection,
coalesces rapid state changes through a bounded worker, and detaches the
worker without attempting writes after disconnect. When the BLE characteristic
supports acknowledged writes, the handler uses them. Otherwise it spaces LED
writes and retries only a released button's off command once; it does not send
continuous background reconciliation traffic. LED packets deliberately use
the fixed `80 80` timestamp header emitted by BlueBoard firmware; the general
BLE-MIDI encoder remains capable of standards-valid changing timestamps.

LED feedback is independent of macro execution, so `--led-feedback` works in
the default dry-run mode and can also be combined with `--execute-actions`.
This is momentary physical-button feedback; it does not represent persistent
amplifier, preset, or effect state.

If a legacy board has stopped responding to host LED commands, try one fresh,
paced clear sequence before power-cycling it:

```powershell
.\runBlueBoard.ps1 --led-feedback --reset-leds --debug
```

The command cannot prove that the board accepted the clear because this
BlueBoard exposes write-without-response on Windows.

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

On Windows, `global` means that the command is available outside this
repository's virtual environment; it does not necessarily mean a machine-wide
administrator install. If the selected Python installation is not writable,
pip automatically falls back to the current user's Python installation. The
setup script detects the actual versioned Scripts directory created by Python
(for example, `...\AppData\Roaming\Python\Python314\Scripts`), adds it to the
current PowerShell session and persists it in the user's `PATH`. No reboot is
required: `blueboard --version` works in the current session after setup, and
new terminal windows inherit the updated `PATH`. Use `-User` explicitly when a
non-administrator per-user install is desired.

Linux keeps the same scope API, with two safe global variants that avoid
Ubuntu/Debian's PEP 668 restriction:

```bash
./setupBlueBoard.sh --scope global         # system-wide; requires sudo
./setupBlueBoard.sh --scope global --user  # current user; uses pipx
```

Without `--user`, Linux installs a root-owned application environment at
`/opt/blueboard-macro-handler/venv` and a `blueboard` launcher in
`/usr/local/bin`, making it available to all users without modifying the OS
Python. With `--user`, pipx installs an editable per-user command in the
user's local binary directory; open a new terminal after setup if PATH was
updated. Run the system-wide command only from a checkout you trust, because
it installs code with elevated privileges. Re-run the same command to update
the system-wide copy after changing the checkout.

## Linux setup

To update an existing checkout and refresh its installation in one step, make
sure local changes are committed or stashed, then run the matching updater:

```bash
./updateBlueBoard.sh                         # local venv
./updateBlueBoard.sh --scope global          # system-wide; requires sudo
./updateBlueBoard.sh --scope global --user   # pipx per-user install
```

The updater stops before fetching if the checkout has uncommitted changes. It
then fetches and fast-forwards the local `main` branch from `origin/main`,
before rerunning the selected setup scope. The Windows equivalent is
`.\updateBlueBoard.ps1`, with `-Scope global` and `-User` using the same
meanings as the setup script.

Install the system Bluetooth and virtual-input prerequisites (package names
shown for Linux Mint/Ubuntu):

```bash
./setupBlueBoard.sh
./scanBlueBoard.sh --debug --scan-timeout 15
./runBlueBoard.sh --debug --execute-actions
```

For Linux keyboard macros, the verified first-install sequence is:

```bash
./setupBlueBoard.sh --skip-system
sudo usermod -aG input "$USER"
# log out, then log back in
groups                         # confirm "input" is listed
./runBlueBoard.sh --debug --execute-actions
```

As an explicit convenience, setup can perform the group change for you:

```bash
./setupBlueBoard.sh --skip-system --add-input-group
```

This option changes persistent account permissions and still requires a logout
and login. It is opt-in because membership in `input` grants access to system
input devices; without the flag, setup only prints the equivalent `usermod`
command.

The launcher checks `/dev/uinput` and the current user's `input` membership
before starting BLE when `--execute-actions` is present. This turns a silent
macro failure into an immediate setup message. The relogin is required for
the new group membership to reach the current session.

The setup script automatically installs `bluez`, `python3-venv`,
`python3-dev`, and `kmod` on Debian/Ubuntu/Linux Mint systems when `apt-get`
is available. Per-user global scope additionally installs `pipx`. It also
attempts to load the `uinput` kernel module. Use `--skip-system` when those
prerequisites are already installed or when your distribution uses another
package manager:

```bash
./setupBlueBoard.sh --skip-system
```

On non-Debian distributions, install the equivalent BlueZ, Python virtual
environment/development, uinput, and pipx (for `--scope global --user`)
packages with the native package manager before running the script.

The Linux keyboard backend uses `python-evdev` and `/dev/uinput`. Setup now
loads the `uinput` driver, creates or refreshes the device node, and applies a
narrow `input`-group permission when udev is available. If the current user is
not already in that group, setup prints the required `usermod` command; log
out and in afterward. Do not run the application permanently as root. A
typical local rule is:

```text
KERNEL=="uinput", GROUP="input", MODE="0660", OPTIONS+="static_node=uinput"
```

The setup script places this rule in `/etc/udev/rules.d/99-blueboard-uinput.rules`
when no rule exists. Review this permission with the machine's administrator
because membership in `input` is security sensitive. Bleak communicates with
BlueZ through D-Bus; no kernel driver or raw HCI replacement is used.

Some older BlueBoard firmware exposes BLE-MIDI as the final GATT service. A
known BlueZ service-discovery failure can advertise that service but omit it
from D-Bus, producing a repeated connect/disconnect loop. On Linux, the client
detects this exact condition and falls back to `gatttool` from the already
required `bluez` package. The fallback subscribes directly to the BlueBoard's
fixed BLE-MIDI handles and does not pair, bond, or trust the pedal. Other
devices and platforms continue to use Bleak normally. With `--led-feedback`,
the same fallback uses one interactive ATT session for notifications and
serialized LED writes, with a lightweight descriptor read to detect a silent
disconnect and resume the normal reconnect loop.

## Installed CLI

The project is a standard Python package. Install it from a checkout:

```powershell
py -m pip install .
blueboard scan --debug
blueboard run --execute-actions --led-feedback
```

On Linux, use the setup script so dependencies are installed into an isolated
environment. Do not use system `python3 -m pip install` on Ubuntu/Debian,
because those distributions protect their system Python:

```bash
./setupBlueBoard.sh                 # repository-local environment
./setupBlueBoard.sh --scope global  # system-wide CLI
./setupBlueBoard.sh --scope global --user  # pipx-managed per-user CLI
blueboard run --execute-actions --led-feedback
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
`--execute-actions`. The `run` command also accepts `--led-feedback`. It
defaults to dry-run behavior with LED feedback off unless each side effect is
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

Each run reports packet, event, action, LED-write, failure, dropped-feedback,
reconnect, runtime, and connected-time counters at shutdown.

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

Outbound BLE writes and standards-valid BLE-MIDI encoding drive the stable,
opt-in LED feedback controller released in v1.0.0. The rapid-press,
forced-disconnect, reconnect, and Linux Mint hardware checks have been recorded
against the supported physical board profile. The feature remains opt-in so
users explicitly choose whether outbound LED writes are enabled.

## Troubleshooting

- **Not discovered:** restart while holding C, disconnect other BLE clients,
  check batteries, move closer, and try `--scan-timeout 30`.
- **Saved address not found:** the client logs a warning and falls back to a
  matching BlueBoard name or BLE-MIDI service advertisement.
- **Connects without events:** confirm logs reach `state=subscribing` and
  `state=connected`, then verify the board was started in mode C.
- **Linux repeatedly connects and disconnects:** run with `--debug`. A
  `backend=bluez-gatttool` connection means the automatic compatibility path
  handled BlueZ omitting the board's final BLE-MIDI service. Do not pair or
  trust the pedal manually.
- **Macros only appear in logs:** add `--execute-actions`.
- **Button backlights remain off:** confirm the board was started while holding
  C and add `--led-feedback`. The flag is independent of `--execute-actions`.
- **Linux keyboard macros do not work:** rerun
  `./setupBlueBoard.sh --skip-system --add-input-group`, log out/in, and
  confirm `input` appears in `groups`. The launcher performs the same
  `/dev/uinput` and group checks before `--execute-actions` starts.
- **Action fails:** the failure is logged and BLE processing continues.

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
