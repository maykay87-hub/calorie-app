from datetime import date, time, timedelta
import unittest

from automation_service.availability import candidate_slots


class AvailabilityTests(unittest.TestCase):
    def test_approved_dates_and_thursday_exception(self):
        slots = candidate_slots()
        starts = {start.isoformat() for start, _ in slots}
        self.assertIn('2026-11-02T20:30:00+08:00', starts)
        self.assertIn('2026-11-05T14:00:00+08:00', starts)
        self.assertNotIn('2026-11-05T20:30:00+08:00', starts)
        self.assertIn('2026-11-01T17:00:00+08:00', starts)
        self.assertIn('2026-12-29T20:30:00+08:00', starts)
        for start, end in slots:
            self.assertTrue(date(2026, 11, 1) <= start.date() <= date(2026, 12, 31))
            self.assertEqual(end - start, timedelta(minutes=45))
            self.assertEqual(start.utcoffset(), timedelta(hours=8))
            self.assertEqual(end.date(), start.date())
            if start.weekday() >= 5:
                self.assertEqual(start.time(), time(17))
            if start.weekday() == 3:
                self.assertNotEqual(start.time(), time(20, 30))

    def test_all_blackouts_are_excluded_and_no_duplicates(self):
        starts = [start for start, _ in candidate_slots()]
        self.assertEqual(len(starts), len(set(starts)))
        blocked = {date(2026, 11, d) for d in (14, 22, 28, 29)}
        blocked |= {date(2026, 12, d) for d in range(5, 13)}
        blocked |= {date(2026, 12, d) for d in range(24, 28)}
        blocked |= {date(2026, 12, 30), date(2026, 12, 31)}
        self.assertFalse({start.date() for start in starts} & blocked)
        # Check adjacent allowed dates were not swallowed by inclusive ranges.
        days = {start.date() for start in starts}
        self.assertTrue({date(2026, 12, 4), date(2026, 12, 13),
                         date(2026, 12, 23), date(2026, 12, 28)} <= days)


if __name__ == '__main__':
    unittest.main()
