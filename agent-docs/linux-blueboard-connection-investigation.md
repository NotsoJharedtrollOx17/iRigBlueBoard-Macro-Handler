# Linux BlueBoard connection investigation

Date: 2026-08-13

## Executive result

Linux Mint was not failing to turn Bluetooth on, and the pedal was not being
paired as an ordinary desktop Bluetooth device. The application connected to
the iRig BlueBoard successfully, but BlueZ omitted the board's final
BLE-MIDI GATT service from its D-Bus service model. The client then treated the
missing service as a connection failure, exited the Bleak context (which
disconnects the board), and retried with exponential backoff. That produced
the visible connect/disconnect loop.

The board's GATT table is valid at the ATT level. The system's already
installed `gatttool` can see and subscribe to the omitted service, so the
Linux client now has a narrowly scoped compatibility path:

1. Use Bleak normally on Windows and Linux.
2. If Linux connects but the expected BLE-MIDI service is absent from Bleak's
   service collection, invoke `gatttool` from the existing `bluez` package.
3. Subscribe to the board's MIDI value characteristic and parse notifications
   into the existing decoder/router pipeline.
4. Do not pair, bond, trust, or alter the normal BlueZ device state.

No new Python dependency was added.

## Machine evidence

Observed on the Linux Mint test machine:

- BlueZ: `5.72`
- Kernel: `7.0.0-28-generic`
- Bluetooth controller: Realtek `hci0`, address `0C:96:E6:CF:64:4C`
- BlueBoard address: `BC:6A:29:34:DD:76`
- BlueBoard advertised name: `iRig BlueBoard`
- Advertised BLE-MIDI service: `03b80e5a-ede8-4b33-a751-6ce34ec4c700`
- MIDI characteristic: `7772e5db-3868-4112-a1a9-f2669d106bf3`

`bluetoothctl devices Paired` initially listed only the MX Keys. The
BlueBoard was not paired, bonded, or trusted. The Bluetooth service was active
and the adapter was powered.

BlueZ emitted repeated:

```text
No matching connection for device
```

These messages occurred on the same cadence as the application's retry loop.
They were a symptom of the client repeatedly closing failed Bleak sessions,
not evidence that desktop Bluetooth was independently claiming the board.

## Application trace before the fix

The application discovered and connected to the board:

```text
discovered name=iRig BlueBoard address=BC:6A:29:34:DD:76 RSSI=-36
state=connecting pair=False
state=discovering
```

BlueZ reported `ServicesResolved=True`, but the D-Bus service objects exposed
only Generic Access, Generic Attribute, Device Information, and Battery
Service. The BLE-MIDI service was absent. The old code then raised:

```text
RuntimeError('BLE-MIDI service was not discovered')
```

The `async with BleakClient(...)` scope disconnected the device, and the
outer reconnect loop began again.

## Low-level GATT evidence

The BlueZ-bundled low-level tool saw the complete primary-service table:

```text
attr handle = 0x0001, end grp handle = 0x000b uuid: 00001800-0000-1000-8000-00805f9b34fb
attr handle = 0x000c, end grp handle = 0x000f uuid: 00001801-0000-1000-8000-00805f9b34fb
attr handle = 0x0010, end grp handle = 0x001a uuid: 0000180a-0000-1000-8000-00805f9b34fb
attr handle = 0x001b, end grp handle = 0x001f uuid: 0000180f-0000-1000-8000-00805f9b34fb
attr handle = 0x0020, end grp handle = 0xffff uuid: 03b80e5a-ede8-4b33-a751-6ce34ec4c700
```

The BLE-MIDI characteristic and its Client Characteristic Configuration
descriptor are:

```text
handle = 0x0022, uuid = 7772e5db-3868-4112-a1a9-f2669d106bf3
handle = 0x0023, uuid = 00002902-0000-1000-8000-00805f9b34fb
```

Subscribing through the existing BlueZ tool succeeded:

```text
Characteristic value was written successfully
```

This isolates the fault to the BlueZ D-Bus service exposure path rather than
the controller, radio, board advertisement, or BLE-MIDI UUID constants.

## Pairing experiment

The existing `--pair` option was tested once. It did not produce a bond; the
pairing operation remained pending and temporarily marked the board trusted.
That temporary state was explicitly reverted with `bluetoothctl untrust` and
`bluetoothctl disconnect`. Pairing is therefore not used as an automatic fix.

## Implemented compatibility path

`python/src/blueboard_macro_handler/client.py` now contains:

- `BluezMidiServiceOmitted`, raised only on Linux when the expected service is
  absent after a successful Bleak connection.
- `parseGatttoolNotification`, a pure parser for the tool's notification
  lines.
- `runBluezGatttoolFallback`, which starts:

  ```text
  gatttool -b <address> --char-write-req --handle=0x0023 --value=0100 --listen
  ```

- Existing MIDI decoding, event routing, metrics, state-address persistence,
  and disconnect cleanup are reused.

The fallback is intentionally hardware-specific. The iRig BlueBoard firmware
tested here uses the fixed handles `0x0022` and `0x0023`; if a future hardware
revision changes its attribute layout, the handles must be discovered or
configured rather than assumed.

## Validation

The bounded live test reached:

```text
state=subscribing backend=bluez-gatttool characteristic=0x0022
state=connected address=BC:6A:29:34:DD:76 backend=bluez-gatttool
```

It remained connected for the rest of the test window without the previous
reconnect cycle. No physical pedal press was made during that run, so the
remaining hardware validation is to press A-D and confirm decoded MIDI events.

Targeted tests passed: 11/11 (`testPackageClient.py` and `testBleMidi.py`).
The full suite has three unrelated Windows-only failures when run on Linux:
two calls to Windows-specific `ctypes` APIs and one Windows structure-size
assertion.

The package metadata and runtime version are aligned to `1.0.0` in
`pyproject.toml` and `python/src/blueboard_macro_handler/__init__.py`.

## Operational test procedure

Run the existing launcher in dry-run mode:

```bash
./runBlueBoard.sh --debug --dry-run
```

Expected Linux fallback log:

```text
BlueZ D-Bus omitted the advertised BLE-MIDI service; using the BlueZ gatttool compatibility path
state=connected ... backend=bluez-gatttool
```

Press each pedal button and verify MIDI/event logs. Only after that succeeds
should side effects be enabled:

```bash
./runBlueBoard.sh --debug --execute-actions
```

Do not manually pair or trust the pedal for this workaround. Ensure no other
BLE client (phone, DAW, or Bluetooth utility) is connected to the board.

## References

- [Bleak Linux backend documentation](https://bleak.readthedocs.io/en/stable/backends/linux.html)
- [BleakClient service filtering and pairing documentation](https://bleak.readthedocs.io/en/latest/api/client.html)
- [BlueZ issue: service not detected for a specific device](https://github.com/bluez/bluez/issues/438)
- [BlueZ `Device1` API, including `ServicesResolved`](https://github.com/bluez/bluez/blob/master/doc/org.bluez.Device.rst)
- [Bleak issue: BlueZ service-object/cache failures](https://github.com/hbldh/bleak/issues/1435)
