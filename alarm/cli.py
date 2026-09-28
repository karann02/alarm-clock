"""Command-line entry point: parse arguments, build the alarm, run it."""

import argparse
import sys
import time
from datetime import datetime, timedelta

from alarm.clock import Alarm, AlarmRunner, SilentPlayer
from alarm.timeparse import next_occurrence, parse_clock_time, parse_duration

EXIT_OK = 0
EXIT_CANCELLED = 130  # Unix convention for Ctrl+C (128 + SIGINT)


def _arg_type(parse):
    """Turn a ValueError from our parsers into a clean argparse error (exit 2)."""

    def convert(text):
        try:
            return parse(text)
        except ValueError as exc:
            raise argparse.ArgumentTypeError(str(exc)) from None

    return convert


def _non_negative_int(text):
    try:
        value = int(text)
    except ValueError:
        raise ValueError(f"'{text}' is not a whole number") from None
    if value < 0:
        raise ValueError(f"'{text}' must be 0 or more")
    return value


def build_parser():
    parser = argparse.ArgumentParser(
        prog="python3 -m alarm",
        description="A simple alarm clock for the terminal.",
        epilog="examples:  python3 -m alarm 07:30   |   python3 -m alarm 7:30pm "
        "--label Standup   |   python3 -m alarm --in 25m",
    )
    when = parser.add_mutually_exclusive_group(required=True)
    when.add_argument(
        "time", nargs="?", type=_arg_type(parse_clock_time),
        help="clock time: 07:30, 19:05, 7:30pm, 7am (a passed time means tomorrow)",
    )
    when.add_argument(
        "--in", dest="duration", metavar="DURATION", type=_arg_type(parse_duration),
        help="ring after a duration: 25m, 1h30m, 90s",
    )
    parser.add_argument("--label", default="", help="text shown when the alarm rings")
    parser.add_argument(
        "--snooze", type=_arg_type(parse_duration), default=timedelta(minutes=5),
        metavar="DURATION", help="snooze length (default: 5m)",
    )
    parser.add_argument(
        "--max-snoozes", type=_arg_type(_non_negative_int), default=3, metavar="N",
        help="how many times you can snooze (default: 3)",
    )
    parser.add_argument("--mute", action="store_true", help="visual alert only, no sound")
    return parser


def main(argv=None, now=datetime.now, sleep=time.sleep, prompt=input, out=None, player=None):
    args = build_parser().parse_args(argv)  # invalid input -> message + exit 2
    out = out or sys.stdout

    current = now()
    fire_at = current + args.duration if args.duration else next_occurrence(args.time, current)
    alarm = Alarm(fire_at=fire_at, label=args.label, snooze=args.snooze,
                  max_snoozes=args.max_snoozes)

    if player is None:
        if args.mute:
            player = SilentPlayer()
        else:
            from alarm.sound import AlarmPlayer
            player = AlarmPlayer()

    runner = AlarmRunner(now=now, sleep=sleep, prompt=prompt, out=out, player=player,
                         is_tty=out.isatty())
    try:
        runner.run(alarm)
        return EXIT_OK
    except KeyboardInterrupt:
        out.write("\ncancelled\n")
        out.flush()
        return EXIT_CANCELLED
    finally:
        close = getattr(player, "close", None)
        if close:
            close()
