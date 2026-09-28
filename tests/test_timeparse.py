import unittest
from datetime import datetime, time, timedelta

from alarm.timeparse import (
    format_remaining,
    next_occurrence,
    parse_clock_time,
    parse_duration,
)


class ParseClockTimeTest(unittest.TestCase):
    def test_24_hour(self):
        self.assertEqual(parse_clock_time("07:30"), time(7, 30))
        self.assertEqual(parse_clock_time("19:05"), time(19, 5))
        self.assertEqual(parse_clock_time("0:00"), time(0, 0))
        self.assertEqual(parse_clock_time("23:59"), time(23, 59))

    def test_am_pm(self):
        self.assertEqual(parse_clock_time("7:30pm"), time(19, 30))
        self.assertEqual(parse_clock_time("7am"), time(7, 0))
        self.assertEqual(parse_clock_time(" 7:30 PM "), time(19, 30))
        self.assertEqual(parse_clock_time("7:30a.m."), time(7, 30))

    def test_12am_is_midnight_and_12pm_is_noon(self):
        self.assertEqual(parse_clock_time("12am"), time(0, 0))
        self.assertEqual(parse_clock_time("12:15am"), time(0, 15))
        self.assertEqual(parse_clock_time("12pm"), time(12, 0))
        self.assertEqual(parse_clock_time("12:45pm"), time(12, 45))

    def test_bare_hour_is_rejected_as_ambiguous(self):
        with self.assertRaisesRegex(ValueError, "ambiguous"):
            parse_clock_time("7")

    def test_invalid_hours(self):
        for text in ("24:00", "25:00", "13pm", "0am", "0:30pm"):
            with self.subTest(text=text), self.assertRaisesRegex(ValueError, "hour"):
                parse_clock_time(text)

    def test_invalid_minutes(self):
        for text in ("7:60", "7:99pm"):
            with self.subTest(text=text), self.assertRaisesRegex(ValueError, "minutes"):
                parse_clock_time(text)

    def test_garbage(self):
        for text in ("", "abc", "7:5", "7:30xm", "07:30:00", "-7:00"):
            with self.subTest(text=text), self.assertRaisesRegex(ValueError, "invalid time"):
                parse_clock_time(text)


class ParseDurationTest(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(parse_duration("25m"), timedelta(minutes=25))
        self.assertEqual(parse_duration("1h30m"), timedelta(hours=1, minutes=30))
        self.assertEqual(parse_duration("90s"), timedelta(seconds=90))
        self.assertEqual(parse_duration("1h"), timedelta(hours=1))
        self.assertEqual(parse_duration("1H 5M 3S"), timedelta(hours=1, minutes=5, seconds=3))

    def test_zero_is_rejected(self):
        for text in ("0m", "0h0m0s"):
            with self.subTest(text=text), self.assertRaisesRegex(ValueError, "greater than zero"):
                parse_duration(text)

    def test_too_long_is_rejected_without_overflow(self):
        self.assertEqual(parse_duration("168h"), timedelta(days=7))
        for text in ("168h1s", "99999999999999999999h", "90000000h"):
            with self.subTest(text=text), self.assertRaisesRegex(ValueError, "too long"):
                parse_duration(text)

    def test_bad_durations(self):
        for text in ("", "5", "5x", "-5m", "m", "30m1h", "1.5h", "abc"):
            with self.subTest(text=text), self.assertRaisesRegex(ValueError, "invalid duration"):
                parse_duration(text)


class NextOccurrenceTest(unittest.TestCase):
    def test_later_today(self):
        now = datetime(2026, 9, 29, 6, 0)
        self.assertEqual(next_occurrence(time(7, 30), now), datetime(2026, 9, 29, 7, 30))

    def test_already_passed_today_means_tomorrow(self):
        now = datetime(2026, 9, 29, 8, 0)
        self.assertEqual(next_occurrence(time(7, 30), now), datetime(2026, 9, 30, 7, 30))

    def test_exactly_now_means_tomorrow(self):
        now = datetime(2026, 9, 29, 7, 30)
        self.assertEqual(next_occurrence(time(7, 30), now), datetime(2026, 9, 30, 7, 30))

    def test_seconds_past_target_minute_means_tomorrow(self):
        now = datetime(2026, 9, 29, 7, 30, 1)
        self.assertEqual(next_occurrence(time(7, 30), now), datetime(2026, 9, 30, 7, 30))

    def test_crosses_month_boundary(self):
        now = datetime(2026, 1, 31, 23, 0)
        self.assertEqual(next_occurrence(time(6, 0), now), datetime(2026, 2, 1, 6, 0))

    def test_crosses_year_boundary(self):
        now = datetime(2026, 12, 31, 23, 59)
        self.assertEqual(next_occurrence(time(0, 0), now), datetime(2027, 1, 1, 0, 0))


class FormatRemainingTest(unittest.TestCase):
    def test_formats_hours_minutes_seconds(self):
        self.assertEqual(format_remaining(timedelta(hours=1, minutes=2, seconds=3)), "01:02:03")

    def test_rounds_partial_seconds_up(self):
        self.assertEqual(format_remaining(timedelta(seconds=0.4)), "00:00:01")

    def test_never_negative(self):
        self.assertEqual(format_remaining(timedelta(seconds=-5)), "00:00:00")

    def test_more_than_a_day(self):
        self.assertEqual(format_remaining(timedelta(hours=25)), "25:00:00")


if __name__ == "__main__":
    unittest.main()
