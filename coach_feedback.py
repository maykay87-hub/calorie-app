"""Human-written reviews, compatible with the existing feedback worksheet.

No AI generation or automatic review delivery. Append revisions to preserve history.
"""
from datetime import date, timedelta

HEADERS = ['username', 'month', 'note']


def review_period(kind, day):
    day = date.fromisoformat(str(day))
    if kind == 'weekly':
        start = day - timedelta(days=day.weekday())
        end = start + timedelta(days=6)
        return f'Week {start.isoformat()} — {end.isoformat()}'
    if kind == 'monthly':
        return day.strftime('%Y-%m')
    raise ValueError('Choose a weekly or monthly review.')


def _read(sheet):
    if sheet is None:
        return [], []
    rows = sheet.get_all_values()
    if not rows or rows == [[]]:
        return [], []
    headers = rows[0]
    if any(headers.count(key) != 1 for key in HEADERS):
        raise ValueError('Unexpected feedback columns; existing data was preserved.')
    return headers, rows[1:]


def load_feedback(sheet, username):
    headers, rows = _read(sheet)
    latest = {}
    for index, row in enumerate(rows):
        values = dict(zip(headers, row))
        if values.get('username') != username or not str(values.get('note', '')).strip():
            continue
        period = str(values.get('month', '')).strip()
        # ISO months and weekly intervals sort by the period, not sheet row order.
        try:
            start = (date.fromisoformat(period[5:15]) if period.startswith('Week ')
                     else date.fromisoformat(period + '-01'))
        except ValueError:
            start = date.min
        latest[period] = dict(period=period, note=str(values['note']),
                              sort=(start, index))
    return sorted(latest.values(), key=lambda item: item['sort'], reverse=True)


def publish_feedback(sheet, username, period, note):
    username, period, note = (str(value).strip() for value in (username, period, note))
    if not username or username == 'admin' or not period or not note:
        raise ValueError('Select a student and enter a review before publishing.')
    if len(note) > 6000:
        raise ValueError('Keep a review within 6000 characters.')
    if sheet is None:
        raise ValueError('Feedback worksheet is unavailable.')
    headers, rows = _read(sheet)
    # Retry safely if the previous append succeeded but its acknowledgement was lost.
    for row in reversed(rows):
        values = dict(zip(headers, row))
        if values.get('username') == username and values.get('month') == period:
            if values.get('note') == note:
                return 'unchanged'
            break
    if not headers:
        headers = HEADERS[:]
        sheet.update(range_name='A1', values=[headers], value_input_option='RAW')
    record = dict(username=username, month=period, note=note)
    sheet.append_row([record.get(key, '') for key in headers], value_input_option='RAW')
    return 'published'
