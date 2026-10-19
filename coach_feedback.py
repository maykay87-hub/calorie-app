"""Human-written reviews, compatible with the existing feedback worksheet.

No AI generation or automatic review delivery. Append revisions to preserve history.
"""
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

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
    if headers.count('published_at') > 1 or any(len(row) > len(headers) for row in rows[1:]):
        raise ValueError('Unexpected feedback columns; existing data was preserved.')
    return headers, rows[1:]


def load_feedback(sheet, username):
    headers, rows = _read(sheet)
    reviews = []
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
        published = str(values.get('published_at', '')).strip()
        display_time = ''
        posted = datetime.combine(start, datetime.min.time(), tzinfo=timezone.utc)
        if published:
            try:
                posted = datetime.fromisoformat(published)
                if posted.tzinfo is None:
                    posted = posted.replace(tzinfo=ZoneInfo('Asia/Kuala_Lumpur'))
                display_time = posted.astimezone(ZoneInfo('Asia/Kuala_Lumpur')).strftime('%Y-%m-%d %H:%M')
            except (ValueError, OverflowError):
                posted = datetime.combine(start, datetime.min.time(), tzinfo=timezone.utc)
        reviews.append(dict(period=period, note=str(values['note']),
                            published_at=display_time, key=index + 2,
                            sort=(posted, index)))
    return sorted(reviews, key=lambda item: item['sort'], reverse=True)


def publish_feedback(sheet, username, period, note):
    username, period, note = (str(value).strip() for value in (username, period, note))
    if not username or username == 'admin' or not period or not note:
        raise ValueError('Select a student and enter a review before publishing.')
    if len(note) > 6000:
        raise ValueError('Keep a review within 6000 characters.')
    if sheet is None:
        raise ValueError('Feedback worksheet is unavailable.')
    headers, rows = _read(sheet)
    # An unchanged serial retry does not create a duplicate; supplements append.
    for row in reversed(rows):
        values = dict(zip(headers, row))
        if values.get('username') == username and values.get('month') == period:
            if values.get('note') == note:
                return 'unchanged'
            break
    if not headers or 'published_at' not in headers:
        headers = (headers or HEADERS[:]) + ['published_at']
        sheet.update(range_name='A1', values=[headers], value_input_option='RAW')
    record = dict(username=username, month=period, note=note,
                  published_at=datetime.now(ZoneInfo('Asia/Kuala_Lumpur')).isoformat(timespec='seconds'))
    sheet.append_row([record.get(key, '') for key in headers], value_input_option='RAW')
    return 'published'
