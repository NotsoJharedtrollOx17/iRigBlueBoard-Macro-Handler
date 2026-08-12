# iRig BlueBoard MIDI Router — Codex Implementation Brief

## 1. Objective

Build a low-latency, reconnecting router for the iRig BlueBoard that:

1. Connects directly to the board over BLE-MIDI.
2. Decodes incoming MIDI messages.
3. Converts CC20–CC23 into configurable actions.
4. Supports Windows and Linux Mint.
5. Provides a C++17 implementation with native platform APIs.
6. Provides a Python 3.10+ reference/prototype implementation.
7. Optionally sends MIDI back to the BlueBoard for LED feedback.

The application must remain in user space. Do not write a kernel driver or replace the operating-system Bluetooth stack.

## 2. Confirmed device behavior

The tested BlueBoard works in BLE-MIDI mode when button C is held during power-up. The Android tests established that:

- the device advertises and connects;
- Android pairing succeeds;
- the MIDI BLE connector receives events;
- events continue with the screen locked;
- mode C emits standard MIDI Control Change messages;
- the current practical mappings are:

| Button | MIDI message | Meaning |
|---|---|---|
| A | `B0 14 7F` / `B0 14 00` | CC20 press/release |
| B | `B0 15 7F` / `B0 15 00` | CC21 press/release |
| C | `B0 16 7F` / `B0 16 00` | CC22 press/release |
| D | `B0 17 7F` / `B0 17 00` | CC23 press/release |

`B0` means Control Change on MIDI channel 1. Values 127 and 0 represent press and release. The router must not assume that every future message is one of these CCs; it should ignore unsupported messages safely.

The documented BLE-MIDI service and characteristic are:

```text
serviceUuid:        03b80e5a-ede8-4b33-a751-6ce34ec4c700
midiCharacteristic: 7772e5db-3868-4112-a1a9-f2669d106bf3
```

The characteristic uses notifications for incoming data and writes for outgoing data. The board's startup-mode quirk is an operational requirement, not a reason to reverse-engineer the radio firmware.

## 3. Architecture

```text
BLE-MIDI notification
        |
        v
platform BLE client
        |
        v
BLE-MIDI decoder
        |
        v
normalized MidiEvent
        |
        v
router / state machine
   |         |          |
   v         v          v
keyboard   OSC/UDP    MIDI output
actions               and LEDs
```

The core must not include Windows, BlueZ, WinRT, ALSA, or uinput headers. Platform code supplies interfaces such as `BleClient`, `KeyboardOutput`, `MidiOutput`, and `DatagramOutput`.

Suggested tree:

```text
blueboardRouter/
  CMakeLists.txt
  include/
    bleMidiDecoder.hpp
    midiEvent.hpp
    router.hpp
    reconnectController.hpp
  src/
    bleMidiDecoder.cpp
    router.cpp
    reconnectController.cpp
    main.cpp
    platform/windows/
      winBleClient.cpp
      winKeyboardOutput.cpp
      winMidiOutput.cpp
    platform/linux/
      bluezBleClient.cpp
      uinputKeyboardOutput.cpp
      alsaMidiOutput.cpp
  python/
    bleMidi.py
    blueboardClient.py
    router.py
    actions.py
    main.py
  tests/
    bleMidiDecoderTests.cpp
    testBleMidi.py
  config/
    blueboard.toml
```

## 4. Normalized event model

Use one representation in both languages:

```text
MidiEvent {
  type: controlChange | noteOn | noteOff | other
  channel: 0..15
  data1: 0..127
  data2: 0..127
  timestamp: monotonic time
}
```

The router should derive button edges from values:

```text
value >= 64  -> pressed
value < 64   -> released
```

For macro bindings, invoke the action on `pressed` by default. Releases must still update internal state so that reconnects cannot leave keys or notes logically stuck.

## 5. BLE-MIDI parsing requirements

BLE-MIDI is not identical to a raw MIDI byte stream. Each notification contains BLE-MIDI timestamp information, and a notification can contain multiple MIDI messages. The decoder must:

- validate the packet header;
- consume timestamp bytes before messages;
- recognize MIDI status bytes;
- support running status;
- support multiple messages in one packet;
- retain incomplete message state across notifications if needed;
- ignore malformed bytes without crashing;
- eventually support Note On, Note Off, CC, Program Change, Pitch Bend, and SysEx;
- retain only the subset needed by the BlueBoard router initially.

Do not hard-code the sample packet shape `80 80 B0 14 7F` as the only valid shape. It is a useful unit-test fixture, not a complete protocol implementation.

## 6. C++17 core skeleton

```cpp
// midiEvent.hpp
#pragma once

#include <cstdint>
#include <chrono>

enum class MidiMessageType {
    controlChange,
    noteOn,
    noteOff,
    programChange,
    pitchBend,
    system,
    unknown
};

struct MidiEvent {
    MidiMessageType type = MidiMessageType::unknown;
    std::uint8_t channel = 0;
    std::uint8_t data1 = 0;
    std::uint8_t data2 = 0;
    std::chrono::steady_clock::time_point receivedAt{};
};
```

```cpp
// bleMidiDecoder.hpp
#pragma once

#include "midiEvent.hpp"
#include <cstdint>
#include <functional>
#include <vector>

class BleMidiDecoder {
public:
    using EventHandler = std::function<void(const MidiEvent&)>;

    explicit BleMidiDecoder(EventHandler eventHandler);
    void parsePacket(const std::vector<std::uint8_t>& packet);
    void reset();

private:
    EventHandler eventHandler;
    std::uint8_t runningStatus = 0;
    std::vector<std::uint8_t> pendingData;
};
```

The implementation should use a small state machine. Every decoded event should be emitted with `std::chrono::steady_clock::now()`. Keep timestamp interpretation separate from event arrival time; the latter is sufficient for macro routing, while BLE timestamp reconstruction can be added for diagnostics.

```cpp
// router.hpp
#pragma once

#include "midiEvent.hpp"
#include <functional>

class Router {
public:
    using Action = std::function<void(const MidiEvent&)>;

    explicit Router(Action action);
    void handleEvent(const MidiEvent& event);
    void releaseAll();

private:
    Action action;
    bool buttonState[4] = {false, false, false, false};
};
```

The core C++ build target is C++17. Avoid `std::span`, which is C++20. Use `const std::vector<std::uint8_t>&`, pointer-plus-length, or a small byte-view type.

## 7. Windows implementation

Use C++/WinRT and the Windows SDK:

- scan: `BluetoothLEAdvertisementWatcher`;
- connect: `BluetoothLEDevice::FromBluetoothAddressAsync`;
- discover: `GetGattServicesAsync` and `GetCharacteristicsForUuidAsync`;
- subscribe: register `GattCharacteristic::ValueChanged`, then write the CCCD with `Notify`;
- keyboard macros: `SendInput`;
- UDP: Winsock;
- optional MIDI output: Windows MIDI Services or WinMM, behind an interface.

Keep strong references to the device, service, characteristic, and event-revoker. Losing the characteristic object or event registration can stop notifications. The BLE client should expose callbacks such as:

```cpp
class BleClient {
public:
    virtual ~BleClient() = default;
    virtual bool connect() = 0;
    virtual void disconnect() = 0;
    virtual bool writePacket(const std::vector<std::uint8_t>& packet) = 0;
};
```

`SendInput` example:

```cpp
void sendCtrlShiftR() {
    INPUT inputs[6]{};
    WORD keys[3] = {VK_CONTROL, VK_SHIFT, 'R'};

    for (int index = 0; index < 3; ++index) {
        inputs[index].type = INPUT_KEYBOARD;
        inputs[index].ki.wVk = keys[index];
    }

    for (int index = 0; index < 3; ++index) {
        inputs[index + 3].type = INPUT_KEYBOARD;
        inputs[index + 3].ki.wVk = keys[2 - index];
        inputs[index + 3].ki.dwFlags = KEYEVENTF_KEYUP;
    }

    SendInput(6, inputs, sizeof(INPUT));
}
```

Limitations: `SendInput` cannot cross Windows integrity levels. If the destination application is elevated, the router must run at a compatible integrity level.

## 8. Linux Mint implementation

Use BlueZ through D-Bus rather than raw HCI sockets:

- scan/connect through `org.bluez.Device1`;
- locate the remote characteristic exposed through the BlueZ object hierarchy;
- call `org.bluez.GattCharacteristic1.StartNotify`;
- consume the characteristic's `Value` property changes;
- write outbound packets with `WriteValue` and suitable options;
- keyboard injection: `/dev/uinput`;
- MIDI: ALSA sequencer API;
- UDP: POSIX sockets.

The application should not assume fixed object paths. Discover them through `org.freedesktop.DBus.ObjectManager.GetManagedObjects`, then match UUID properties.

Linux setup is likely to require:

```bash
sudo apt install bluez libdbus-1-dev libasound2-dev
```

For `/dev/uinput`, configure a narrowly scoped udev rule or group permission. The daemon should not run permanently as root merely to inject keys.

## 9. Python 3.10+ reference implementation

The Python version is the behavioral reference and diagnostic tool. Use `bleak` for native BLE access and the standard library for routing, logging, configuration, and UDP. Optional packages are `python-osc` and `mido`/`python-rtmidi`.

```python
# bleMidi.py
from dataclasses import dataclass
from enum import Enum
from time import monotonic


class MidiMessageType(Enum):
    controlChange = "controlChange"
    noteOn = "noteOn"
    noteOff = "noteOff"
    unknown = "unknown"


@dataclass(frozen=True)
class MidiEvent:
    messageType: MidiMessageType
    channel: int
    data1: int
    data2: int
    receivedAt: float


def decodeBleMidi(packet: bytes) -> list[MidiEvent]:
    """Decode the BlueBoard's BLE-MIDI notifications into MIDI events."""
    events: list[MidiEvent] = []
    if not packet or packet[0] & 0x80 == 0:
        return events

    index = 1
    runningStatus: int | None = None

    while index < len(packet):
        # A timestamp header precedes each MIDI message in the BLE-MIDI packet.
        if packet[index] & 0x80:
            index += 1
        if index >= len(packet):
            break

        status = packet[index]
        if status & 0x80:
            index += 1
            runningStatus = status
        elif runningStatus is not None:
            status = runningStatus
        else:
            index += 1
            continue

        messageType = status & 0xF0
        channel = status & 0x0F
        dataLength = 1 if messageType in (0xC0, 0xD0) else 2
        if index + dataLength > len(packet):
            break

        data1 = packet[index]
        data2 = packet[index + 1] if dataLength == 2 else 0
        index += dataLength

        if messageType == 0xB0:
            eventType = MidiMessageType.controlChange
        elif messageType == 0x90 and data2 == 0:
            eventType = MidiMessageType.noteOff
        elif messageType == 0x90:
            eventType = MidiMessageType.noteOn
        elif messageType == 0x80:
            eventType = MidiMessageType.noteOff
        else:
            eventType = MidiMessageType.unknown

        events.append(MidiEvent(eventType, channel, data1, data2, monotonic()))

    return events
```

```python
# blueboardClient.py
import asyncio
from bleak import BleakClient, BleakScanner

serviceUuid = "03b80e5a-ede8-4b33-a751-6ce34ec4c700"
midiCharacteristicUuid = "7772e5db-3868-4112-a1a9-f2669d106bf3"


async def findBlueBoard():
    devices = await BleakScanner.discover(service_uuids=[serviceUuid], timeout=8)
    for device in devices:
        if device.name and "BlueBoard" in device.name:
            return device
    raise RuntimeError("BlueBoard not found; hold C while powering it on")


async def runBlueBoard(eventHandler):
    retryDelay = 1.0
    while True:
        try:
            device = await findBlueBoard()
            async with BleakClient(device) as client:
                await client.start_notify(
                    midiCharacteristicUuid,
                    lambda _, data: [eventHandler(event) for event in decodeBleMidi(bytes(data))],
                )
                retryDelay = 1.0
                while client.is_connected:
                    await asyncio.sleep(1)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            print(f"connection failure: {error}")
            await asyncio.sleep(retryDelay)
            retryDelay = min(retryDelay * 2.0, 20.0)
```

The lambda above is intentionally compact; production code should use a named callback and a queue so BLE notification callbacks never perform slow actions.

## 10. Configuration and actions

Start with JSON in both implementations to avoid introducing a TOML parser dependency:

```json
{
  "bindings": [
    {"cc": 20, "edge": "press", "action": "ctrlShiftR"},
    {"cc": 21, "edge": "press", "action": "sendOsc", "address": "/katana/next"},
    {"cc": 22, "edge": "press", "action": "programChange", "program": 4},
    {"cc": 23, "edge": "release", "action": "stop"}
  ]
}
```

For strict standard-library Python, implement the first configuration as a Python dictionary or JSON. For C++, either write a small restricted JSON reader or begin with a compiled configuration structure; do not make a parser a project blocker.

## 11. Reconnection and safety rules

Use this state machine:

```text
scanning -> connecting -> discovering -> subscribing -> connected
    ^                                                |
    +---------------- backoff <---------------------+
```

Required behavior:

- scan by service UUID, then verify the name;
- retain the selected device identity when possible;
- use bounded exponential backoff: 1, 2, 4, 8, 16, 20 seconds;
- reset backoff after a stable connection;
- detect notification-subscription failure separately from link failure;
- release all active keys/notes when disconnected;
- never execute an action twice because of reconnect replay;
- log monotonic time, state, error, RSSI when available, and retry count;
- serialize GATT writes;
- keep BLE callbacks short and non-blocking.

## 12. Testing plan

### Unit tests

- one CC press/release;
- all CC20–CC23 mappings;
- channel filtering;
- malformed packets;
- multiple messages in one packet;
- running status;
- partial packet handling;
- note-on velocity zero as note-off;
- decoder reset after disconnect.

### Hardware tests

- 1,000 button press/release cycles;
- eight-hour idle and active run;
- screen locked where applicable;
- ten board power cycles;
- forced PC Bluetooth disable/enable;
- board moved through the intended operating distance;
- no stuck keyboard key after forced link loss;
- reconnect within ten seconds after the board returns;
- verify logs contain every disconnect reason.

## 13. Build recommendations

Use CMake with C++17:

```cmake
cmake_minimum_required(VERSION 3.20)
project(blueboardRouter LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
add_executable(blueboardRouter
    src/main.cpp
    src/bleMidiDecoder.cpp
    src/router.cpp
)
target_include_directories(blueboardRouter PRIVATE include)
```

Keep platform targets conditional. Windows links Windows Runtime/SDK libraries; Linux links D-Bus, ALSA, and pthread. The portable decoder and router should compile on both platforms without conditional code.

## 14. Implementation order

1. Freeze the event model and write decoder tests from the observed packets.
2. Implement the C++17 decoder and console replay tool.
3. Implement Python decoding and compare its output against C++ fixtures.
4. Implement Windows BLE notification subscription.
5. Add Windows `SendInput` actions.
6. Implement reconnect and stuck-state cleanup.
7. Implement Linux BlueZ D-Bus transport.
8. Add Linux uinput and ALSA outputs.
9. Add outbound BLE-MIDI LED feedback.
10. Add configuration, structured logging, and long-duration validation.

## 15. Authoritative references

- [BLE-MIDI specification](https://www.hangar42.nl/wp-content/uploads/2017/10/BLE-MIDI-spec.pdf) — service, characteristic, packet framing, timestamps, and transport rules.
- [Microsoft `GattCharacteristic::ValueChanged`](https://learn.microsoft.com/en-us/uwp/api/windows.devices.bluetooth.genericattributeprofile.gattcharacteristic.valuechanged) — Windows notification event.
- [Microsoft GATT characteristic methods](https://learn.microsoft.com/en-us/uwp/api/windows.devices.bluetooth.genericattributeprofile.gattcharacteristic) — descriptor writes and characteristic operations.
- [BlueZ GATT D-Bus API](https://github.com/bluez/bluez/blob/master/doc/gatt-api.txt) — `StartNotify`, `StopNotify`, `ReadValue`, and `WriteValue`.
- [Android MIDI documentation](https://source.android.com/docs/core/audio/midi) — Android MIDI transports and testing model.
- [MIDI BLE Connect](https://play.google.com/store/apps/details?id=com.mobileer.example.midibtlepairing) — the successful Android connection workflow used in this project.
- [Bleak documentation](https://bleak.readthedocs.io/) — Python BLE client API used by the reference prototype.
- [Microsoft `SendInput`](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-sendinput) — Windows keyboard and mouse injection.
- [Linux uinput documentation](https://www.kernel.org/doc/html/latest/input/uinput.html) — user-space input-device injection.

## 16. Codex working rules

- All identifiers, functions, variables, and filenames use camelCase where the language permits it.
- Preserve platform-neutral core logic.
- Prefer the standard library and native OS APIs in C++17.
- Keep Python dependencies limited to `bleak` initially.
- Treat the observed CC20–CC23 behavior as confirmed, but keep the parser general enough for valid BLE-MIDI packets.
- Never send a keyboard action on release unless the binding explicitly requests it.
- Never hide disconnects; every reconnect attempt must be observable in logs.
- Make one small, testable change per iteration.
