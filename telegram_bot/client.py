"""Minimal Telegram Bot API client built on the standard library (no extra dependencies)."""
import json
import logging
import uuid
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from . import config

log = logging.getLogger('kartej.telegram')
TIMEOUT = 8


class TelegramError(Exception):
    pass


def _url(method):
    return f'https://api.telegram.org/bot{config.token()}/{method}'


def _send(request):
    try:
        with urlopen(request, timeout=TIMEOUT) as response:
            payload = json.loads(response.read())
    except HTTPError as error:
        try:
            payload = json.loads(error.read())
        except ValueError:
            raise TelegramError(f'HTTP {error.code}') from None
    except (URLError, TimeoutError, OSError, ValueError) as error:
        raise TelegramError(str(error)) from None
    if not payload.get('ok'):
        raise TelegramError(payload.get('description', 'Telegram request failed'))
    return payload.get('result')


def call(method, **params):
    params = {key: value for key, value in params.items() if value is not None}
    body = json.dumps(params, ensure_ascii=False).encode()
    return _send(Request(_url(method), data=body, headers={'Content-Type': 'application/json'}))


def send_photo(chat_id, photo, caption='', reply_markup=None, filename='receipt.jpg'):
    """Upload image bytes with multipart/form-data."""
    boundary = uuid.uuid4().hex
    fields = {'chat_id': str(chat_id), 'caption': caption, 'parse_mode': 'HTML'}
    if reply_markup:
        fields['reply_markup'] = json.dumps(reply_markup, ensure_ascii=False)
    parts = []
    for name, value in fields.items():
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode())
    parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="photo"; filename="{filename}"\r\n'
                 f'Content-Type: image/jpeg\r\n\r\n'.encode() + photo + b'\r\n')
    parts.append(f'--{boundary}--\r\n'.encode())
    return _send(Request(_url('sendPhoto'), data=b''.join(parts),
                         headers={'Content-Type': f'multipart/form-data; boundary={boundary}'}))


def download_file(file_id, limit=10 * 1024 * 1024):
    info = call('getFile', file_id=file_id)
    if info.get('file_size', 0) > limit:
        raise TelegramError('File too large')
    url = f'https://api.telegram.org/file/bot{config.token()}/{info["file_path"]}'
    try:
        with urlopen(Request(url), timeout=TIMEOUT) as response:
            data = response.read(limit + 1)
    except (URLError, TimeoutError, OSError) as error:
        raise TelegramError(str(error)) from None
    if len(data) > limit:
        raise TelegramError('File too large')
    return data


def safe(method, **params):
    """Best-effort call: never lets a Telegram outage break bookings or admin actions."""
    try:
        return call(method, **params)
    except TelegramError as error:
        log.warning('Telegram %s failed: %s', method, error)
        return None
