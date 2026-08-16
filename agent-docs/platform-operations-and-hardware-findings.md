# Platform operations and hardware findings

## Purpose and evidence boundary

This document combines the Windows LED investigation, Linux Mint connection
investigation, keyboard-permission validation, and final cross-platform
hardware record. It is intentionally more detailed than the README so future
maintainers can distinguish physical observations from software assumptions.

Evidence is labeled implicitly by its source:

- **Observed** means recorded from the physical iRig BlueBoard or operating
  system during the dated test runs.
- **Implemented** means verified by inspection of the current source tree.
- **Automated** means covered by repository tests with mocked or pure inputs.
- **Unverified elsewhere** means the behavior should not be generalized beyond
  the tested hardware, firmware, or operating-system profile.

## Supported physical profile

The recorded hardware contract is an iRig BlueBoard started in mode 2 by
holding **C** during power-up.

| Button | Press | Release | LED on | LED off |
|---|---|---|---|---|
| A | `B0 14 7F` | `B0 14 00` | `B0 14 7F` | `B0 14 00` |
| B | `B0 15 7F` | `B0 15 00` | `B0 15 7F` | `B0 15 00` |
| C | `B0 16 7F` | `B0 16 00` | `B0 16 7F` | `B0 16 00` |
| D | `B0 17 7F` | `B0 17 00` | `B0 17 7F` | `B0 17 00` |

Input and feedback use MIDI channel 1. Values 64 or greater are treated as on
or pressed; values below 64 are off or released.

```text
BLE-MIDI service        03b80e5a-ede8-4b33-a751-6ce34ec4c700
BLE-MIDI characteristic 7772e5db-3868-4112-a1a9-f2669d106bf3
tested ATT value handle 0x0022
tested ATT CCC handle   0x0023
```

The UUIDs are standard BLE-MIDI identifiers. The ATT handles are not standard;
they belong only to the tested BlueBoard attribute layout.

## Shared operating rules

Before diagnosing either platform:

1. Disconnect phones, tablets, DAWs, MIDI utilities, and other BLE clients.
2. Power the board off.
3. Hold C while powering it on and allow startup to finish.
4. Start with a scan and dry-run connection.
5. Confirm A-D press and release logs before enabling macros.
6. Enable LED feedback independently when visual validation is required.
7. Retain `--debug` logs when behavior differs from this record.

Pairing is not part of the normal tested workflow. The application can request
pairing through `--pair`, but the Linux investigation showed that pairing did
not fix the service-omission problem.

## Windows operations

### Local setup and run

```powershell
.\setupBlueBoard.ps1
.\scanBlueBoard.ps1 --debug --scan-timeout 15
.\runBlueBoard.ps1 --debug
.\runBlueBoard.ps1 --debug --execute-actions --led-feedback
```

The first form installs an editable package in `python\.venv`. The launchers
always use that environment and the repository configuration.

Use `-Scope global` when the installed `blueboard` command must be available
outside the checkout:

```powershell
.\setupBlueBoard.ps1 -Scope global
.\setupBlueBoard.ps1 -Scope global -User
blueboard --version
```

The setup script checks both the selected Python Scripts directory and the
versioned per-user Scripts directory for `blueboard.exe`. It adds the detected
directory to the current process and persists it in the user PATH. If an older
terminal still cannot resolve the command, open a new terminal; a system
reboot is unnecessary.

### Keyboard behavior

Windows actions use the native `SendInput` API. The complete `INPUT` union is
required even for keyboard-only use because the largest union member controls
the native structure size. On 64-bit Windows, the expected size is 40 bytes.
The earlier incomplete structure produced `WinError 87`; the packaged backend
and tests now preserve the correct ABI.

`SendInput` targets the foreground application and is subject to User
Interface Privilege Isolation. A normally launched handler cannot inject input
into a higher-integrity elevated application.

## Windows LED investigation

### Initial failure pattern

Physical testing on 2026-08-14 and 2026-08-15 reproduced two related symptoms:

1. a released button, especially C or D, could remain lit; and
2. after repeated button activity, input events continued but physical LEDs
   stopped responding to new host writes.

Macro dispatch was not the cause. The C-only reproduction used an unmapped
button, and physical press/release notifications continued to arrive while the
LED state was wrong.

The tested characteristic advertised `write-without-response`, not
acknowledged `write`. Windows therefore confirmed only that each packet was
accepted by the host BLE stack. It could not confirm that the pedal received or
applied the packet.

### 2026-08-14 trace

The trace selected the unacknowledged transport at `22:36:33.138`. C release
arrived at `22:37:02.472`, and the corresponding C-off write was logged at
`22:37:02.479`. The former periodic reconciler kept sending C-off commands at
two-second intervals through `22:37:43.914`, but the physical light remained
stuck.

The shutdown summary recorded:

```text
input events      30
LED writes       169
connected time   71.923 seconds
local failures    0
queue drops       0
```

This disproved the assumption that periodic background refresh would recover
the receiver. It produced substantial traffic without device-level evidence
or recovery.

### 2026-08-15 trace

A more conservative run received 28 events and produced 46 planned writes:

```text
initial clears   4
LED-on writes   14
LED-off writes  14
off retries     14
```

No local write failed, no feedback entry was dropped, and the BLE connection
did not reconnect. Every physical press had a corresponding logged LED-on
write, yet the physical board eventually stopped lighting. Queue coalescing
was therefore not losing the desired on states.

Every captured packet emitted by the BlueBoard began with the BLE-MIDI header
`80 80`, representing a zero timestamp. The host LED encoder at that point used
a changing 13-bit timestamp, which wraps every 8.192 seconds. An independent
BlueBoard integration report described a similar output stall and reported
that an immediate/zero timestamp corrected it.

### Corrected feedback policy

The stable implementation now:

- encodes BlueBoard LED frames with fixed header `80 80`;
- leaves the general BLE-MIDI encoder capable of normal timestamps;
- initializes A-D off once after connection;
- serializes and coalesces requested states;
- spaces writes by 125 ms;
- retries only the released button's off state once after 200 ms;
- cancels that retry when the button is pressed again;
- emits no idle background reconciliation traffic;
- unbinds without attempting cleanup writes after disconnect;
- provides one paced clear sequence through `--reset-leds`.

Subsequent physical testing confirmed stable momentary feedback on Windows and
Linux Mint with this policy. The absence of readback remains a hardware
limitation: a successful local write counter is not proof of visible state.

### Windows LED regression procedure

1. Run `.\runBlueBoard.ps1 --led-feedback --debug`.
2. Confirm the four initialization lines use packets beginning `80 80`.
3. Press and release C at least 20 times, including rapid cycles.
4. Repeat for A, B, and D.
5. Combine A/B with `--execute-actions` and confirm macro work does not alter
   LED timing.
6. Keep the connection active longer than several former timestamp-wrap
   periods.
7. Power the board off while a light is on, restart in mode 2, and confirm all
   lights initialize off after reconnect.
8. Confirm no periodic reconciliation log appears while the board is idle.

If a light becomes stuck, run one reset before power-cycling:

```powershell
.\runBlueBoard.ps1 --led-feedback --reset-leds --debug
```

Record whether the reset clears the light. Do not describe it as guaranteed
recovery.

## Linux Mint connection investigation

### Executive result

The original Linux connect/disconnect loop was not caused by a disabled
adapter, desktop pairing conflict, invalid advertisement, or incorrect UUID.
Bleak connected successfully, but BlueZ 5.72 omitted the BlueBoard's final
BLE-MIDI service from the D-Bus GATT object model. The application treated the
missing service as failure, exited the Bleak context, disconnected, and entered
its reconnect backoff.

Low-level ATT inspection showed that the board's full GATT table remained
available. The BlueZ-bundled `gatttool` utility could discover the final service
and subscribe to it. The implementation therefore retains Bleak everywhere and
uses a narrow Linux compatibility path only after this precise omission.

### Test-machine evidence

The 2026-08-13 investigation recorded:

```text
distribution context  Linux Mint
BlueZ                 5.72
kernel                7.0.0-28-generic
controller            Realtek hci0, 0C:96:E6:CF:64:4C
BlueBoard             BC:6A:29:34:DD:76
advertised name       iRig BlueBoard
```

The hardware addresses identify that test only and must not be copied into a
default configuration.

`bluetoothctl devices Paired` did not list the BlueBoard. The adapter was
powered and the Bluetooth service was active. BlueZ logged repeated
`No matching connection for device` messages on the same cadence as the
application retries; those messages were a consequence of sessions being
closed, not evidence that another desktop process owned the pedal.

### Application evidence before correction

The application reached:

```text
discovered name=iRig BlueBoard address=BC:6A:29:34:DD:76 RSSI=-36
state=connecting pair=False
state=discovering
```

BlueZ reported `ServicesResolved=True`, but D-Bus exposed only Generic Access,
Generic Attribute, Device Information, and Battery services. The client then
raised:

```text
RuntimeError('BLE-MIDI service was not discovered')
```

Exiting `BleakClient` disconnected the board and restarted the loop.

### ATT evidence

The complete primary-service table included the advertised final service:

```text
0x0001-0x000b  Generic Access
0x000c-0x000f  Generic Attribute
0x0010-0x001a  Device Information
0x001b-0x001f  Battery Service
0x0020-0xffff  03b80e5a-ede8-4b33-a751-6ce34ec4c700
```

The tested BLE-MIDI characteristic layout was:

```text
0x0022  7772e5db-3868-4112-a1a9-f2669d106bf3
0x0023  00002902-0000-1000-8000-00805f9b34fb
```

Writing `0100` to the Client Characteristic Configuration descriptor succeeded
and enabled notifications. This isolated the problem to BlueZ's D-Bus service
exposure path rather than the controller, radio, advertisement, or board ATT
table.

### Pairing experiment

The `--pair` option was tested once. Pairing remained pending, did not produce
a useful bond, and temporarily marked the pedal trusted. The test state was
reverted with `bluetoothctl untrust` and `bluetoothctl disconnect`. Pairing is
not used as an automatic workaround.

## Linux compatibility path

`BluezMidiServiceOmitted` is raised only on Linux after a successful Bleak
connection lacks the expected service. The reconnect loop then invokes
`runBluezGatttoolFallback()` with the discovered address.

Without LED feedback, the compatibility process uses a simple subscription:

```text
gatttool -b <address> --char-write-req --handle=0x0023 --value=0100 --listen
```

Notification lines for handle `0x0022` are parsed into bytes and fed through
the same decoder, router, action dispatcher, metrics, and disconnect cleanup as
the Bleak path.

With LED feedback enabled, one interactive session is used:

1. start `gatttool --interactive -b <address>`;
2. send `connect`;
3. write `0100` to handle `0x0023`;
4. bind the feedback writer after the successful subscription response;
5. consume notifications from `0x0022`;
6. serialize feedback as `char-write-cmd 0x0022 <packet>`;
7. read the descriptor every five seconds while otherwise silent, detecting a
   disconnected session and returning to reconnect backoff.

The process responds to the shared stop event, is terminated on exit, and is
killed after a bounded wait if graceful termination stalls. It does not pair,
bond, or trust the pedal.

The fallback has two important limits:

- `gatttool` is a legacy BlueZ utility and may be absent or change behavior on
  future distributions;
- handles `0x0022` and `0x0023` are specific to the tested firmware layout.

If either assumption changes, fail clearly. Do not silently apply these handles
to another BLE-MIDI product.

## Linux keyboard validation

### Verified procedure

```bash
./setupBlueBoard.sh --skip-system --add-input-group
# log out and log back in
groups
./runBlueBoard.sh --debug --execute-actions
```

The `groups` output must contain `input`. Supplementary group membership does
not appear in an already-running desktop session, so the logout/login cannot
be replaced by merely opening another shell in the same session.

### Permission model

The packaged Linux backend creates a virtual keyboard through `evdev.UInput`.
The setup script:

- loads the `uinput` kernel module;
- installs or reuses a udev rule;
- triggers and settles udev when available;
- creates `/dev/uinput` with major/minor `10:223` if necessary;
- assigns group `input` and mode `0660`;
- optionally adds the target user to `input`.

The persistent rule is:

```text
KERNEL=="uinput", GROUP="input", MODE="0660", OPTIONS+="static_node=uinput"
```

`runBlueBoard.sh` checks that `/dev/uinput` is a character device and that the
current session belongs to `input` only when `--execute-actions` is supplied.
This keeps BLE diagnostics and LED-only testing available without keyboard
permission.

Membership in `input` is security-sensitive because it grants access to system
input devices. The application should not be run permanently as root.

## Linux installation scopes

| Scope | Command | Result |
|---|---|---|
| Repository | `./setupBlueBoard.sh` | Editable package plus Linux extra in `python/.venv` |
| Per-user global | `./setupBlueBoard.sh --scope global --user` | Editable pipx application and user-local launcher |
| System-wide global | `./setupBlueBoard.sh --scope global` | Root-owned venv in `/opt/blueboard-macro-handler` and managed `/usr/local/bin/blueboard` |

These paths avoid modifying Debian/Ubuntu's externally managed Python. The
system installer refuses to replace an unrelated launcher. Run elevated setup
only from a trusted checkout because it installs that checkout's code.

When `apt-get` is available, setup installs BlueZ, Python venv/development
support, and kmod. The pipx package is added for per-user global scope. On other
distributions, install equivalents with the native package manager and use
`--skip-system`.

## Cross-platform validation record

The following has been physically confirmed for the documented profile:

| Behavior | Windows | Linux Mint |
|---|---|---|
| BLE advertisement and discovery | Confirmed | Confirmed |
| CC20-CC23 press/release decoding | Confirmed | Confirmed |
| Default A/B keyboard macros | Confirmed | Confirmed with uinput permission |
| C/D intentionally unmapped | Confirmed | Confirmed |
| Reconnect path | Confirmed during development | Confirmed through compatibility backend |
| Momentary A-D LED feedback | Confirmed | Confirmed through `gatttool` fallback |
| Fixed `80 80` feedback frames | Confirmed in debug traces | Confirmed in fallback trace |
| Clean fallback disconnect | Not applicable | Confirmed |

Automated tests additionally exercise packet decoding, routing, native Windows
input layout, feedback coalescing and retries, mocked Bleak lifecycle,
serialized writes, `gatttool` notification parsing, interactive subscription,
health checking, reset behavior, and process cleanup.

The record does not establish:

- compatibility with every BlueBoard firmware or hardware revision;
- compatibility with arbitrary BLE-MIDI pedals;
- availability of `gatttool` on every Linux distribution;
- device-level acknowledgement for unacknowledged LED writes;
- an eight-hour soak or 1,000-cycle qualification run;
- complete BLE-MIDI protocol conformance.

## Operational validation sequence

### Windows

```powershell
.\scanBlueBoard.ps1 --debug --scan-timeout 15
.\runBlueBoard.ps1 --debug
.\runBlueBoard.ps1 --debug --execute-actions
.\runBlueBoard.ps1 --debug --led-feedback
.\runBlueBoard.ps1 --debug --execute-actions --led-feedback
```

### Linux Mint

```bash
./scanBlueBoard.sh --debug --scan-timeout 15
./runBlueBoard.sh --debug
./runBlueBoard.sh --debug --led-feedback
./runBlueBoard.sh --debug --execute-actions --led-feedback
```

For both platforms, verify:

1. scan output identifies the expected board;
2. logs reach `state=connected`;
3. each physical press and release is logged exactly once after edge
   normalization;
4. A and B execute only with `--execute-actions`;
5. C and D remain `macro=unmapped` with the default configuration;
6. A-D LEDs mirror physical state only with `--led-feedback`;
7. Ctrl+C prints a summary and releases resources;
8. a forced board power cycle enters reconnect backoff and later reconnects.

On affected Linux systems, also verify:

```text
BlueZ D-Bus omitted the advertised BLE-MIDI service; using the BlueZ gatttool compatibility path
state=connected ... backend=bluez-gatttool
```

## Diagnostic interpretation

| Symptom or log | Interpretation | Next action |
|---|---|---|
| No matching advertisement | Wrong startup mode, another client owns the pedal, weak signal, or scan too short | Restart while holding C, disconnect other clients, increase timeout |
| Saved address warning | Stored address was absent | Allow name/service fallback or pass `--address` intentionally |
| `state=backoff` after discovery | Inspect the attached exception; the connection, service, subscription, or backend failed | Retain full debug trace |
| `backend=bluez-gatttool` | Known Linux service-omission compatibility path selected | Confirm installed `gatttool` and tested handles |
| Repeated Linux disconnects without fallback | Failure did not match the narrow omission condition or fallback failed | Inspect BlueZ services and process output; do not pair blindly |
| Macro logs show `execute=False` | Expected dry-run boundary | Add `--execute-actions` only after validation |
| C/D show `macro=unmapped` | Expected default configuration | Add a trusted typed action if desired |
| `/dev/uinput` launcher error | Device node or current-session permission missing | Rerun setup, add group, log out/in |
| LED debug write succeeds but light does not change | Host accepted an unacknowledged packet; pedal application is unknown | Try reset once, then power-cycle and retain logs |
| Feedback queue drop | Worker could not accept a state request | Treat as a defect; retain metrics and reproduction |
| Action exception | Backend or target action failed | BLE input continues; correct the action or platform permission |

## References

- [BLE-MIDI specification](https://www.hangar42.nl/wp-content/uploads/2017/10/BLE-MIDI-spec.pdf)
- [Bleak client API](https://bleak.readthedocs.io/en/latest/api/client.html)
- [Bleak Linux backend](https://bleak.readthedocs.io/en/stable/backends/linux.html)
- [BlueZ GATT D-Bus API](https://github.com/bluez/bluez/blob/master/doc/org.bluez.GattCharacteristic.rst)
- [BlueZ Device D-Bus API](https://github.com/bluez/bluez/blob/master/doc/org.bluez.Device.rst)
- [Microsoft `SendInput`](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-sendinput)
- [Linux uinput documentation](https://www.kernel.org/doc/html/latest/input/uinput.html)
- [BlueBoard LED timestamp field report](https://forum.juce.com/t/irig-blueboard-midi-issue-and-potential-fix/29746)
