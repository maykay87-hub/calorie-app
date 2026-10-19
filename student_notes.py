"""Append-only supplementary notes and bounded private attachments.

Metadata and binary chunks use separate worksheets. No public download URLs.
Attachments are fetched by their stored row range only after account validation.
"""
import base64
import hashlib
import json
import re
from datetime import date, datetime
from zoneinfo import ZoneInfo

NOTE_HEADERS = ['note_id', 'username', 'Date', 'Meal', 'Remarks', 'files_json', 'created_at', 'needs_calories']
FILE_HEADERS = ['file_id', 'username', 'note_id', 'part', 'payload']
MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_FILES = 2
CHUNK_SIZE = 30000


def _rows(sheet, headers):
    if sheet is None:
        return []
    rows = sheet.get_all_values()
    if not rows or rows == [[]]:
        return []
    if rows[0] != headers:
        raise ValueError('Supplementary record format needs review; nothing was changed.')
    return rows[1:]


def _initialize(sheet, headers):
    rows = sheet.get(f'A1:{chr(64 + len(headers))}1')
    if not rows or rows == [[]]:
        sheet.update(range_name='A1', values=[headers], value_input_option='RAW')
    elif rows[0] != headers:
        raise ValueError('Supplementary record format needs review; nothing was changed.')


def _file(name, data):
    if not isinstance(data, bytes) or not data or len(data) > MAX_FILE_BYTES:
        raise ValueError('Each attachment must be non-empty and no larger than 2 MB.')
    clean = str(name).replace('\\', '/').rsplit('/', 1)[-1]
    clean = ''.join(c for c in clean if c.isprintable()).strip()[:120]
    extension = clean.rsplit('.', 1)[-1].lower()
    signatures = {
        'jpg': ('image/jpeg', data.startswith(b'\xff\xd8\xff')),
        'jpeg': ('image/jpeg', data.startswith(b'\xff\xd8\xff')),
        'png': ('image/png', data.startswith(b'\x89PNG\r\n\x1a\n')),
        'webp': ('image/webp', data[:4] == b'RIFF' and data[8:12] == b'WEBP'),
        'pdf': ('application/pdf', data.startswith(b'%PDF-')),
    }
    mime, valid = signatures.get(extension, ('', False))
    if not valid:
        raise ValueError('Please attach a JPG, PNG, WebP image or PDF with the matching file format.')
    return dict(name=clean, mime=mime, size=len(data), sha256=hashlib.sha256(data).hexdigest(), data=data)


def prepare_note(username, day, meal, remarks, uploads=(), needs_calories=True):
    day = date.fromisoformat(str(day)).isoformat()
    remarks = str(remarks).strip()
    if not username or username == 'admin' or meal not in {'Breakfast', 'Lunch', 'Dinner', 'Snack', 'Other'}:
        raise ValueError('Choose a meal for the supplementary record.')
    if len(remarks) > 2000:
        raise ValueError('Keep your remarks within 2000 characters.')
    if len(uploads) > MAX_FILES:
        raise ValueError('Attach up to two files per supplementary record.')
    files = [_file(name, data) for name, data in uploads]
    if not remarks and not files:
        raise ValueError('Write a note or attach a photo/file before saving.')
    identity = [username, day, meal, remarks, bool(needs_calories),
                [{k: f[k] for k in ('name', 'size', 'sha256')} for f in files]]
    note_id = hashlib.sha256(json.dumps(identity, ensure_ascii=False).encode()).hexdigest()
    return dict(note_id=note_id, username=username, Date=day, Meal=meal, Remarks=remarks,
                needs_calories=bool(needs_calories), files=files)


def load_notes(sheet, username, day=None):
    notes = []
    for row in _rows(sheet, NOTE_HEADERS):
        values = dict(zip(NOTE_HEADERS, row))
        if values.get('username') != username or (day is not None and values.get('Date') != str(day)):
            continue
        try:
            if len(row) != len(NOTE_HEADERS) or values.get('Meal') not in {'Breakfast', 'Lunch', 'Dinner', 'Snack', 'Other'} or not re.fullmatch(r'[a-f0-9]{64}', str(values.get('note_id', ''))):
                raise ValueError('Incomplete supplementary record.')
            date.fromisoformat(values['Date'])
            files = json.loads(values.get('files_json') or '[]')
            if not isinstance(files, list) or len(files) > MAX_FILES:
                raise ValueError('Invalid attachment metadata.')
            for file in files:
                if (not isinstance(file, dict)
                        or not {'name', 'mime', 'size', 'sha256', 'file_id', 'start', 'parts'}.issubset(file)
                        or not isinstance(file['name'], str) or not 1 <= len(file['name']) <= 120
                        or file['mime'] not in {'image/jpeg', 'image/png', 'image/webp', 'application/pdf'}
                        or not isinstance(file['size'], int) or isinstance(file['size'], bool)
                        or not 0 < file['size'] <= MAX_FILE_BYTES
                        or not isinstance(file['sha256'], str) or not re.fullmatch(r'[a-f0-9]{64}', file['sha256'])
                        or not isinstance(file['file_id'], str) or not re.fullmatch(r'[a-f0-9]{64}', file['file_id'])):
                    raise ValueError('Invalid attachment metadata.')
        except (KeyError, ValueError, TypeError):
            raise ValueError('A supplementary record needs review; existing data is preserved.') from None
        values['files'] = files
        values['needs_calories'] = str(values.get('needs_calories', '')).lower() in {'true', '1', 'yes'}
        notes.append(values)
    # Identical retries may yield duplicate physical rows under concurrent requests.
    latest = {n['note_id']: n for n in notes}
    return sorted(latest.values(), key=lambda n: (n['Date'], n.get('created_at', '')), reverse=True)


def save_note(note_sheet, file_sheet, prepared):
    existing = load_notes(note_sheet, prepared['username'])
    if any(n['note_id'] == prepared['note_id'] for n in existing):
        return 'unchanged'
    _initialize(note_sheet, NOTE_HEADERS)
    manifests = []
    if prepared['files']:
        if file_sheet is None:
            raise ValueError('Attachment storage is unavailable; your input has not been saved.')
        _initialize(file_sheet, FILE_HEADERS)
        chunks, spans = [], []
        for index, file in enumerate(prepared['files']):
            file_id = hashlib.sha256(f"{prepared['note_id']}:{index}".encode()).hexdigest()
            encoded = base64.b64encode(file['data']).decode('ascii')
            parts = [encoded[i:i + CHUNK_SIZE] for i in range(0, len(encoded), CHUNK_SIZE)]
            spans.append((len(chunks), len(parts), file_id, file))
            chunks.extend([[file_id, prepared['username'], prepared['note_id'], str(i), part]
                           for i, part in enumerate(parts)])
        result = file_sheet.append_rows(chunks, value_input_option='RAW')
        updated_range = result.get('updates', {}).get('updatedRange', '')
        match = re.search(r'!A(\d+):E(\d+)$', updated_range)
        if not match or int(match[2]) - int(match[1]) + 1 != len(chunks):
            raise ValueError('Attachment save was not confirmed; please retry with your input kept here.')
        start_row = int(match[1])
        for offset, count, file_id, file in spans:
            manifests.append({**{k: file[k] for k in ('name', 'mime', 'size', 'sha256')},
                              'file_id': file_id, 'start': start_row + offset, 'parts': count})
    # The note is the commit marker: orphan chunks after failure are never listed.
    record = {**prepared, 'files_json': json.dumps(manifests, ensure_ascii=False),
              'created_at': datetime.now(ZoneInfo('Asia/Kuala_Lumpur')).isoformat(timespec='seconds'),
              'needs_calories': str(prepared['needs_calories']).lower()}
    note_sheet.append_row([record[h] for h in NOTE_HEADERS], value_input_option='RAW')
    return 'saved'


def download_attachment(note_sheet, file_sheet, username, note_id, file_id):
    note = next((n for n in load_notes(note_sheet, username) if n['note_id'] == note_id), None)
    meta = next((f for f in note['files'] if f.get('file_id') == file_id), None) if note else None
    if meta is None:
        raise ValueError('Attachment not available for this account.')
    start, count = meta.get('start'), meta.get('parts')
    if (not isinstance(start, int) or isinstance(start, bool) or start < 2
            or not isinstance(count, int) or isinstance(count, bool) or not 1 <= count <= 100):
        raise ValueError('Attachment metadata needs review.')
    rows = file_sheet.get(f'A{start}:E{start + count - 1}')
    if len(rows) != count:
        raise ValueError('Attachment is incomplete; please retry.')
    encoded = []
    for i, row in enumerate(rows):
        if len(row) != 5 or row[:4] != [file_id, username, note_id, str(i)]:
            raise ValueError('Attachment could not be verified.')
        encoded.append(row[4])
    try:
        content = base64.b64decode(''.join(encoded), validate=True)
    except ValueError:
        raise ValueError('Attachment could not be decoded.') from None
    if len(content) != meta['size'] or hashlib.sha256(content).hexdigest() != meta['sha256']:
        raise ValueError('Attachment could not be verified.')
    return content, meta


def mark_note_counted(note_sheet, username, note_id):
    for index, row in enumerate(_rows(note_sheet, NOTE_HEADERS)):
        values = dict(zip(NOTE_HEADERS, row))
        if values.get('username') == username and values.get('note_id') == note_id:
            note_sheet.update(range_name=f'H{index + 2}', values=[['false']], value_input_option='RAW')
            return
    raise ValueError('Supplementary record is not available for this account.')


def annotate_energy_status(records, notes):
    pending = {}
    for note in notes or []:
        if note['needs_calories']:
            pending[note['Date']] = pending.get(note['Date'], 0) + 1
    result = []
    for row in records:
        item = dict(row, Pending_calorie_notes=None if notes is None else pending.get(row['Date'], 0),
                    Energy_complete=None if notes is None else pending.get(row['Date'], 0) == 0)
        if item['Energy_complete'] is not True and 'Protein' in item:
            # Known logged protein remains available, but is not a complete-day total.
            item['Protein'] = None
        result.append(item)
    return result
