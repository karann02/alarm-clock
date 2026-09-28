# Alarm Clock (Python CLI)

A small, dependency-free alarm clock for the terminal. Set an alarm by clock time
or by duration, watch a live countdown, get a real audible alarm, then snooze or
dismiss it.

Built as a 30-minute exercise: the goal was a **small, correct, well-tested core**
rather than many features. The requirements and plan worked out before coding are
in [PLAN.md](PLAN.md).

## Requirements

- Python **3.9+**
- **No dependencies** — standard library only, nothing to `pip install`
- Sound: `afplay` (macOS, built in), `winsound` (Windows, built in), or
  `paplay` / `aplay` (Linux). Without any of these it falls back to the terminal bell.

## Usage

Run from the project folder:

```bash
python3 -m alarm 07:30                      # 24-hour clock time
python3 -m alarm 7:30pm --label "Standup"   # 12-hour clock time with a label
python3 -m alarm 12am                       # midnight (a passed time means tomorrow)
python3 -m alarm --in 25m                   # after a duration
python3 -m alarm --in 1h30m --snooze 10m --max-snoozes 2
python3 -m alarm --in 5s --mute             # visual alert only
python3 -m alarm --help
```

While waiting, a countdown is shown (`Ringing in 00:24:59`). When the alarm rings,
answer `s` to snooze or `d` to dismiss. Press **Ctrl+C** at any time to cancel.

### Accepted formats

| Input | Examples | Notes |
|---|---|---|
| Clock time | `07:30`, `19:05`, `7:30pm`, `7am`, `12am` | A time equal to or earlier than now rings **tomorrow**. A bare hour like `7` is rejected as ambiguous. |
| Duration | `25m`, `1h30m`, `90s`, `1h` | Units `h`, `m`, `s` in that order. Must be > 0 and at most 7 days. |

### Options

| Option | Default | Description |
|---|---|---|
| `TIME` (positional) | — | Clock time to ring at. Use this **or** `--in`, not both. |
| `--in DURATION` | — | Ring after a duration. |
| `--label TEXT` | none | Text shown in the countdown and when ringing. |
| `--snooze DURATION` | `5m` | Snooze length. |
| `--max-snoozes N` | `3` | How many times you can snooze (0 = dismiss only). |
| `--mute` | off | Visual alert only, no sound. |

### Exit codes

| Code | Meaning |
|---|---|
| `0` | Alarm rang and was dismissed |
| `2` | Invalid input (bad time/duration, both or neither of `TIME` and `--in`) — argparse convention |
| `130` | Cancelled with Ctrl+C — Unix convention (128 + SIGINT) |

## Design decisions

| Decision | Why |
|---|---|
| Standard library only | Clone and run — no setup, no dependency problems. |
| Parsing/scheduling are pure functions (`timeparse.py`) that take `now` as an argument | Time parsing is where bugs hide; pure functions are easy to test exhaustively. |
| `AlarmRunner` receives `now`, `sleep`, `prompt`, `out` and the sound player as parameters | Tests use a fake clock where `sleep()` advances time instantly — a 10-minute alarm with snoozes is tested in milliseconds, without patching globals. |
| Wait in ticks of at most 0.5 s toward an absolute deadline, re-reading the clock each tick | One long `sleep()` drifts and is wrong after the laptop sleeps; ticks also drive the countdown. |
| Countdown redraw only when stdout is a TTY | Piped or logged output stays clean. |
| Reject a bare hour like `7` | 7am or 7pm? For an alarm, failing loudly beats guessing wrong. |
| `12am → 00:00`, `12pm → 12:00` via `hour % 12 (+12 for pm)` | The classic AM/PM bug, handled explicitly and tested. |
| Generated 4-beep ~2 kHz WAV (stdlib `wave`), played with the platform player | The terminal bell is muted by default in many terminals. |
| Sound repeats about every 1 s in a background thread, stops immediately on snooze/dismiss/Ctrl+C, auto-stops after 60 s | Responsive, and a forgotten alarm never rings forever. |
| If the sound player fails, fall back to the terminal bell | A broken audio setup must never silence the alarm. |
| Durations capped at 7 days | Huge values would overflow `datetime` and crash; a clear error is better. |
| EOF on stdin = dismiss; unknown answer = ask again | No crash when input is piped or closed. |
| Snooze counts from when you answer, not from when it rang | A slow answer doesn't shorten the snooze. |

## Out of scope

Deliberately cut to fit the time box:

- Multiple alarms at once, recurring alarms (daily/weekdays)
- Persistence or a config file
- Timezones and DST — times are naive local time
- Background/daemon mode (the alarm lives in the terminal session)
- Custom sounds; any GUI, web UI or database

## Running the tests

```bash
python3 -m unittest -v
```

41 tests, standard-library `unittest`, no real waiting (fake clock):

| File | Tests | Covers |
|---|---|---|
| `tests/test_timeparse.py` | 21 | 12am/12pm, invalid hours/minutes, ambiguous `7`, bad/zero/too-long durations, tomorrow rollover across month and year boundaries |
| `tests/test_clock.py` | 12 | Exact ring time, tick size, snooze, max snoozes, EOF, countdown only on a TTY, sound stops on Ctrl+C, clock jumps |
| `tests/test_cli.py` | 4 | Scheduling from the CLI, exit codes 0/2/130, error messages, player cleanup |
| `tests/test_sound.py` | 4 | WAV format and content, repeat/stop, auto-stop, fallback to the bell |

## Project layout

```
alarm/
  __init__.py
  __main__.py     # `python3 -m alarm` entry point
  cli.py          # argparse, wiring, exit codes, Ctrl+C
  clock.py        # Alarm dataclass + AlarmRunner (wait, ring, snooze/dismiss)
  sound.py        # WAV generation, platform players, background repeat loop
  timeparse.py    # pure parsing and scheduling functions
tests/
  test_cli.py
  test_clock.py
  test_sound.py
  test_timeparse.py
PLAN.md           # requirements and plan made before coding
README.md
```
