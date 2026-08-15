# iRig BlueBoard Macro Handler — Dev Branch Technical Summary

## Purpose

This document is the working brief for the `dev` branch of `iRigBlueBoard-Macro-Handler`. It preserves the project as a reusable, transport-agnostic macro handler while documenting the BlueBoard-specific BLE-MIDI adapter and the opt-in LED-feedback implementation.

## Confirmed hardware contract

Boot the board while holding **C** to enter BLE-MIDI mode 2. It transmits MIDI channel 1 control changes:

| Button | Press | Release |
|---|---|---|
| A | CC20, value 127 | CC20, value 0 |
| B | CC21, value 127 | CC21, value 0 |
| C | CC22, value 127 | CC22, value 0 |
| D | CC23, value 127 | CC23, value 0 |

BLE-MIDI endpoint:

```text
serviceUuid = 03b80e5a-ede8-4b33-a751-6ce34ec4c700
midiCharacteristicUuid = 7772e5db-3868-4112-a1a9-f2669d106bf3
```

The characteristic is bidirectional: notifications carry BlueBoard input and write-without-response carries host feedback.

## Current dev-branch design

```text
BlueBoard -> BLE transport -> BLE-MIDI decoder -> Router -> ActionDispatcher
                                              |                 |
                                              v                 v
                                         LED feedback       keyboard/UDP/launch
```

The boundaries are intentional:

- `client.py` owns scanning, connection, notification subscription, GATT writes, reconnects, metrics, and the BlueZ compatibility fallback.
- `ble_midi.py` decodes and encodes BLE-MIDI packets.
- `router.py` converts normalized MIDI events to press/release edges, applies cooldowns, and owns button state.
- `actions/` is cross-platform macro output.
- `LedFeedbackController` is separate from macros: it receives desired LED state while transport-specific GATT details remain in the client.

Keep the generic macro layer MIDI-independent. It should consume gestures and emit abstract actions; only the BlueBoard adapter knows CC20–23.

## Important dev-branch improvements

- Python package version is 0.3.0, Python 3.10+, with `bleak` as the BLE dependency and `evdev` as the Linux extra.
- The command application exposes `scan`, `run`, `replay`, `validate`, and `init-config`.
- Actions are dry-run by default; `--execute-actions` is required for keyboard, UDP, or launch side effects.
- Last successful device address is persisted, but discovery falls back to service/name matching if it changes.
- BLE writes are serialized through `BlueBoardClient.writeLock`.
- Linux setup now handles venv, system-wide `/opt` installation, and pipx per-user installation without violating Debian/Ubuntu PEP 668 protections.
- `runBlueBoard.sh` preflights `/dev/uinput` and `input` group membership before enabling keyboard actions.
- The Linux path recognizes an older-firmware/BlueZ defect where the advertised BLE-MIDI service is omitted from D-Bus discovery; it uses a narrow `gatttool` fallback only for that case.
- Update scripts refuse to fetch over uncommitted local changes and then fast-forward the expected branch before setup.

## Linux Mint validation plan

1. Clone the intended branch and inspect `git status` before running updater scripts.
2. Boot BlueBoard with C held; disconnect Android or any other active BLE client.
3. Run `./setupBlueBoard.sh` for a local venv. Prefer this during development.
4. For keyboard execution, run `./setupBlueBoard.sh --skip-system --add-input-group`, then log out and back in.
5. Run `./scanBlueBoard.sh --debug --scan-timeout 15`.
6. Run `./runBlueBoard.sh --debug` first; confirm scan, subscribe, connected, and CC20–23 logs.
7. Run `./runBlueBoard.sh --debug --execute-actions` only after dry-run confirmation.
8. If normal BlueZ discovery loops, retain debug logs and verify the documented `bluez-gatttool` fallback is selected. Do not manually pair or trust the pedal.
9. Validate all four press/release edges, forced board power cycles, and Ctrl+C cleanup.

Do not run the application permanently as root. `/dev/uinput` access is intentionally granted through the `input` group and a narrow udev rule.

## LED feedback: implemented opt-in feature

The `dev.button-backlights` branch exposes momentary feedback through
`blueboard run --led-feedback`. The flag remains opt-in until physical rapid-
press and reconnection validation is recorded. It is independent of
`--execute-actions`, so macro failures and dry-run mode do not suppress visual
feedback.

In mode C the per-switch LEDs are host controlled. Echo the button’s CC back on channel 1:

| Event | Outbound MIDI |
|---|---|
| A on/off | `B0 14 7F` / `B0 14 00` |
| B on/off | `B0 15 7F` / `B0 15 00` |
| C on/off | `B0 16 7F` / `B0 16 00` |
| D on/off | `B0 17 7F` / `B0 17 00` |

Values `>= 64` light the corresponding LED; values `< 64` clear it.

The packet-building primitive already exists:

```python
packet = encodeBleMidi(0xB0, bytes((20, 127)))
await client.writePacket(packet, response=False)
```

### Implemented shape

Create `LedFeedbackController` with a bounded `asyncio.Queue`. It accepts abstract requests such as `setLed(cc, isOn)` and owns packet encoding plus `client.writePacket`. Bind it to the active client only after connection succeeds; unbind on disconnect.

Router behavior on every accepted state change:

```text
CC20 press   -> Router records A=true  -> LedFeedbackController.setLed(20, true)
CC20 release -> Router records A=false -> LedFeedbackController.setLed(20, false)
```

LED feedback must mirror physical press/release even when a macro action fails. It must not be coupled to UDP, keyboard, or launch success.

On connect, clear A–D once to establish a known visual state. On disconnect, clear local feedback state without attempting writes; reinitialize after reconnect.

Do not create one async task per MIDI event. A single feedback worker preserves output ordering and prevents bursty presses from creating uncontrolled tasks.

## Validation required before enabling LEDs by default

Automated coverage now verifies encoding for every CC/state pair, one request
per accepted router edge, duplicate suppression, serialized writes, connection
initialization, reconnect rebinding, write-failure isolation, and the
interactive Linux compatibility session. The remaining gates require the
physical board:

- Hardware test: press and release A–D individually, then perform 100 rapid cycles per button.
- Hardware test: force a board power-off while a LED is on; reconnect and verify all LEDs initialize off.
- Linux test using both regular Bleak and the `gatttool` fallback when applicable.

## Development sequence

1. Complete Linux Mint dry-run and executed-action validation. Done.
2. Add LED feedback behind `--led-feedback`. Done.
3. Add complete unit coverage. Done; physical hardware evidence remains.
4. Make it default only after reconnection and rapid-press hardware tests pass.
5. Consider `1.0.0` only after both platform hardware records and the other release gates are complete.
6. Later, add a distinct persistent-state mode for Katana effect state. Do not confuse it with momentary press echo.

## References

- Repository dev branch: https://github.com/NotsoJharedtrollOx17/iRigBlueBoard-Macro-Handler/tree/dev
- BLE-MIDI specification: https://www.hangar42.nl/wp-content/uploads/2017/10/BLE-MIDI-spec.pdf
- BlueBoard mode-2 LED mapping: https://manualzz.com/doc/54441731/irig-blueboard-user-manual
- Bleak client API: https://bleak.readthedocs.io/en/latest/api/client.html
- BlueZ GATT API: https://github.com/bluez/bluez/blob/master/doc/gatt-api.txt
