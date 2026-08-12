# iRig BlueBoard Macro Handler

> **Notice:** This is an independent, community-developed project. It is not
> affiliated with, sponsored by, or endorsed by IK Multimedia, iRig, or any
> manufacturer of the referenced hardware and software. Product names and
> trademarks belong to their respective owners.

The first runnable milestone is a Python 3.10+ Windows diagnostic client. It
scans for the BlueBoard, connects to its BLE-MIDI GATT service, subscribes to
notifications, decodes MIDI, and logs CC20-CC23 button edges. It deliberately
does not inject keyboard input yet, so BLE connection issues can be diagnosed
independently from macro behavior.

## Connecting the BlueBoard to a device

The BlueBoard must be started in its BLE-MIDI mode before the computer scans
for it. A BLE peripheral generally accepts one active connection, so release
any existing Android, tablet, or DAW connection first.

1. **Prepare the board.** Install working batteries and switch Bluetooth on in
   the target computer or phone. If the board is currently connected to
   another device, close that application and disable Bluetooth on the other
   device temporarily.
2. **Start BLE-MIDI mode.** Hold button **C** while powering on the
   BlueBoard. Keep holding C until the board has finished starting, then place
   it close to the target device during the first connection attempt.
3. **Leave system Bluetooth pairing available.** On Windows, open **Settings >
   Bluetooth & devices** and ensure Bluetooth is enabled. Do not select an
   unrelated classic-Bluetooth audio profile; this project needs the board's
   BLE-MIDI GATT service.
4. **Scan from this project.** From the `python` directory, run:

   ```powershell
   .\.venv\Scripts\python.exe src\main.py scan --debug --scan-timeout 15
   ```

   The output should include the BlueBoard name, its Windows BLE address, and
   an RSSI value. If it is found, copy the address for the next step.
5. **Connect and subscribe.** Run the client using the discovered address:

   ```powershell
   .\.venv\Scripts\python.exe src\main.py run --address "DEVICE-ADDRESS" --debug
   ```

   The client connects to service
   `03b80e5a-ede8-4b33-a751-6ce34ec4c700`, subscribes to characteristic
   `7772e5db-3868-4112-a1a9-f2669d106bf3`, and waits for notifications. A
   successful connection is reported as `state=connected`.
6. **Verify the MIDI path.** Press and release each button. The log should
   show Control Change events on MIDI channel 1: A=`CC20`, B=`CC21`, C=`CC22`,
   and D=`CC23`; press values are normally `127` and release values `0`.

If GATT discovery or subscription requires authentication, repeat the run
command with `--pair`. Windows may display a pairing prompt; complete it and
allow the command to reconnect. Pairing is not required for every BlueBoard
firmware revision.

### Connecting from Android first

Android can be used to confirm that the board is transmitting BLE-MIDI, but it
must be disconnected before Windows can claim the board. Stop the MIDI/BLE
connector application, disconnect or forget the board in Android Bluetooth
settings, and then power-cycle the BlueBoard while holding C. Otherwise the
Windows scan may see no BlueBoard even though the hardware is powered on.

### Troubleshooting

- **No device appears:** power-cycle while holding C, move within a few meters,
  confirm batteries, and extend `--scan-timeout` to 30 seconds.
- **The board appears but connection fails:** close Android/DAW MIDI apps,
  remove stale Windows Bluetooth entries if necessary, then retry with
  `--pair`.
- **Connected but no events arrive:** verify that the client reports
  `state=subscribing` followed by `state=connected`; restart the board in mode
  C and retry. Notifications are enabled by the program, not by a keyboard
  pairing profile.
- **Events stop after a while:** leave the client running; it logs the failure,
  clears active button state, and retries with bounded delays of 1, 2, 4, 8,
  16, and 20 seconds.
- **A macro does not affect an elevated application:** Windows input injection
  cannot cross integrity levels. The diagnostic milestone only logs actions;
  any future `SendInput` action must run at an appropriate integrity level.

## Windows quick start

1. Install a current 64-bit Python and enable Bluetooth in Windows.
2. Open PowerShell in the `python` directory and create the environment:

   ```powershell
   py -3.10 -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   ```

3. Disconnect the BlueBoard from Android (a BLE peripheral normally accepts
   only one active client), then hold the BlueBoard **C** switch while powering
   it on in BLE-MIDI mode.
4. Check that Windows can see it:

   ```powershell
   .\.venv\Scripts\python.exe src\main.py scan --debug
   ```

5. Connect and watch button events:

   ```powershell
   .\.venv\Scripts\python.exe src\main.py run --debug
   ```

   A successful press on A resembles `controlChange channel=1 data1=20
   data2=127`; release uses `data2=0`. Buttons B-D use CC21-CC23.

The repository-root PowerShell launchers provide the same workflow without
changing directories:

```powershell
.\setupBlueBoard.ps1
.\scanBlueBoard.ps1 --debug --scan-timeout 15
.\runBlueBoard.ps1 --debug
```

If PowerShell blocks local scripts for the current session, run
`Set-ExecutionPolicy -Scope Process Bypass` and retry. The launchers do not
change the system-wide execution policy.

If service discovery fails before subscribing, retry with `--pair`. You can
also pass the address printed by `scan` via `--address`. Stop with Ctrl+C.
Reconnect attempts and failures remain visible in the log.

## Tests

From the `python` directory:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test*.py" -v
```

The current milestone logs configured actions from `config/blueboard.json`.
Windows `SendInput` actions should only be enabled after the hardware
notification path has been confirmed.

Native keyboard macros are opt-in. Run the client with `--execute-actions` to
enable them. Windows uses the native `SendInput` ABI; Linux uses a `/dev/uinput` virtual
keyboard and requires narrowly scoped access to that device. The sample
bindings map A to `Ctrl+Shift+R` and B to `Alt+Tab`; edit
`python/config/blueboard.json` to change them. Unknown actions remain logged.
