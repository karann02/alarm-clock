"""Alarm model and the runner that waits, rings, and handles snooze/dismiss.

All side effects (clock, sleeping, reading input, writing output, sound) are
injected, so tests can drive a whole alarm with a fake clock in milliseconds.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Callable, List

from alarm.timeparse import format_remaining

TICK_SECONDS = 0.5


@dataclass
class Alarm:
    fire_at: datetime
    label: str = ""
    snooze: timedelta = timedelta(minutes=5)
    max_snoozes: int = 3


@dataclass
class RunResult:
    rang_at: List[datetime] = field(default_factory=list)
    snoozes: int = 0


class SilentPlayer:
    """A player that makes no sound; the default, and handy in tests."""

    def start(self):
        pass

    def stop(self):
        pass


class AlarmRunner:
    def __init__(
        self,
        now: Callable[[], datetime],
        sleep: Callable[[float], None],
        prompt: Callable[[str], str],
        out,
        player=None,
        is_tty: bool = False,
        tick: float = TICK_SECONDS,
    ):
        self.now = now
        self.sleep = sleep
        self.prompt = prompt
        self.out = out
        self.player = player or SilentPlayer()
        self.is_tty = is_tty
        self.tick = tick

    def run(self, alarm: Alarm) -> RunResult:
        result = RunResult()
        label = f" ({alarm.label})" if alarm.label else ""
        self._write(f"Alarm set for {alarm.fire_at:%a %d %b %H:%M:%S}{label}\n")

        deadline = alarm.fire_at
        while True:
            self._wait_until(deadline, label)
            rang_at = self.now()
            result.rang_at.append(rang_at)
            self._write(f"\n*** ALARM{label} - {rang_at:%H:%M:%S} ***\n")

            can_snooze = result.snoozes < alarm.max_snoozes
            self.player.start()
            try:
                choice = self._ask(can_snooze, alarm.max_snoozes)
            finally:
                self.player.stop()

            if choice == "s":
                result.snoozes += 1
                deadline = self.now() + alarm.snooze
                self._write(
                    f"Snoozed ({result.snoozes}/{alarm.max_snoozes}) "
                    f"until {deadline:%H:%M:%S}\n"
                )
                continue
            self._write("Dismissed.\n")
            return result

    def _wait_until(self, deadline: datetime, label: str):
        # Re-read the wall clock every tick instead of one long sleep: no drift,
        # and still correct if the machine was suspended in between.
        while True:
            remaining = deadline - self.now()
            if remaining <= timedelta(0):
                break
            if self.is_tty:
                self._write(f"\rRinging in {format_remaining(remaining)}{label}  ")
            self.sleep(min(self.tick, remaining.total_seconds()))
        if self.is_tty:
            self._write("\r\033[K")

    def _ask(self, can_snooze: bool, max_snoozes: int) -> str:
        question = "[s]nooze / [d]ismiss? " if can_snooze else "[d]ismiss? "
        while True:
            try:
                answer = self.prompt(question).strip().lower()
            except EOFError:
                self._write("\n(no input - dismissing)\n")
                return "d"
            if answer in ("d", "dismiss"):
                return "d"
            if answer in ("s", "snooze"):
                if can_snooze:
                    return "s"
                self._write(f"No snoozes left (max {max_snoozes}).\n")
                continue
            self._write("Please type s or d.\n" if can_snooze else "Please type d.\n")

    def _write(self, text: str):
        self.out.write(text)
        self.out.flush()
