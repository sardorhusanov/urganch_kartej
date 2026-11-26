"""One-time bot setup: webhook, command menu and Mini App menu button.

    uv run --env-file .env.local python -m telegram_bot.setup
"""
import sys

from . import client, config

CUSTOMER_COMMANDS = [
    {'command': 'start', 'description': 'Bosh menyu'},
    {'command': 'orders', 'description': 'Buyurtmalarim va zaklat holati'},
    {'command': 'prices', 'description': 'Avtomobillar narxi'},
    {'command': 'contact', 'description': 'Aloqa'},
]
ADMIN_COMMANDS = CUSTOMER_COMMANDS + [
    {'command': 'admin_orders', 'description': 'Yaqin buyurtmalar va manzillar'},
    {'command': 'receipts', 'description': 'Tekshiriladigan cheklar'},
    {'command': 'panel', 'description': 'Admin panel'},
]


def main():
    if not config.enabled() or not config.webhook_secret():
        sys.exit('Set TELEGRAM_BOT_TOKEN and TELEGRAM_WEBHOOK_SECRET first.')
    url = config.public_url()
    me = client.call('getMe')
    client.call('setWebhook', url=f'{url}/api/telegram/webhook', secret_token=config.webhook_secret(),
                allowed_updates=['message', 'callback_query'], drop_pending_updates=False)
    client.call('setMyCommands', commands=CUSTOMER_COMMANDS)
    for admin in config.admin_ids():
        client.safe('setMyCommands', commands=ADMIN_COMMANDS, scope={'type': 'chat', 'chat_id': admin})
    client.call('setChatMenuButton', menu_button={'type': 'web_app', 'text': 'Ilova', 'web_app': {'url': url}})
    client.call('setMyDescription', description=(
        'Urganch Kartej — Xorazm bo‘ylab haydovchili avtomobillar: to‘ylar, mehmonlar va biznes safarlari. '
        'Ilovada avtomobil tanlang, buyurtma va zaklat holatini shu yerda kuzating.'))
    client.call('setMyShortDescription', short_description='Xorazm bo‘ylab haydovchili avtomobillar')
    print(f'@{me["username"]} is ready: webhook {url}/api/telegram/webhook, admins {sorted(config.admin_ids()) or "none"}')


if __name__ == '__main__':
    main()
