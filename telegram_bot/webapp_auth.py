"""Validate Telegram Mini App initData (https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app)."""
import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl

from . import config

MAX_AGE = 24 * 3600


def validate_init_data(init_data, max_age=MAX_AGE):
    """Return the Telegram user dict when initData is authentic and fresh, otherwise None."""
    bot_token = config.token()
    if not init_data or not bot_token or len(init_data) > 4096:
        return None
    try:
        fields = dict(parse_qsl(init_data, strict_parsing=True))
    except ValueError:
        return None
    received = fields.pop('hash', '')
    check_string = '\n'.join(f'{key}={value}' for key, value in sorted(fields.items()))
    secret = hmac.new(b'WebAppData', bot_token.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, received):
        return None
    try:
        if time.time() - int(fields.get('auth_date', '0')) > max_age:
            return None
        user = json.loads(fields.get('user', 'null'))
    except ValueError:
        return None
    return user if isinstance(user, dict) and isinstance(user.get('id'), int) else None
