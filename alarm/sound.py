"""Alarm sound: a generated beep WAV, looped in a background thread.

The terminal bell ('\\a') is muted by default in many terminals, so we build a
classic 4-beep digital alarm with the stdlib `wave` module and play it with the
platform's own player. Everything here is standard library only.
"""

import math
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import wave
from array import array

SAMPLE_RATE = 22050
BEEP_HZ = 2000
BEEP_SECONDS = 0.08
GAP_SECONDS = 0.06
BEEPS = 4


def make_alarm_wav(path):
    """Write a 4-beep ~2 kHz alarm to `path` (16-bit mono PCM)."""
    samples = array("h")
    beep_len = int(SAMPLE_RATE * BEEP_SECONDS)
    gap_len = int(SAMPLE_RATE * GAP_SECONDS)
    fade = int(SAMPLE_RATE * 0.005)  # 5 ms fade in/out avoids clicks
    for _ in range(BEEPS):
        for i in range(beep_len):
            envelope = min(1.0, i / fade, (beep_len - 1 - i) / fade)
            value = math.sin(2 * math.pi * BEEP_HZ * i / SAMPLE_RATE)
            samples.append(int(0.6 * 32767 * envelope * value))
        samples.extend([0] * gap_len)
    if sys.byteorder == "big":
        samples.byteswap()  # WAV data is little-endian
    with wave.open(path, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(samples.tobytes())


class CommandBackend:
    """Plays the file with an external command (afplay, paplay, aplay)."""

    def __init__(self, command, path):
        self.command = command
        self.path = path

    def play(self, stop):
        proc = subprocess.Popen(
            self.command + [self.path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        while proc.poll() is None:
            if stop.wait(0.02):
                proc.terminate()
                proc.wait()
                return
        if proc.returncode != 0:
            # e.g. paplay installed but no sound server running
            raise OSError(f"{self.command[0]} exited with code {proc.returncode}")


class WinsoundBackend:
    def __init__(self, path):
        self.path = path

    def play(self, stop):
        import winsound

        winsound.PlaySound(self.path, winsound.SND_FILENAME | winsound.SND_ASYNC)
        stop.wait(BEEPS * (BEEP_SECONDS + GAP_SECONDS))
        winsound.PlaySound(None, 0)


class BellBackend:
    """Last resort: the terminal bell."""

    def play(self, stop):
        sys.stdout.write("\a")
        sys.stdout.flush()


def choose_backend(path):
    if sys.platform == "darwin" and shutil.which("afplay"):
        return CommandBackend(["afplay"], path)
    if sys.platform == "win32":
        return WinsoundBackend(path)
    if shutil.which("paplay"):
        return CommandBackend(["paplay"], path)
    if shutil.which("aplay"):
        return CommandBackend(["aplay", "-q"], path)
    return BellBackend()


class AlarmPlayer:
    """Repeats the alarm sound about every `interval` seconds until stopped.

    start()/stop() may be called repeatedly (once per ring). Playback stops by
    itself after `max_seconds` so a forgotten alarm never rings forever.
    """

    def __init__(self, backend=None, interval=1.0, max_seconds=60.0, fallback=None):
        self._backend = backend
        self._fallback = fallback or BellBackend()
        self._wav_path = None
        self.interval = interval
        self.max_seconds = max_seconds
        self._stop = threading.Event()
        self._thread = None

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        if self._backend is None:
            fd, self._wav_path = tempfile.mkstemp(prefix="alarm-", suffix=".wav")
            os.close(fd)
            make_alarm_wav(self._wav_path)
            self._backend = choose_backend(self._wav_path)
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, args=(self._stop,), daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None

    @property
    def playing(self):
        return bool(self._thread and self._thread.is_alive())

    def close(self):
        self.stop()
        if self._wav_path:
            try:
                os.remove(self._wav_path)
            except OSError:
                pass
            self._wav_path = None

    def _loop(self, stop):
        started = time.monotonic()
        while not stop.is_set() and time.monotonic() - started < self.max_seconds:
            cycle_start = time.monotonic()
            try:
                self._backend.play(stop)
            except Exception:
                # Never let a broken player silence the alarm: use the bell instead.
                self._backend = self._fallback
                self._backend.play(stop)
            stop.wait(max(0.0, self.interval - (time.monotonic() - cycle_start)))
