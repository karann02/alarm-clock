# Alarm Clock CLI — Plan

## Problem
A single-alarm clock for the terminal: set it by clock time or duration, see a
countdown, get a loud alert, snooze or dismiss, and exit cleanly. 30-minute time box,
so a small, correct, well-tested core beats many features.

## Scope
**In:** alarm by clock time (`07:30`, `7:30pm`) or duration (`--in 25m`, `1h30m`);
optional label; live countdown; ring with sound; snooze/dismiss with max snoozes;
`--mute`; clean Ctrl+C.

**Out:** multiple/recurring alarms, persistence/config, timezones/DST, daemon mode,
custom sounds, any GUI/web/database.

**Rules:** reject ambiguous input like `7`; a time equal to or before now means tomorrow.

## Module layout
```
alarm/
  __init__.py
  __main__.py     # enables `python3 -m alarm`
  timeparse.py    # PURE: parse_clock_time, parse_duration, next_occurrence, format_remaining
  clock.py        # Alarm dataclass + AlarmRunner (wait → ring → snooze/dismiss), I/O injected
  sound.py        # generate alarm WAV (stdlib `wave`), platform player, silent player for tests
  cli.py          # argparse, wiring real now/sleep/input/stdout, exit codes
tests/
  test_timeparse.py
  test_clock.py
  test_cli.py
PLAN.md
README.md
```

## Key design decisions
| Decision | Why |
|---|---|
| Standard library only (argparse, datetime, wave, subprocess, threading, unittest) | Clone-and-run, zero setup or dependency issues. |
| Parsing/scheduling as pure functions taking `now` as an argument | That's where bugs hide; pure functions are trivial to test exhaustively. |
| `AlarmRunner` gets `now`, `sleep`, `prompt`, `out`, `player` injected | Tests use a fake clock — a 10-minute alarm with snoozes runs in milliseconds, no patching. |
| Wait in short ticks (~0.5s) toward an **absolute deadline**, re-reading the wall clock each tick | One long `sleep()` drifts and breaks after laptop sleep; ticks also drive the countdown. |
| Countdown redraw (`\r`) only when stdout is a TTY | Piped/logged output stays clean. |
| Reject bare `7`; accept `7:00`, `7am`, `19:00` | For an alarm, failing loudly beats guessing wrong. |
| `12am → 00:00`, `12pm → 12:00` via `hour % 12 (+12 if pm)` | The classic AM/PM bug, handled explicitly and tested. |
| Generated WAV beep (≈2 kHz, 4 beeps) played via `afplay`/`winsound`/`paplay`/`aplay`, fallback `\a` | The terminal bell is muted by default in many terminals. |
| Sound loops in a background thread with a stop `Event`; auto-stop after 60s | Stops instantly on snooze/dismiss/Ctrl+C; never rings forever. |
| EOF on stdin = dismiss; invalid answer = ask again | No crash when input is piped or closed. |
| Exit codes: 0 ok, 2 bad input (argparse convention), 130 Ctrl+C (Unix convention) | Scriptable and predictable. |
| Naive local time | Timezones/DST are out of scope — documented, not hidden. |

## Implementation order
1. `timeparse.py` + `tests/test_timeparse.py` — riskiest logic first.
2. `clock.py` + `tests/test_clock.py` — runner with a FakeClock (sleep advances time).
3. `sound.py` + `cli.py` + `__main__.py` — wiring, exit codes, Ctrl+C.
4. Self-review pass for bugs and weak tests; fix accepted findings.
5. Manual validation of the real app (sound, snooze, errors, exit codes).
6. README.md + .gitignore, push to GitHub.
