"""Bot settings, read from the environment on every call so tests and deployments can change them."""
import os

DEFAULT_PUBLIC_URL = 'https://urganch-kartej.vercel.app'


def token():
    return os.getenv('TELEGRAM_BOT_TOKEN', '').strip()


def enabled():
    return bool(token())


def webhook_secret():
    return os.getenv('TELEGRAM_WEBHOOK_SECRET', '').strip()


def admin_ids():
    """Telegram user IDs allowed to manage orders, e.g. KARTEJ_ADMIN_TELEGRAM_IDS=12345,67890."""
    raw = os.getenv('KARTEJ_ADMIN_TELEGRAM_IDS', '')
    return {int(part) for part in raw.replace(' ', '').split(',') if part.lstrip('-').isdigit()}


def is_admin(user_id):
    return user_id in admin_ids()


def public_url():
    return os.getenv('KARTEJ_PUBLIC_URL', DEFAULT_PUBLIC_URL).rstrip('/')
