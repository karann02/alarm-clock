import io
import unittest
from datetime import datetime, timedelta

from alarm.clock import Alarm, AlarmRunner

START = datetime(2026, 9, 29, 7, 0, 0)


class FakeClock:
    """now() returns fake time; sleep() advances it instantly and records the call."""

    def __init__(self, start=START, jump_on_first_sleep=timedelta(0)):
        self.current = start
        self.sleeps = []
        self._jump = jump_on_first_sleep

    def now(self):
        return self.current

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.current += timedelta(seconds=seconds) + self._jump
        self._jump = timedelta(0)


class FakePrompt:
    """Returns scripted answers in order; raises EOFError when they run out."""

    def __init__(self, *answers):
        self.answers = list(answers)
        self.questions = []

    def __call__(self, question):
        self.questions.append(question)
        if not self.answers:
            raise EOFError
        answer = self.answers.pop(0)
        if isinstance(answer, BaseException):
            raise answer
        return answer


class FakePlayer:
    def __init__(self):
        self.starts = 0
        self.stops = 0

    @property
    def playing(self):
        return self.starts > self.stops

    def start(self):
        self.starts += 1

    def stop(self):
        self.stops += 1


def make_runner(clock, prompt, is_tty=False):
    out = io.StringIO()
    player = FakePlayer()
    runner = AlarmRunner(
        now=clock.now, sleep=clock.sleep, prompt=prompt, out=out,
        player=player, is_tty=is_tty,
    )
    return runner, out, player


class AlarmRunnerTest(unittest.TestCase):
    def test_rings_exactly_at_deadline_and_dismisses(self):
        clock = FakeClock()
        fire_at = START + timedelta(minutes=10)
        runner, out, _ = make_runner(clock, FakePrompt("d"))

        result = runner.run(Alarm(fire_at=fire_at, label="Tea"))

        self.assertEqual(result.rang_at, [fire_at])
        self.assertEqual(result.snoozes, 0)
        self.assertEqual(clock.now(), fire_at)  # did not oversleep
        text = out.getvalue()
        self.assertIn("Alarm set for Tue 29 Sep 07:10:00 (Tea)", text)
        self.assertIn("*** ALARM (Tea) - 07:10:00 ***", text)
        self.assertTrue(text.endswith("Dismissed.\n"))

    def test_waits_in_short_ticks_that_add_up_to_the_delay(self):
        clock = FakeClock()
        runner, _, _ = make_runner(clock, FakePrompt("d"))

        runner.run(Alarm(fire_at=START + timedelta(seconds=10.2)))

        self.assertLessEqual(max(clock.sleeps), 0.5)
        self.assertEqual(len(clock.sleeps), 21)  # 20 full ticks + one 0.2s tick
        self.assertAlmostEqual(sum(clock.sleeps), 10.2, places=6)

    def test_snooze_then_dismiss_rings_again_after_snooze(self):
        clock = FakeClock()
        fire_at = START + timedelta(minutes=1)
        runner, out, _ = make_runner(clock, FakePrompt("s", "d"))

        result = runner.run(Alarm(fire_at=fire_at, snooze=timedelta(minutes=5)))

        self.assertEqual(result.rang_at, [fire_at, fire_at + timedelta(minutes=5)])
        self.assertEqual(result.snoozes, 1)
        self.assertIn("Snoozed (1/3) until 07:06:00", out.getvalue())

    def test_max_snoozes_is_enforced(self):
        clock = FakeClock()
        prompt = FakePrompt("s", "s", "s", "d")
        runner, out, _ = make_runner(clock, prompt)

        result = runner.run(Alarm(fire_at=START, snooze=timedelta(minutes=1), max_snoozes=2))

        self.assertEqual(result.snoozes, 2)
        self.assertEqual(len(result.rang_at), 3)
        self.assertIn("No snoozes left (max 2).", out.getvalue())
        self.assertEqual(
            prompt.questions,
            ["[s]nooze / [d]ismiss? ", "[s]nooze / [d]ismiss? ", "[d]ismiss? ", "[d]ismiss? "],
        )

    def test_eof_on_stdin_dismisses(self):
        clock = FakeClock()
        runner, out, _ = make_runner(clock, FakePrompt())  # no answers -> EOFError

        result = runner.run(Alarm(fire_at=START + timedelta(seconds=1)))

        self.assertEqual(len(result.rang_at), 1)
        self.assertIn("(no input - dismissing)", out.getvalue())
        self.assertTrue(out.getvalue().endswith("Dismissed.\n"))

    def test_invalid_answer_asks_again(self):
        clock = FakeClock()
        prompt = FakePrompt("x", "  D  ")
        runner, out, _ = make_runner(clock, prompt)

        result = runner.run(Alarm(fire_at=START))

        self.assertEqual(len(prompt.questions), 2)
        self.assertIn("Please type s or d.", out.getvalue())
        self.assertEqual(result.snoozes, 0)

    def test_no_countdown_when_not_a_tty(self):
        clock = FakeClock()
        runner, out, _ = make_runner(clock, FakePrompt("d"), is_tty=False)

        runner.run(Alarm(fire_at=START + timedelta(seconds=2)))

        self.assertNotIn("\r", out.getvalue())
        self.assertNotIn("Ringing in", out.getvalue())

    def test_countdown_when_tty(self):
        clock = FakeClock()
        runner, out, _ = make_runner(clock, FakePrompt("d"), is_tty=True)

        runner.run(Alarm(fire_at=START + timedelta(seconds=2), label="Tea"))

        self.assertIn("\rRinging in 00:00:02 (Tea)", out.getvalue())
        self.assertIn("\rRinging in 00:00:01 (Tea)", out.getvalue())

    def test_sound_plays_only_while_ringing(self):
        clock = FakeClock()
        runner, _, player = make_runner(clock, FakePrompt("s", "d"))

        runner.run(Alarm(fire_at=START, snooze=timedelta(seconds=1)))

        self.assertEqual(player.starts, 2)
        self.assertEqual(player.stops, 2)
        self.assertFalse(player.playing)

    def test_sound_stops_on_ctrl_c_while_ringing(self):
        clock = FakeClock()
        runner, _, player = make_runner(clock, FakePrompt(KeyboardInterrupt()))

        with self.assertRaises(KeyboardInterrupt):
            runner.run(Alarm(fire_at=START))

        self.assertEqual(player.starts, 1)
        self.assertFalse(player.playing)

    def test_alarm_already_due_rings_without_sleeping(self):
        clock = FakeClock()
        runner, _, _ = make_runner(clock, FakePrompt("d"))

        result = runner.run(Alarm(fire_at=START - timedelta(seconds=5)))

        self.assertEqual(clock.sleeps, [])
        self.assertEqual(result.rang_at, [START])

    def test_wall_clock_jump_rings_on_next_tick(self):
        # Simulates the laptop sleeping for an hour during a 10-minute alarm.
        clock = FakeClock(jump_on_first_sleep=timedelta(hours=1))
        runner, _, _ = make_runner(clock, FakePrompt("d"))

        result = runner.run(Alarm(fire_at=START + timedelta(minutes=10)))

        self.assertEqual(len(clock.sleeps), 1)
        self.assertEqual(result.rang_at, [START + timedelta(hours=1, seconds=0.5)])


if __name__ == "__main__":
    unittest.main()
