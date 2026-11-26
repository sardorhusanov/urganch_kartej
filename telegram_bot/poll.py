"""Local development without a public webhook: long-poll Telegram and handle updates in this process.

    uv run --env-file .env.local python -m telegram_bot.poll

Polling removes the webhook; run `python -m telegram_bot.setup` again before using the deployed bot.
"""
import logging
import time

from . import client, config, handlers


def main():
    logging.basicConfig(level=logging.INFO)
    if not config.enabled():
        raise SystemExit('Set TELEGRAM_BOT_TOKEN first.')
    from backend import main as backend
    backend.initialize(backend.app)
    client.call('deleteWebhook')
    print('Polling Telegram… press Ctrl+C to stop.')
    offset = None
    while True:
        try:
            client.TIMEOUT = 40
            updates = client.call('getUpdates', offset=offset, timeout=30, allowed_updates=['message', 'callback_query'])
        except client.TelegramError as error:
            logging.warning('getUpdates failed: %s', error)
            time.sleep(3)
            continue
        finally:
            client.TIMEOUT = 8
        for update in updates:
            offset = update['update_id'] + 1
            try:
                handlers.handle(update)
            except Exception:  # noqa: BLE001
                logging.exception('Update failed')


if __name__ == '__main__':
    main()
