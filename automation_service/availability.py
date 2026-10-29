"""Owner-approved consultation window; generates candidates, never publishes slots.

Booking storage remains the authority for reservations. This calendar alone must
never be used to confirm payment, availability or a completed appointment.
"""
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

TIMEZONE = ZoneInfo('Asia/Kuala_Lumpur')
WINDOW_START = date(2026, 11, 1)
WINDOW_END = date(2026, 12, 31)
SESSION_MINUTES = 45
WEEKDAY_TIMES = (time(14), time(15), time(16), time(20, 30))
WEEKEND_TIMES = (time(17),)
BLOCKED_RANGES = (
    (date(2026, 11, 14), date(2026, 11, 14)),
    (date(2026, 11, 22), date(2026, 11, 22)),
    (date(2026, 11, 28), date(2026, 11, 29)),
    (date(2026, 12, 5), date(2026, 12, 12)),
    (date(2026, 12, 24), date(2026, 12, 27)),
    (date(2026, 12, 30), date(2027, 1, 3)),
)


def candidate_slots():
    """Return aware start/end pairs inside the approved window, in date order."""
    result = []
    day = WINDOW_START
    while day <= WINDOW_END:
        if not any(start <= day <= end for start, end in BLOCKED_RANGES):
            times = WEEKDAY_TIMES if day.weekday() < 5 else WEEKEND_TIMES
            for clock in times:
                if day.weekday() == 3 and clock == time(20, 30):
                    continue  # Thursday evening is unavailable; afternoon stays open.
                start = datetime.combine(day, clock, TIMEZONE)
                result.append((start, start + timedelta(minutes=SESSION_MINUTES)))
        day += timedelta(days=1)
    return tuple(result)


if __name__ == '__main__':
    import json
    print(json.dumps({
        'timezone': str(TIMEZONE),
        'status': 'candidate_slots_not_published',
        'slots': [{'starts_at': start.isoformat(), 'ends_at': end.isoformat()}
                  for start, end in candidate_slots()],
    }, indent=2))
