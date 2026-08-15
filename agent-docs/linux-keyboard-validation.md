# Linux keyboard macro validation

Date: 2026-08-14

## Verified procedure

The Linux BLE connection and macro keyboard path were validated with this
sequence on Linux Mint:

```bash
./setupBlueBoard.sh --skip-system
sudo usermod -aG input "$USER"
# log out and log back in
groups
./runBlueBoard.sh --debug --execute-actions
```

The equivalent explicit convenience form is:

```bash
./setupBlueBoard.sh --skip-system --add-input-group
```

It performs the persistent `usermod -aG input` change but still requires a
logout/login. The flag is intentionally opt-in because `input` membership is
security-sensitive.

The `groups` output must contain `input`. The relogin is not optional: Linux
does not add the newly granted supplementary group to an already-running
session.

## Why this is required

The Linux keyboard backend creates a virtual keyboard through `/dev/uinput`
using `python-evdev`. The kernel driver and device node are system resources;
the application should not run permanently as root. The setup script loads
the driver, installs a udev rule, creates the node when udev does not create it,
and applies `0660` permissions with group `input`. The user must then belong to
that group in the active login session.

Without the node, `evdev.UInput` raises an error. Without group membership,
the process cannot open the node. Before this validation, that failure was
only visible as a macro action error after BLE had already connected.

## Launcher guard

`runBlueBoard.sh` now checks the two prerequisites only when
`--execute-actions` is supplied:

- `/dev/uinput` must be a character device;
- the current session must list `input` in `id -nG`.

Dry-run mode remains available without keyboard permissions, which preserves
the ability to diagnose BLE and MIDI routing independently:

```bash
./runBlueBoard.sh --debug --dry-run
```

## Security note

Membership in `input` grants access to input devices and is security
sensitive. Review it with the machine administrator. The application does not
need to run as root.
