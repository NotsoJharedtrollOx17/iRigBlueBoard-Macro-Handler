# Release history and roadmap

## Purpose

This document reconciles the project's milestone notes with the current source
tree. It records what was implemented, what was physically validated, what the
version identifiers mean, and which limitations should guide the next release.

The status snapshot below was taken on 2026-08-15. Recheck Git branches, tags,
tests, and hardware before using it as a later release record.

## Current release state

At the time of this audit:

```text
working branch        dev
reviewed commit       3b64b8f
remote relationship  dev was five commits ahead of origin/dev
package version       1.0.0
runtime version       1.0.0
latest local tag      v0.3.0
main                  7737eba / origin/main
```

The source code and metadata are prepared as version `1.0.0`, and the tested
board profile has passed the recorded Windows and Linux Mint hardware checks.
There was no local `v1.0.0` Git tag during this audit. Merging, tagging,
building, publishing, and attaching artifacts remain explicit maintainer
operations; code version alone does not prove that a release was published.

The current `pyproject.toml` classifies the package as
`Production/Stable`. That classification should remain only if the release is
intentionally limited to the documented BlueBoard firmware profile and its
known Linux compatibility constraints.

## Branch and updater policy

The established development flow is:

```text
feature/<name> -> dev -> main -> release tag
```

The LED work used `dev.button-backlights` before being integrated into local
`dev`. Root update scripts are production updaters: they refuse dirty
worktrees, fetch `origin/main`, switch to the local `main` branch or create it,
fast-forward from `origin/main`, and rerun setup.

This has an important consequence for contributors: running an updater from a
clean feature or `dev` checkout intentionally switches the checkout to `main`.
To refresh a development branch, use Git directly and rerun the appropriate
setup script. A future updater may add an explicit branch option, but it must
not silently infer a branch when installing production code.

## Milestone history

### 1. Project genesis and implementation planning

Early commits preserved sample material and a broad implementation brief:

- `c63b7c5`: initial repository state;
- `47c9036`: initial sample project upload;
- `24ab936`: transferred implementation context;
- `653ac1c`: removed unused C/C++ sample files.

The original brief proposed parallel C++17 and Python implementations. The
project deliberately converged on Python. The maintained product is now the
installable `blueboard_macro_handler` package; a native port remains deferred.

### 2. BLE-MIDI and Windows macro prototype

- `6dd77c6`: initial Python BLE connection testing;
- `8d3f568`: first working default Windows macros.

This phase established the physical mapping of channel 1 CC20-CC23, the Bleak
connection path, stateful edge routing, and native Windows keyboard injection.
The Windows `SendInput` ABI was later corrected by defining the complete
native union, preventing the historical invalid-parameter error.

### 3. Installable command application

- `b7c6b4c`: installable pip command application;
- `51648fe`: global-scope installation;
- `23b03d2` / `v0.2.0`: wall-clock logs with button and macro details;
- `7577270`: clearer executed-key reporting;
- `0cce31c`: project and author welcome banner;
- `7737eba`: cleaned placeholder files and setup error paths.

The package gained console commands, typed configuration, action dispatch,
dry-run execution, replay, state persistence, lifecycle metrics, and root-level
launchers. Actions remained opt-in so installation or connection alone could
not inject input.

### 4. Installation updates and Linux scopes

- `487dc86`: Linux prerequisite installation in setup;
- `30db339`: corrected pipx installation path;
- `5012880` / `v0.2.1`: clean-worktree update mechanism;
- `ce85efe`: Linux BLE connection-loop diagnosis and compatibility backend;
- `88165a5`: development version alignment;
- `796f4b6`: Linux `/dev/uinput` preparation and validation;
- `e933560`: Linux implementation review;
- `f4af5af` / `v0.3.0`: Windows global PATH correction.

Linux work was a real platform implementation, not only documentation. It
added isolated repository, pipx, and `/opt` environments; a narrow udev/input
permission model; launcher preflight checks; and the BlueZ service-omission
fallback used on the validated Mint system.

### 5. Momentary button-backlight feedback

- `231fbc1`: preserved the LED implementation summary;
- `8b847c8`: first opt-in LED feedback implementation;
- `f8336a9`: stable press/release feedback policy;
- `7fb3941`: source-version 1.0.0 preparation;
- `3b64b8f`: README author, license, and citation metadata.

The first feedback policy exposed a legacy-receiver problem: unacknowledged
host writes could appear successful while a light remained on or while the
pedal stopped applying later commands. High-frequency periodic reconciliation
did not recover the device. The corrected implementation uses the fixed
`80 80` timestamp observed on the pedal, coalesced serialized writes, bounded
pacing, one off retry, no idle refresh, and an explicit reset sequence.

Physical Windows and Linux Mint tests subsequently confirmed momentary
feedback on the supported profile.

### 6. Documentation consolidation

The original `agent-docs` directory accumulated seven partially overlapping
briefs, investigations, roadmaps, and milestone reviews. The 2026-08-15 audit
reconciled their claims against the entire maintained source and consolidated
them into:

1. `architecture-and-extension-guide.md`;
2. `platform-operations-and-hardware-findings.md`;
3. `release-history-and-roadmap.md`.

The README remains the operational entry point. These documents provide the
deeper context needed by maintainers and AI agents without forcing users to
read historical implementation plans.

## Capability status

| Capability | Status | Evidence boundary |
|---|---|---|
| Windows BLE scan/connect/subscribe | Complete for tested profile | Physical test plus mocked lifecycle tests |
| Linux normal Bleak path | Implemented | Shared Bleak code; use where BlueZ exposes the service normally |
| Linux BlueZ omission fallback | Complete for tested handles | Physical Mint test plus parser/process tests |
| CC20-CC23 decoding and edge routing | Complete | Physical tests and packet fixtures |
| Default Windows/Linux A/B keyboard macros | Complete | Physical tests; Linux requires uinput permission |
| C/D harmless defaults | Complete | Default configuration and router tests |
| Typed keyboard/log/UDP/launch actions | Complete | Configuration and dispatcher tests |
| Dry-run and replay | Complete | CLI and fixture tests |
| JSON/human logs and run summaries | Complete | Source inspection and CLI tests |
| Last-address persistence with discovery fallback | Complete | State and client tests |
| Momentary A-D LED feedback | Complete for tested profile | Windows/Linux physical tests and controller tests |
| Persistent amplifier/effect LED state | Not implemented | Deliberately outside momentary feedback semantics |
| Complete BLE-MIDI protocol support | Not implemented | Decoder covers required channel-voice subset |
| C++17 implementation | Not implemented | Earlier design only |
| Cross-platform CI matrix | Not present | Local tests only |

## Reconciled Python roadmap

The former Python roadmap mixed completed work and future-tense descriptions.
Its items now resolve as follows.

### Configuration and action management — implemented

JSON configuration is validated at startup and normalized into immutable
models. Keyboard, log, UDP, and launch actions are typed. Launch uses an
argument array and `shell=False`; `null` is the explicit unmapped value. C and
D remain unmapped by default.

Possible future work is a formal hardware profile schema, richer key
validation at configuration-load time, and optional action types with the same
strict side-effect boundary. Arbitrary shell commands should not be added as a
casual convenience.

### Action interface — implemented

`ActionDispatcher` separates routing from platform keyboard backends and
supports release/close cleanup. The keyboard interface is expressed as a
typing protocol. A future refactor could generalize protocols for all action
types, but the current router is already platform-neutral.

### Dry-run and replay — implemented

Live run and packet replay default to no operating-system actions. Replay uses
hex packet fixtures and the same packaged decoder/router path. LED feedback is
intentionally a separate live BLE flag and is not part of offline replay.

### Automated tests — substantially implemented

The suite covers the observed decoder behavior, duplicate suppression,
bindings, cooldown-adjacent routing, action failures, configuration, CLI,
native Windows ABI, state persistence, Bleak lifecycle, serialized writes,
fallback parsing and process lifecycle, and LED feedback.

Remaining test infrastructure work is a Windows/Linux CI matrix, broader
configuration boundaries, explicit reconnect/backoff timing tests, updater
script tests, and any dynamic handle/profile implementation.

### BLE-MIDI decoding — sufficient for this device, incomplete generally

Running status, multiple messages, malformed packets, split messages, Note On
velocity zero, CC, Program Change, and Pitch Bend are handled. Remote timestamp
reconstruction, System Common, System Real-Time, SysEx, and full malformed
stream recovery remain future protocol work.

### Connection lifecycle — implemented

Explicit states, bounded reconnect backoff, notification queues, address
persistence, discovery fallback, decoder reset, stop-notify cleanup, and action
release are present. The Linux compatibility process also has stop,
termination, timeout, and silent-disconnect handling.

Future lifecycle work should focus on deterministic tests, dynamic profile
selection, and compatibility with newer Linux BLE APIs rather than redesigning
the working state machine.

### Structured logging and summaries — implemented

Human logs include local wall-clock timestamps with milliseconds. JSON logs
include monotonic time, level, logger, message, and exceptions. Shutdown
summaries include runtime, connection time, packets, events, actions, feedback,
failures, drops, and reconnects.

Logs do not currently expose every field as a separate JSON property because
structured details are embedded in the message. A future schema may normalize
fields if machine ingestion becomes a first-class requirement.

### Macro safety controls — partially implemented

Implemented controls include default dry-run, explicit action enabling,
cooldowns, duplicate-edge suppression, exception isolation, reverse-order key
release for combos, disconnect cleanup, Linux permission preflight, and Ctrl+C
shutdown.

Not implemented are an interactive startup confirmation, a global hotkey panic
listener independent of Ctrl+C, foreground-window policy, or centrally defined
per-action rate limits beyond binding cooldowns. Add them only when a concrete
deployment needs them; do not make non-interactive automation impossible by
default.

### Outbound BLE-MIDI and feedback — implemented for this profile

The package has a general encoder, serialized client writes, transport
capability selection, a bounded feedback worker, initialization, coalescing,
failure counters, conservative retries, reconnect rebinding, and reset mode.
Persistent remote effect state remains a separate future feature.

### Packaging — implemented

`pyproject.toml` defines the package, Python requirement, dependencies,
optional Linux and development extras, console script, package data, Ruff, and
pytest configuration. Root scripts cover repository and isolated global
installation paths.

Release automation, continuous artifact validation, and publishing are still
manual.

### Documentation synchronization — implemented as a process

The README now describes current behavior and links to three detailed files.
Future feature changes should update the relevant document in the same commit.
Physical findings should name their environment and avoid being generalized
without evidence.

## Automated validation snapshot

The documentation audit ran on the Windows checkout on 2026-08-15:

```text
unittest discovery  59 tests passed
Ruff                 all configured checks passed
```

The test suite deliberately includes simulated failures that log tracebacks;
those messages are expected when their enclosing tests pass.

Earlier Linux notes described three Windows-specific failures during Linux
collection. The current tests use platform-aware expected sizes and guard
Windows-only APIs, so that limitation is no longer represented by the source.
A fresh Linux execution should still be recorded before claiming a green
cross-platform CI result.

## Physical validation snapshot

### Windows

- BlueBoard discovery and connection confirmed.
- Channel 1 CC20-CC23 press/release behavior confirmed.
- A maps to `Ctrl+Shift+R`; B maps to `Alt+Tab`.
- C and D are intentionally unmapped in the default configuration.
- Native action failures do not stop BLE processing.
- Fixed-timestamp, momentary A-D LED feedback confirmed.
- Rapid button activity and reconnect behavior were exercised during LED
  stabilization.

### Linux Mint

- BlueZ service-omission failure reproduced and isolated.
- Stable `backend=bluez-gatttool` connection confirmed with tested handles.
- `/dev/uinput` device and active-session `input` membership requirements
  confirmed.
- Default keyboard macros confirmed after correct permissions.
- Interactive fallback subscription, LED initialization, sustained health
  checking, and clean disconnect confirmed.
- Momentary A-D LED feedback confirmed on the supported board profile.

See `platform-operations-and-hardware-findings.md` for trace-level evidence and
the boundary of each claim.

## Known limitations

### Fixed Linux ATT handles

The compatibility backend hard-codes value handle `0x0022` and CCC handle
`0x0023`. These values are correct for the tested BlueBoard but may change with
another firmware or hardware revision. Dynamic discovery or explicit validated
profiles is the highest-value portability improvement.

### Legacy `gatttool` dependency

`gatttool` is deprecated upstream. It is present in the full BlueZ package on
the validated system, but future distributions may omit it. The program fails
clearly when it is unavailable; it does not currently offer another low-level
fallback.

### No LED acknowledgement or state readback

The tested Windows characteristic exposes write-without-response. Host success
does not prove that the pedal changed state, and `--reset-leds` cannot guarantee
recovery. Power cycling remains the physical fallback.

### Device-specific feedback semantics

Feedback is hard-coded to channel 1 CC20-CC23 and a zero BLE-MIDI timestamp.
That behavior is supported by physical evidence for this board, not by a
generic BLE-MIDI LED standard.

### Decoder scope

The decoder covers the channel-voice behavior needed by the BlueBoard. It is
not a complete BLE-MIDI library and does not expose reconstructed remote
timestamps or full system-message semantics.

### Duplicate milestone modules

The package namespace is authoritative, but the repository still tracks older
camelCase modules and their tests. They provide historical regression value
but increase maintenance surface and can confuse an unfamiliar contributor.
Remove them only through an explicit cleanup that migrates any unique fixtures
and tests.

### Production-only updater behavior

Update scripts always target `main`. This is safe and predictable for end
users but surprising during branch development. Documentation now states this
explicitly. A branch flag remains optional future work.

### No automated Windows/Linux CI

Local automated checks and physical validation exist, but the repository has
no checked-in CI workflow. Platform-specific regressions therefore depend on
maintainer execution until CI is added.

### Qualification depth

The project has stress and reconnect evidence, but it has not recorded every
ambitious test proposed in the early brief, such as 1,000 cycles and an
eight-hour soak. Do not imply those qualifications have occurred.

## Prioritized roadmap

### Priority 1: finalize release provenance

1. Review and merge the intended `dev` commit into `main` without unrelated
   history changes.
2. Run the full automated suite on Windows and Linux from clean environments.
3. Repeat a concise physical smoke test on both platforms.
4. Build a wheel and source distribution from the exact release commit.
5. Install both artifacts into clean environments and run `blueboard --version`,
   `validate`, and `replay`.
6. Create signed or annotated `v1.0.0` release provenance according to the
   maintainer's chosen GitHub workflow.
7. Publish only the artifacts built from that tagged commit.

### Priority 2: add cross-platform CI

Create a Windows/Linux matrix for Python 3.10 and at least one current Python
version. Run unittest discovery, Ruff, package build, wheel installation, CLI
version, configuration validation, and replay. Hardware tests should remain a
separate manual gate.

### Priority 3: formalize the hardware profile

Move UUIDs, button controllers, feedback channel, fixed timestamp policy, and
Linux handles into a validated profile object. Preserve current defaults and
avoid exposing unsafe arbitrary-handle writes without validation.

### Priority 4: replace or harden the Linux fallback

Investigate dynamic ATT discovery and maintained BlueZ interfaces. Until a
replacement is proven on the affected machine, retain the narrow working path.
Expand process tests for startup variations, malformed output, failed
subscription, repeated EOF, timeout, stop races, and reconnect accounting.

### Priority 5: retire duplicate milestone code

Compare legacy and packaged tests, move unique assertions to package tests,
remove obsolete modules, and simplify import behavior. This is a cleanup task,
not a prerequisite for the working runtime.

### Priority 6: improve protocol completeness only when needed

Add timestamp reconstruction and system-message handling from shared fixtures.
Keep BlueBoard routing tests isolated from general protocol expansion so a
standards change does not destabilize the proven device path.

### Priority 7: consider richer safety and observability

Possible additions include field-structured JSON events, explicit action rate
limits, an optional panic hotkey, foreground-process diagnostics, and clearer
notification-drop metrics. Each should remain opt-in or backwards compatible.

### Priority 8: separate persistent feedback semantics

If the handler later tracks amplifier or effect state, define a separate mode
with an authoritative external state source, startup synchronization, and
reconnect reconciliation. Do not reinterpret momentary button echo as
persistent state.

## Release checklist

### Repository

- [ ] Intended changes are on `dev` with a clean worktree.
- [ ] README links resolve and `agent-docs/` contains exactly the maintained
      three-document set.
- [ ] Package and runtime versions agree.
- [ ] Default repository and packaged configurations agree.
- [ ] No generated `build`, `dist`, cache, log, or virtual-environment content
      is staged.
- [ ] `dev` is reviewed and intentionally merged into `main`.

### Automated validation

- [ ] Full unittest suite passes on Windows.
- [ ] Full unittest suite passes on Linux.
- [ ] Ruff passes on maintained package source and tests.
- [ ] Wheel and source distribution build from a clean checkout.
- [ ] Built wheel installs in a clean Windows environment.
- [ ] Built wheel plus Linux extra installs in a clean Linux environment.
- [ ] `blueboard validate` and fixture replay succeed from the installed wheel.

### Hardware validation

- [ ] Scan and connect in mode 2 on Windows.
- [ ] A-D press and release logs match CC20-CC23.
- [ ] A/B macros execute only with `--execute-actions`.
- [ ] C/D remain unmapped by default.
- [ ] A-D LEDs remain momentary under rapid input.
- [ ] Feedback remains independent from action execution.
- [ ] Forced disconnect and reconnect initialize lights off.
- [ ] Linux normal Bleak or documented compatibility backend remains stable.
- [ ] Linux uinput setup and active-session permission remain correct.
- [ ] Ctrl+C and forced link loss leave no stuck input state.

### Publication

- [ ] Release notes name the tested operating systems and hardware-profile
      limitation.
- [ ] Fixed handles and `gatttool` dependency are disclosed.
- [ ] Artifacts are built from the exact tagged commit.
- [ ] A `v1.0.0` tag and release entry exist if this is the first stable public
      release.
- [ ] Citation, author, year, and MIT attribution remain correct.

## Starting checklist for future agents

1. Read the README and all three `agent-docs` files.
2. Inspect `git status`, branch tracking, tags, and the recent log.
3. Treat `python/src/blueboard_macro_handler` as the runtime source of truth.
4. Run tests before changing behavior and record the platform used.
5. Separate code evidence, automated evidence, and physical observations.
6. Keep macros and LED writes independently opt-in.
7. Preserve the normal Bleak path and the narrow selection condition for the
   Linux fallback.
8. Do not generalize fixed handles or write success beyond the tested profile.
9. Add tests and update documentation in the same behavior-changing work.
10. Ask for new hardware evidence when a claim cannot be established from
    source, fixtures, or existing dated records.
