# Architecture and extension guide

## Purpose

This document is the implementation map for maintainers and AI agents working
on `iRigBlueBoard-Macro-Handler`. It records the current runtime boundaries,
the hardware contract that the code relies on, the invariants protected by the
tests, and the safest places to extend the project.

The current application is a Python 3.10+ package. An early project brief also
proposed a C++17 implementation, but no C++ runtime is present in this
repository. Treat those native-platform ideas as a possible future port, not
as an implemented or supported path.

## Sources of truth

Use the following order when code and prose disagree:

1. `python/src/blueboard_macro_handler/` is the maintained runtime.
2. `python/tests/` defines the automated behavioral contract.
3. `python/config/blueboard.json` is the repository launcher configuration.
4. `python/src/blueboard_macro_handler/default_config.json` is the installed
   CLI default.
5. Root setup, scan, run, and update scripts define installation behavior.
6. The README is the user-facing operational summary.
7. The three files in `agent-docs/` preserve design reasoning, physical test
   evidence, limitations, and future work.

The adjacent camelCase modules directly under `python/src` are retained
milestone implementations. Some legacy tests still exercise them, but new
features belong in the package namespace unless a deliberate cleanup migrates
or removes the old coverage.

## Confirmed BlueBoard contract

The supported physical profile is the iRig BlueBoard in mode 2. Select that
mode by holding **C** while powering on the pedal. The tested input mapping is:

| Button | MIDI press | MIDI release | Internal controller |
|---|---|---|---|
| A | `B0 14 7F` | `B0 14 00` | CC20 |
| B | `B0 15 7F` | `B0 15 00` | CC21 |
| C | `B0 16 7F` | `B0 16 00` | CC22 |
| D | `B0 17 7F` | `B0 17 00` | CC23 |

`B0` is Control Change on MIDI channel 1. The router considers values 64-127
pressed and values 0-63 released. Configuration uses one-based channels
(`1`-`16`), while decoded `MidiEvent.channel` values are zero-based
(`0`-`15`).

The BLE-MIDI endpoint is:

```text
service UUID        03b80e5a-ede8-4b33-a751-6ce34ec4c700
characteristic UUID 7772e5db-3868-4112-a1a9-f2669d106bf3
```

Notifications carry input packets. The same characteristic accepts outbound
BLE-MIDI packets for momentary LED feedback on the tested board.

## Runtime data flow

```text
advertisement / saved address
            |
            v
      BlueBoardClient
  Bleak first; Linux-only
  compatibility fallback
            |
            v
      notification queue
            |
            v
       BleMidiDecoder
            |
            v
          Router
       /          \
      v            v
ActionDispatcher  LedFeedbackController
      |            |
      v            v
keyboard / UDP /  serialized BLE-MIDI writes
launch / log
```

The BLE callback only copies bytes into a bounded queue. Decoding, routing,
logging, action dispatch, and feedback requests happen outside the backend
notification callback.

## Repository map

| Path | Responsibility |
|---|---|
| `python/src/blueboard_macro_handler/cli.py` | CLI grammar, command dispatch, welcome banner, summaries, and exit codes |
| `client.py` | Scanning, connection lifecycle, Bleak subscription, reconnects, state persistence, GATT writes, and Linux fallback |
| `ble_midi.py` | Stateful channel-voice decoding and outbound BLE-MIDI framing |
| `router.py` | Edge detection, duplicate suppression, cooldowns, action invocation, and LED requests |
| `led_feedback.py` | Feedback state, coalescing queue, pacing, initialization, retries, and packet encoding |
| `config.py` | JSON validation and normalized immutable configuration models |
| `models.py` | MIDI events, connection states, and run metrics |
| `state.py` | Platform-appropriate last-address persistence |
| `logging_utils.py` | Human wall-clock and JSON log formatting |
| `actions/dispatcher.py` | Dry-run boundary and typed action dispatch |
| `actions/windows.py` | Native Windows `SendInput` keyboard backend |
| `actions/linux.py` | `python-evdev` `/dev/uinput` keyboard backend |
| `python/tests/` | Packaged and retained-milestone behavioral coverage |
| root scripts | Reproducible setup, scan, run, and production-branch update workflows |

## Command layer

The installed entry point is `blueboard_macro_handler.cli:main`. It exposes:

| Command | Behavior |
|---|---|
| `scan` | Discover devices by configured name substring or BLE-MIDI service |
| `run` | Connect, decode, route, reconnect, and optionally emit side effects |
| `replay FILE` | Decode fixture packets without BLE hardware |
| `validate` | Load, validate, normalize, and print configuration |
| `init-config` | Copy the packaged default configuration to an editable path |

`run` and `replay` default to dry-run action dispatch. Only
`--execute-actions` permits keyboard, UDP, or program-launch side effects.
`--led-feedback` is a separate opt-in outbound BLE side effect. It remains
active in action dry-run mode because it is driven by accepted button edges,
not by action success.

Expected top-level exit behavior is:

- `0` for a completed command;
- `2` for configuration, argument-dependent, replay, or runtime setup errors
  caught by the CLI;
- `130` when Ctrl+C reaches the CLI shutdown handler.

## Connection lifecycle

The client exposes these states in logs:

```text
scanning -> connecting -> discovering -> subscribing -> connected
    ^                                                     |
    +-------------------- backoff <-----------------------+
                                      |
                                      v
                                   stopped
```

The normal transport is Bleak on every platform:

1. Scan for advertisements matching the configured name or service UUID.
2. Prefer the requested or last successful address when it is present.
3. Fall back to the first matching advertisement when that address is absent.
4. Connect with optional pairing and a backend timeout.
5. Confirm the BLE-MIDI service and characteristic.
6. Bind LED feedback when enabled.
7. Start notifications and consume them through a queue.
8. Wait for either stop or disconnect.
9. Unbind feedback, stop notifications when possible, reset decoder state,
   release router/action state, and reconnect with bounded backoff.

Backoff starts at one second, doubles after each unsuccessful cycle, and caps
at 20 seconds. A successful Bleak connection resets it. The last successful
address is written atomically to a platform-appropriate state file:

- Windows: `%LOCALAPPDATA%/blueboard-macro-handler/state.json`;
- Linux: `$XDG_STATE_HOME/blueboard-macro-handler/state.json`, or the matching
  path under `~/.local/state` when the variable is absent.

The Linux `gatttool` path is not a second general transport. It is selected
only after a successful Linux Bleak connection omits the expected advertised
service. Its hardware-specific evidence and handle contract are documented in
`platform-operations-and-hardware-findings.md`.

## BLE-MIDI decoder contract

`BleMidiDecoder` is stateful across notifications and is reset on disconnect.
The current implementation:

- rejects packets without a valid high-bit BLE-MIDI header;
- skips timestamp bytes while parsing channel-voice messages;
- supports running status;
- supports multiple messages in one notification;
- retains partial message data across notification boundaries;
- emits Control Change, Note On, Note Off, Program Change, and Pitch Bend;
- treats Note On with velocity zero as Note Off;
- ignores unsupported status bytes without terminating the client.

The decoder records local monotonic receipt time. It does not reconstruct the
remote BLE-MIDI timestamp, and it does not yet provide complete System Common,
System Real-Time, SysEx, or channel-pressure semantics. Do not describe it as a
complete BLE-MIDI implementation.

`encodeBleMidi()` validates the status and seven-bit data values, then emits a
13-bit timestamp header. Callers may supply a fixed timestamp. LED feedback
does so deliberately because the physical BlueBoard was stable with a zero
timestamp header (`80 80`).

## Router invariants

The router owns normalized button state independently for every decoded
channel/controller pair. For Control Change events it:

1. derives pressed state from the value threshold;
2. stores the new state;
3. suppresses duplicate press or release values;
4. emits LED feedback only for channel 1 and CC20-CC23;
5. identifies bindings matching controller, one-based configured channel, and
   edge;
6. logs the physical button and normalized action description;
7. skips `null` actions;
8. applies per-binding monotonic cooldowns;
9. invokes actions behind an exception boundary.

Action exceptions increment `actionFailures`, are logged with a traceback, and
do not escape into BLE notification consumption. On disconnect or shutdown,
`releaseAll()` clears the remembered button states and asks the active keyboard
backend to release managed input state.

Do not couple LED state to action dispatch. A failed, suppressed, unmapped, or
dry-run action must not prevent an accepted physical edge from updating
momentary feedback.

## Configuration model

Configuration is JSON with a `device` object and a `bindings` array:

```json
{
  "device": {
    "name": "BlueBoard",
    "scanTimeout": 8.0,
    "pair": false
  },
  "bindings": [
    {
      "cc": 20,
      "channel": 1,
      "edge": "press",
      "cooldownMs": 250,
      "action": {
        "type": "keyboard",
        "keys": ["CTRL", "SHIFT", "R"]
      }
    }
  ]
}
```

Validation boundaries are:

- `cc`: integer `0`-`127`;
- `channel`: integer `1`-`16`;
- `edge`: `press` or `release`;
- `cooldownMs`: non-negative integer;
- `scanTimeout`: positive number;
- `pair`: boolean;
- `action`: a typed action, a compatible legacy string, or JSON `null`.

Typed actions are:

| Type | Required data | Runtime behavior |
|---|---|---|
| `keyboard` | non-empty `keys` string array | Emit a press sequence and reverse-order release sequence |
| `log` | optional `message` | Log only, regardless of action execution mode |
| `udp` | host, port `1`-`65535`, optional message | Send one UTF-8 datagram |
| `launch` | program, optional string argument array | Start with `subprocess.Popen([...], shell=False)` |

JSON `null` means intentionally unmapped; it is not a typed action named
`null`. The legacy strings `ctrlShiftR` and `altTab` normalize to keyboard
actions. Other strings become log actions so older descriptive configurations
remain harmless.

The repository and packaged defaults must remain behaviorally aligned. If one
changes, update the other and add or adjust configuration tests.

## Action boundary

`ActionDispatcher` is the only switch between observation and operating-system
side effects. It logs every normalized action. When `execute=False`, keyboard,
UDP, and launch actions return without performing work. A log action records
its message but is not counted as an executed side effect.

Windows keyboard behavior is built on the complete native `INPUT` union. The
mouse member is intentionally present because it controls the 64-bit structure
size; removing it recreates the historical `SendInput` argument failure.
Keyboard names cover letters, digits, navigation keys, modifiers, and F1-F24.

Linux uses `evdev.UInput` with a declared key capability set. Creating the
virtual device requires a usable `/dev/uinput` and active-session permission.
These are platform setup concerns, not reasons to weaken the dispatcher's
dry-run boundary.

## LED feedback controller

`LedFeedbackController` receives abstract `(cc, isOn)` requests and owns
BlueBoard-specific packet encoding. Its invariants are:

- accept only CC20-CC23;
- remain inert while unbound;
- create one worker per active connection;
- clear A-D once and flush those writes when bound;
- keep only one queued entry per controller and use the latest desired state;
- serialize transport writes through the client's write lock;
- use the fixed zero timestamp for BlueBoard LED packets;
- pace writes at 125 ms by default;
- schedule at most one 200 ms off retry per released button;
- cancel that retry if the same button is pressed again;
- emit no idle reconciliation traffic;
- cancel the worker and retry tasks without writing after disconnect.

The queue is bounded at 1,024 entries, although controller coalescing normally
limits pending feedback to four entries. Queue-full drops, local write
failures, and successful host writes are counted separately. A transport
exception requeues the latest desired controller state; the physical
off-retry policy is distinct from this local error recovery.

If the characteristic advertises acknowledged `write`, the controller asks
the transport for a response. If it only advertises
`write-without-response`, successful completion means the host stack accepted
the command, not that the pedal changed its light. No supported readback exists.

## Logging and metrics

Human logs use local wall-clock time with millisecond precision. JSON logs
include a monotonic timestamp, severity, logger, message, and formatted
exception when present. `--log-file` mirrors the selected format to UTF-8.

`RunMetrics` tracks:

- runtime and connected seconds;
- received packets and decoded events;
- executed actions and action failures;
- successful LED writes, LED failures, and feedback queue drops;
- reconnect cycles.

Counters describe host behavior. In particular, `ledFeedbackWrites` is not
proof of physical LED acknowledgement on a write-without-response device.

## Safe extension recipes

### Add a new action type

1. Add fields to `ActionSpec` only when the action needs new data.
2. Extend `parseAction()` with strict validation and safe defaults.
3. Extend `configAsDict()` so `validate` shows the normalized representation.
4. Add a concise description in `router.actionDescription()`.
5. Implement execution in `ActionDispatcher.invoke()` behind `self.execute`.
6. Keep shell invocation disabled unless a future design explicitly defines
   and secures it.
7. Add configuration, dry-run, execution, failure, and logging tests.

### Add a new keyboard key

1. Add the Windows virtual-key code in `actions/windows.py`.
2. Add the Linux evdev code in `actions/linux.py`.
3. Test normalization and native event order on both platforms.
4. Do not accept a key name on only one supported platform without documenting
   the platform restriction.

### Add a new board profile

Do not scatter new controller numbers or handles through the current modules.
First introduce an explicit profile model containing service/characteristic
UUIDs, button-to-controller mapping, feedback policy, and any compatibility
handles. Preserve the current profile as the default and validate profile data
before scanning or writing.

### Replace the Linux compatibility backend

Keep Bleak as the normal path. A replacement should be selected only for the
known service-omission condition, feed bytes into `handlePacket()`, use
`writePacket()` serialization, respond promptly to stop requests, expose
disconnects, and retain the existing router/action/metrics pipeline.

### Add persistent effect-state LEDs

Create a new semantic mode. Momentary feedback currently represents physical
press state and is intentionally independent of macros. Do not overload it
with application or amplifier state without an explicit source of truth and a
reconnection synchronization policy.

## Test map

The current suite covers two layers:

- retained milestone modules: decoder, stateful routing, and initial Windows
  action behavior;
- packaged runtime: configuration, CLI, action dispatch, native ABI, BLE
  lifecycle, address fallback, serialized writes, Linux fallback parsing and
  process behavior, router invariants, and LED feedback.

Run from the repository root:

```powershell
.\python\.venv\Scripts\python.exe -m unittest discover -s python\tests -p "test*.py" -v
.\python\.venv\Scripts\python.exe -m ruff check python/src/blueboard_macro_handler python/tests
```

The 2026-08-15 documentation audit passed 59 tests and Ruff on Windows. That
result does not replace physical validation or a future Windows/Linux CI
matrix.

For changes that touch hardware behavior, also exercise:

1. dry-run scanning and all A-D press/release logs;
2. executed A/B default macros in a harmless foreground application;
3. C/D remaining unmapped by default;
4. rapid LED press/release cycles;
5. disconnect while a button is down or an LED is on;
6. reconnect initialization and Ctrl+C cleanup;
7. the Linux compatibility backend when the service-omission condition is
   available on the test machine.

## Agent working rules

- Preserve Python 3.10 compatibility and the established camelCase naming
  style used by project-owned identifiers.
- Keep BLE callbacks short and actions behind an exception boundary.
- Keep operating-system and outbound-BLE side effects opt-in.
- Preserve C and D as harmless unmapped defaults.
- Do not weaken `/dev/uinput` permissions or recommend permanent root use.
- Do not generalize the fixed Linux handles beyond the tested board profile.
- Do not interpret a write-without-response completion as hardware
  acknowledgement.
- Update both default configurations when changing defaults.
- Add tests in the same change as a new parser, routing, action, lifecycle, or
  feedback behavior.
- Update the README and the relevant detailed document when an operational
  contract changes.
- Record physical observations separately from inferences and automated-test
  results.

## Deferred native implementation

If a native port becomes worthwhile, retain the behavioral boundaries rather
than translating the Python files line-for-line. A C++17 core should keep MIDI
events, decoding, routing, and reconnect policy independent of C++/WinRT,
BlueZ D-Bus, `SendInput`, `/dev/uinput`, ALSA, or socket headers. Windows can
use C++/WinRT GATT APIs and `SendInput`; Linux should prefer BlueZ D-Bus and
uinput rather than raw HCI or a kernel driver. Shared packet fixtures should
produce equivalent normalized events in both implementations.

Until that port exists with its own build and tests, describe this repository
as the Python implementation only.
