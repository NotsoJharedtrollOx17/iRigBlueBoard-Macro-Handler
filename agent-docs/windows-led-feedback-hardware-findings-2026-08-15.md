# Windows LED feedback hardware findings — 2026-08-15

## Scope

This record covers physical iRig BlueBoard testing on Windows in BLE-MIDI mode
2 (boot while holding C) using `--led-feedback`. Macro execution was enabled
for some runs, but the C-only reproduction had no mapped macro, so the LED
fault is independent of action dispatch.

## Observed behavior

1. Physical press and release packets for A-D continued arriving at the
   handler while an LED could remain lit.
2. Windows reported no exceptions for outbound LED writes, even when the
   corresponding physical LED did not change.
3. The board exposed the BLE-MIDI characteristic as
   `write-without-response`; it did not advertise acknowledged `write`.
4. A C-button stress test reproduced a stuck-on C LED after its release. The
   handler logged the C-off command and later logged repeated C-off commands,
   but the device did not visibly recover during that connection.
5. A later conservative-retry run reproduced the inverse failure: button
   events and local LED-on writes continued, but the physical LEDs stopped
   turning on.

## Evidence from the 2026-08-14 trace

- At `22:36:33.138`, the client selected
  `LED feedback transport=write-without-response`.
- C release was received at `22:37:02.472` and its LED-off write was logged at
  `22:37:02.479`.
- The former periodic reconciler subsequently sent C-off again at two-second
  intervals through `22:37:43.914`.
- The summary reported 30 input events but 169 LED writes over 71.923 seconds
  of connected time, with zero local write failures and zero queue drops.

`write-without-response` only confirms that the Windows BLE stack accepted a
packet for transmission. It does not confirm that the BlueBoard received or
applied it, so the zero-failure counter must not be interpreted as device
acknowledgement.

## Evidence from the 2026-08-15 trace

- The run received 28 events and issued exactly 46 planned writes: four
  initial clears plus 14 on, 14 off, and 14 targeted off-retry packets.
- No write failed, no queue item was dropped, and the connection did not
  reconnect.
- Each physical press had a corresponding local LED-on write, proving that
  queue coalescing did not suppress the missing lights.
- Every packet emitted by the BlueBoard in all captured traces began with
  `80 80`, a zero BLE-MIDI timestamp.
- The host feedback encoder instead used a changing 13-bit monotonic timestamp,
  which wraps every 8.192 seconds.

An independent BlueBoard integration report describes the same intermittent
LED output followed by a complete stall and reports that an immediate/zero
timestamp fixed it:
https://forum.juce.com/t/irig-blueboard-midi-issue-and-potential-fix/29746

## Engineering conclusion

The periodic four-LED reconciliation was unsafe for this legacy receiver. It
generated persistent background traffic and could not recover a board that had
stopped honoring host LED packets. It was removed.

The current conservative policy is:

- serialize and coalesce LED state updates;
- use acknowledged writes when a future backend/device advertises `write`;
- otherwise space writes by 125 ms;
- on release, retry only that button's LED-off packet once after 200 ms;
- cancel that retry if the same button is pressed again;
- never emit idle background LED traffic;
- encode BlueBoard LED frames with the device-compatible fixed `80 80`
  timestamp header while leaving the general BLE-MIDI encoder unchanged;
- provide `blueboard run --led-feedback --reset-leds` for one fresh,
  paced A-D-off recovery attempt.

The reset command cannot guarantee recovery because the device exposes no
application-level acknowledgement or LED-state readback. If it does not clear
the board, power-cycling the BlueBoard remains the required hardware recovery.

## v1.0.0 release validation

The maintainer subsequently confirmed that the corrected fixed-timestamp
implementation works end-to-end on the physical board, including Linux Mint
testing through the BlueZ `gatttool` compatibility path. The conservative
retry policy and explicit opt-in flag remain in place.

The following checks remain useful as regression coverage:

1. Confirm every outbound LED debug line begins with `packet=80 80` and no
   periodic reconciliation messages appear.
2. Press and release only C at least 20 times, including rapid presses, and
   verify each release either clears immediately or after the one 200 ms retry.
3. Repeat for A, B, and D; include mapped A/B actions to confirm they do not
   alter LED timing.
4. If a LED becomes stuck, run
   `blueboard run --led-feedback --reset-leds --debug` before power-cycling and
   retain the log.
5. Record whether the reset clears the LED and whether a reconnect alone is
   sufficient. Do not promote the LED feature to v1.0 until this sequence is
   stable on the physical board.
6. Keep the handler connected and active for at least 60 seconds so testing
   spans several 8.192-second timestamp-wrap periods.
