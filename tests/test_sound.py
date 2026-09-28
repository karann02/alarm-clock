import os
import tempfile
import threading
import time
import unittest
import wave
from array import array

from alarm.sound import BEEPS, BEEP_SECONDS, GAP_SECONDS, SAMPLE_RATE, AlarmPlayer, make_alarm_wav


class CountingBackend:
    def __init__(self):
        self.plays = 0
        self.lock = threading.Lock()

    def play(self, stop):
        with self.lock:
            self.plays += 1


class MakeWavTest(unittest.TestCase):
    def test_wav_has_expected_format_length_and_is_not_silent(self):
        fd, path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        try:
            make_alarm_wav(path)
            with wave.open(path, "rb") as wav:
                self.assertEqual(wav.getnchannels(), 1)
                self.assertEqual(wav.getsampwidth(), 2)
                self.assertEqual(wav.getframerate(), SAMPLE_RATE)
                expected = BEEPS * (int(SAMPLE_RATE * BEEP_SECONDS) + int(SAMPLE_RATE * GAP_SECONDS))
                self.assertEqual(wav.getnframes(), expected)
                samples = array("h", wav.readframes(wav.getnframes()))
            self.assertGreater(max(samples), 10000)
        finally:
            os.remove(path)


def wait_for(condition, timeout=5.0):
    """Poll until condition() is true; generous timeout so slow machines don't flake."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(0.01)
    return False


class FailingBackend:
    def __init__(self):
        self.calls = 0

    def play(self, stop):
        self.calls += 1
        raise OSError("no sound device")


class AlarmPlayerTest(unittest.TestCase):
    def test_repeats_until_stopped_then_stops(self):
        backend = CountingBackend()
        player = AlarmPlayer(backend=backend, interval=0.01, max_seconds=30)
        player.start()
        self.assertTrue(wait_for(lambda: backend.plays >= 3))
        player.stop()
        self.assertFalse(player.playing)
        plays_at_stop = backend.plays
        time.sleep(0.05)
        self.assertEqual(backend.plays, plays_at_stop)  # nothing plays after stop()

    def test_auto_stops_after_max_seconds(self):
        backend = CountingBackend()
        player = AlarmPlayer(backend=backend, interval=0.01, max_seconds=0.1)
        player.start()
        self.assertTrue(wait_for(lambda: not player.playing))
        self.assertGreaterEqual(backend.plays, 1)

    def test_broken_backend_falls_back_to_bell(self):
        failing, bell = FailingBackend(), CountingBackend()
        player = AlarmPlayer(backend=failing, interval=0.01, max_seconds=30, fallback=bell)
        player.start()
        self.assertTrue(wait_for(lambda: bell.plays >= 2))
        player.stop()
        self.assertEqual(failing.calls, 1)  # switched once, then stayed on the bell


if __name__ == "__main__":
    unittest.main()
