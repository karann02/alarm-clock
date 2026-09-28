import contextlib
import io
import unittest
from datetime import datetime, timedelta

from alarm.cli import EXIT_CANCELLED, EXIT_OK, main
from alarm.clock import SilentPlayer

NOW = datetime(2026, 9, 29, 10, 0, 0)


def eof_prompt(question):
    raise EOFError


class ClosablePlayer(SilentPlayer):
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


def run_main(argv, sleep=None, player=None):
    """Run main() with a fake clock whose sleep() advances time instantly."""
    clock = {"now": NOW}

    def fake_sleep(seconds):
        clock["now"] += timedelta(seconds=seconds)

    out = io.StringIO()
    code = main(argv, now=lambda: clock["now"], sleep=sleep or fake_sleep,
                prompt=eof_prompt, out=out, player=player or SilentPlayer())
    return code, out.getvalue()


def run_invalid(argv):
    """Run main() with bad input; return (exit code, stderr)."""
    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        try:
            main(argv)
        except SystemExit as exc:
            return exc.code, err.getvalue()
    raise AssertionError(f"expected SystemExit for {argv}")


class CliTest(unittest.TestCase):
    def test_passed_time_schedules_tomorrow(self):
        code, out = run_main(["12am", "--label", "Midnight"])
        self.assertEqual(code, EXIT_OK)
        self.assertIn("Alarm set for Wed 30 Sep 00:00:00 (Midnight)", out)

    def test_duration(self):
        player = ClosablePlayer()
        code, out = run_main(["--in", "1h30m"], player=player)
        self.assertEqual(code, EXIT_OK)
        self.assertTrue(player.closed)
        self.assertIn("Alarm set for Tue 29 Sep 11:30:00", out)

    def test_ctrl_c_prints_cancelled_and_exits_130(self):
        def interrupted_sleep(seconds):
            raise KeyboardInterrupt

        player = ClosablePlayer()
        code, out = run_main(["--in", "5m"], sleep=interrupted_sleep, player=player)
        self.assertEqual(code, EXIT_CANCELLED)
        self.assertTrue(player.closed)
        self.assertTrue(out.endswith("\ncancelled\n"))
        self.assertNotIn("Traceback", out)

    def test_invalid_inputs_exit_2_with_clear_message(self):
        cases = {
            ("25:00",): "hour must be 0-23",
            ("7",): "ambiguous",
            ("--in", "5x"): "invalid duration",
            ("--in", "99999999999h"): "too long",
            ("--in", "5m", "--snooze", "90000000h"): "too long",
            ("07:00", "--in", "5m"): "not allowed with",
            (): "one of the arguments",
            ("--in", "5m", "--max-snoozes", "-1"): "must be 0 or more",
        }
        for argv, message in cases.items():
            with self.subTest(argv=argv):
                code, err = run_invalid(list(argv))
                self.assertEqual(code, 2)
                self.assertIn(message, err)


if __name__ == "__main__":
    unittest.main()
