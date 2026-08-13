# Python Implementation Roadmap

## Implementation update (version 0.2.0)

The primary roadmap items are now implemented in the installable
`blueboard_macro_handler` package: typed and backward-compatible configuration,
arbitrary Windows/Linux keyboard macros, dry-run and packet replay, an action
dispatcher, explicit connection states, clean shutdown and input cleanup,
last-device persistence with discovery fallback, mocked BLE lifecycle tests,
cooldowns, JSON logging, run summaries, outbound packet encoding/write
primitives, console entry points, and wheel packaging.

LED feedback remains intentionally disabled until its device-specific outbound
message semantics are confirmed on hardware. Linux BLE and uinput behavior
also require final validation on a Linux host with the physical BlueBoard.

## Current status

The Windows Python milestone is operational:

- BLE discovery works through Bleak and Windows WinRT.
- The BlueBoard BLE-MIDI characteristic is discovered and subscribed.
- BLE-MIDI notifications are decoded into normalized MIDI events.
- CC20–CC23 button routing works.
- Windows keyboard macros execute through the native `SendInput` API.
- C and D remain intentionally unmapped by default.
- Reconnect attempts and macro failures are logged without terminating BLE processing.

The next Python tasks should improve reliability, configurability, testing, and
observability. Linux transport and keyboard support should reuse the shared
decoder, router, configuration, and tests instead of duplicating the design.

## Recommended roadmap

### 1. Improve configuration and action management

Validate `python/config/blueboard.json` at startup and move from action-name
conventions toward explicit action definitions. A future binding could look
like:

```json
{
  "cc": 20,
  "edge": "press",
  "action": {
    "type": "keyboard",
    "keys": ["CTRL", "SHIFT", "R"]
  }
}
```

Potential action types include arbitrary keyboard combinations, single-key
presses, key holds/releases, shell commands, application launches, UDP/OSC
messages, and log-only actions. Keep C and D unmapped unless explicitly
configured.

### 2. Define an action interface

The router currently calls an action backend dynamically. Introduce a small
protocol with `invoke()` and `releaseAll()` methods, then provide Windows,
Linux, dry-run, and test implementations. This keeps platform code out of the
router and makes failures easier to test.

### 3. Add dry-run and replay modes

Add a mode that parses and routes events without sending real input:

```powershell
.\runBlueBoard.ps1 --dry-run
```

Also support replaying recorded MIDI fixtures without hardware. This enables
mapping tests without accidentally triggering shortcuts.

### 4. Expand automated tests

Add tests for every configured binding, release-only bindings, duplicate
events, unknown CC values, repeated presses, backend exceptions, reconnect
cleanup, action dispatch, invalid configuration, and mocked Bleak discovery,
subscription, and disconnect behavior.

### 5. Tighten BLE-MIDI decoding

The decoder handles the observed BlueBoard packets, running status, multiple
messages, malformed input, and split messages. Further work should make BLE-
MIDI timestamps standards-complete, preserve timestamp context, handle system
messages and SysEx safely, and maintain shared fixtures for Python and C++.

### 6. Improve connection lifecycle handling

Represent the connection states explicitly:

```text
scanning -> connecting -> discovering -> subscribing -> connected
    ^                                               |
    +---------------- backoff <--------------------+
```

Add separate scan, connection, discovery, and subscription errors; explicit
`stop_notify`; clean Ctrl+C shutdown; action-backend cleanup; stable-device
address persistence; and optional last-known-device prioritization.

### 7. Add structured logging and summaries

Offer optional JSON logs containing monotonic timestamp, connection state,
device address, RSSI, packet bytes, decoded MIDI event, action name, action
result, and reconnect attempt. Print a shutdown summary with connection time,
packets, events, actions, failures, and reconnects.

### 8. Add keyboard-macro safety controls

Before adding more side effects, implement an explicit startup confirmation for
`--execute-actions`, a panic disable command/key, action rate limits, reconnect
replay protection, optional foreground-window logging, and configurable
cooldowns.

### 9. Add outbound BLE-MIDI support

Implement serialized GATT writes, BLE-MIDI packet encoding, a `writePacket()`
client method, configurable LED feedback, and outbound packet tests.

### 10. Package the Python application

Once behavior stabilizes, add `pyproject.toml`, a package namespace instead of
`sys.path` manipulation, console entry points such as `blueboard scan` and
`blueboard run`, typed configuration models, a version, and a release/build
script.

### 11. Keep documentation synchronized

The README should state that keyboard injection is available when
`--execute-actions` is supplied, rather than describing the implementation as
diagnostic-only.

## Suggested implementation order

1. Dry-run and replay mode.
2. Typed action configuration.
3. Action protocol and dispatcher.
4. Connection lifecycle and shutdown cleanup.
5. Mocked BLE-client tests.
6. Safety controls.
7. Outbound LED feedback.
8. Python packaging.

Linux should reuse the shared components. Only the BLE transport and keyboard
backend should be platform-specific.
