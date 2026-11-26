"""Telegram update handling for customers and admins. Stateless, so it works with serverless webhooks:
multi-step actions (receipt upload, rejection reason) carry the order reference in a force-reply prompt."""
import io
import logging
import re

from fastapi import HTTPException

from . import client, config, keyboards, notify, store, texts

log = logging.getLogger('kartej.telegram')
REFERENCE = re.compile(r'UK-[0-9A-F]{32}')
RECEIPT_ID = re.compile(r'Receipt: ([0-9a-f]{32})')
STATUS_ICON = {None: '🕓', 'pending': '⏳', 'approved': '✅', 'rejected': '❌'}
MAX_LIST = 10


class _Upload:
    """Adapter so Telegram photo bytes go through the same validation as website uploads."""
    def __init__(self, data):
        self.file = io.BytesIO(data)


def send(chat_id, text, markup=None):
    return notify.send(chat_id, text, markup)


def handle(update):
    if 'message' in update:
        on_message(update['message'])
    elif 'callback_query' in update:
        on_callback(update['callback_query'])


# ---------- Messages ----------

def on_message(message):
    if message.get('chat', {}).get('type') != 'private' or 'from' not in message:
        return
    user = message['from']
    chat_id = message['chat']['id']
    admin = config.is_admin(user['id'])
    reply_text = (message.get('reply_to_message') or {}).get('text', '')

    if message.get('photo') or str((message.get('document') or {}).get('mime_type', '')).startswith('image/'):
        return receive_receipt(chat_id, user, message, reply_text)

    text = (message.get('text') or '').strip()
    if admin and texts.REJECT_PROMPT_TAG in reply_text and text:
        return reject_with_reason(chat_id, reply_text, text)

    command = text.split()[0].split('@')[0].lower() if text.startswith('/') else text
    if command in ('/start', '/help', '/menu'):
        if admin:
            # Admin commands can only be scoped to a chat after the admin has started the bot.
            from .setup import ADMIN_COMMANDS
            client.safe('setMyCommands', commands=ADMIN_COMMANDS, scope={'type': 'chat', 'chat_id': chat_id})
        send(chat_id, texts.welcome(user.get('first_name'), admin), keyboards.main_menu(admin))
    elif command == '/id':
        send(chat_id, f'Sizning Telegram ID: <code>{user["id"]}</code>')
    elif command in ('/orders', texts.BTN_MY_ORDERS):
        my_orders(chat_id, user['id'])
    elif command in ('/prices', texts.BTN_PRICES):
        send(chat_id, texts.prices(store.cars(), store.places()))
    elif command in ('/contact', texts.BTN_CONTACT):
        send(chat_id, texts.contact())
    elif admin and command in ('/admin_orders', texts.BTN_ADMIN_ORDERS):
        admin_orders(chat_id)
    elif admin and command in ('/receipts', texts.BTN_ADMIN_RECEIPTS):
        admin_receipts(chat_id)
    elif admin and command in ('/panel', texts.BTN_ADMIN_PANEL):
        send(chat_id, 'Avtomobil qo‘shish, rasm va narxlarni admin panelda boshqaring:',
             keyboards.inline([[{'text': texts.BTN_ADMIN_PANEL, 'web_app': keyboards.web_app('/admin')}]]))
    else:
        send(chat_id, 'Quyidagi menyudan bo‘limni tanlang 👇', keyboards.main_menu(admin))


def my_orders(chat_id, user_id):
    orders = store.user_orders(user_id)[:5]
    if not orders:
        return send(chat_id, 'Hali buyurtmalaringiz yo‘q.\nIlovada buyurtma bering — holati shu yerda ko‘rinadi.',
                    keyboards.inline([[{'text': texts.BTN_BOOK, 'web_app': keyboards.web_app('/booking')}]]))
    for order in orders:
        send(chat_id, texts.order_card(order), keyboards.customer_order(order))


def admin_orders(chat_id):
    orders = store.upcoming_orders()
    if not orders:
        return send(chat_id, 'Yaqin kunlarda buyurtma yo‘q.')

    def label(order):
        icon = STATUS_ICON.get(texts.receipt_status(order), '•')
        return f'{icon} {str(order["date"])[5:]} {order["time"]} · {order["carName"][:28]}'

    send(chat_id, f'📥 <b>Yaqin buyurtmalar</b> ({len(orders)})\n'
                  '🕓 chek kutilmoqda · ⏳ tekshirish kerak · ✅ zaklat to‘langan\n\nTafsilot uchun bosing:',
         keyboards.order_list(orders[:15], label))


def admin_receipts(chat_id):
    orders = store.pending_receipts()
    if not orders:
        return send(chat_id, 'Tekshiriladigan chek yo‘q ✅')
    for order in orders[:MAX_LIST]:
        image = store.receipt_image(order['id'])
        if image:
            notify.send_receipt(chat_id, order, image, '⏳ Tekshirish kerak')
        else:
            send(chat_id, texts.order_card(order, admin=True), keyboards.admin_order(order))


def receive_receipt(chat_id, user, message, reply_text):
    orders = store.awaiting_receipt(store.user_orders(user['id']))
    match = REFERENCE.search(reply_text) if texts.RECEIPT_PROMPT_TAG in reply_text else None
    if match:
        order_id = store.order_id_from_reference(match.group())
        order = next((item for item in store.user_orders(user['id']) if item['id'] == order_id), None)
        if not order:
            return send(chat_id, 'Buyurtma topilmadi.')
    elif len(orders) == 1:
        order = orders[0]
    elif not orders:
        return send(chat_id, 'Chek kutilayotgan buyurtma topilmadi. 📋 Buyurtmalarim bo‘limini tekshiring.')
    else:
        return send(chat_id, 'Chek qaysi buyurtma uchun? Tanlang, so‘ng rasmni qayta yuboring:',
                    keyboards.order_list(orders[:MAX_LIST], lambda o: f'🧾 {texts.short_ref(o)} · {o["date"]}'))

    file_id = message['photo'][-1]['file_id'] if message.get('photo') else message['document']['file_id']
    main = store.backend()
    try:
        image = main.encode_photo(_Upload(client.download_file(file_id)))
        order = main.save_receipt(order['id'], image, lambda db: _owned(main, db, order['id'], user['id']))
    except HTTPException as error:
        return send(chat_id, f'⚠️ {error.detail}')
    except client.TelegramError:
        return send(chat_id, '⚠️ Rasmni yuklab bo‘lmadi. Qayta yuboring.')
    notify.receipt_uploaded(order, image)
    send(chat_id, f'✅ <b>{texts.short_ref(order)}</b> — chek qabul qilindi.\n'
                  'Admin tekshirgach, natijasini shu yerga yuboramiz.')


def _owned(main, db, order_id, user_id):
    order = main.read_one(db, 'orders', order_id)
    if store.owner_id(order) != user_id:
        raise HTTPException(404, 'Buyurtma topilmadi.')
    return order


def reject_with_reason(chat_id, reply_text, reason):
    reference, receipt = REFERENCE.search(reply_text), RECEIPT_ID.search(reply_text)
    if not reference or not receipt:
        return send(chat_id, 'Buyurtmani aniqlab bo‘lmadi.')
    order_id = store.order_id_from_reference(reference.group())
    order = review(order_id, receipt.group(1), 'rejected', reason)
    if isinstance(order, str):
        return send(chat_id, f'⚠️ {order}')
    send(chat_id, f'❌ <b>{texts.short_ref(order)}</b> — chek rad etildi. Mijozga xabar yuborildi.')


def review(order_id, receipt_id, status, reason=''):
    """Reuse the admin API logic so the bot and the dashboard behave identically."""
    main = store.backend()
    try:
        return main.review_receipt(order_id, main.ReceiptDecision(receiptId=receipt_id, status=status, reason=reason))
    except HTTPException as error:
        return error.detail


# ---------- Inline buttons ----------

def on_callback(query):
    user = query.get('from', {})
    message = query.get('message') or {}
    chat_id = message.get('chat', {}).get('id', user.get('id'))
    admin = config.is_admin(user.get('id'))
    kind, _, rest = (query.get('data') or '').partition(':')

    def answer(text='', alert=False):
        client.safe('answerCallbackQuery', callback_query_id=query['id'], text=text, show_alert=alert)

    order_id = rest.split(':')[0]
    order = store.get_order(order_id) if order_id else None
    if not order or not (admin or store.owner_id(order) == user.get('id')):
        return answer('Buyurtma topilmadi.', True)

    if kind == 'o':
        answer()
        markup = keyboards.admin_order(order) if admin else keyboards.customer_order(order)
        send(chat_id, texts.order_card(order, admin=admin), markup)
    elif kind == 'loc':
        answer()
        send_locations(chat_id, order)
    elif kind == 'up':
        if texts.receipt_status(order) not in (None, 'rejected'):
            return answer('Bu buyurtma uchun chek allaqachon yuborilgan.', True)
        answer()
        send(chat_id, texts.receipt_prompt(order), keyboards.force_reply('Chek rasmini yuboring'))
    elif kind in ('rc', 'ap', 'rj') and not admin:
        answer('Faqat admin uchun.', True)
    elif kind == 'rc':
        image = store.receipt_image(order['id'])
        if not image:
            return answer('Chek topilmadi.', True)
        answer()
        notify.send_receipt(chat_id, order, image, '🧾 Chek')
    elif kind in ('ap', 'rj'):
        receipt = order.get('receipt') or {}
        prefix = rest.split(':')[1] if ':' in rest else ''
        if receipt.get('status') != 'pending' or not receipt.get('id', '').startswith(prefix):
            return answer('Chek holati allaqachon yangilangan.', True)
        if kind == 'rj':
            answer()
            return send(chat_id, texts.reject_prompt(order), keyboards.force_reply('Rad etish sababi'))
        result = review(order['id'], receipt['id'], 'approved')
        if isinstance(result, str):
            return answer(result, True)
        answer('Zaklat tasdiqlandi ✅')
        if message.get('message_id'):
            client.safe('editMessageReplyMarkup', chat_id=chat_id, message_id=message['message_id'],
                        reply_markup=keyboards.admin_order(result))
        send(chat_id, f'✅ <b>{texts.short_ref(result)}</b> — zaklat tasdiqlandi. Mijozga xabar yuborildi.')
    else:
        answer()


def send_locations(chat_id, order):
    for which, title in (('start', '📍 Olib ketish'), ('end', '🏁 Borish')):
        location = texts.point(order, which)
        if isinstance(location.get('lat'), (int, float)) and isinstance(location.get('lng'), (int, float)):
            client.safe('sendVenue', chat_id=chat_id, latitude=location['lat'], longitude=location['lng'],
                        title=f'{title} · {texts.short_ref(order)}',
                        address=(location.get('address') or location.get('name') or '')[:250])
        else:
            send(chat_id, f'{title}: manzil koordinatalari yo‘q.')
    route = texts.route_url(order)
    if route:
        send(chat_id, f'🧭 <b>{texts.short_ref(order)}</b> yo‘nalishi:',
             keyboards.inline([[{'text': 'Google Maps’da ochish', 'url': route}]]))
