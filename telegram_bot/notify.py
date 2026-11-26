"""Push notifications from the booking flow. Every function is a no-op without a bot token and
never raises, so Telegram problems can't break bookings or receipt reviews."""
import logging

from . import client, config, keyboards, store, texts

log = logging.getLogger('kartej.telegram')
CAPTION_LIMIT = 1024


def _guard(function):
    def wrapper(*args, **kwargs):
        if not config.enabled():
            return
        try:
            function(*args, **kwargs)
        except Exception:  # noqa: BLE001 - notifications are best effort by design.
            log.exception('Telegram notification failed')
    return wrapper


def send(chat_id, text, markup=None):
    return client.safe('sendMessage', chat_id=chat_id, text=text, parse_mode='HTML', reply_markup=markup,
                       link_preview_options={'is_disabled': True})


def send_receipt(chat_id, order, image, title):
    caption = texts.order_card(order, admin=True, title=title)
    markup = keyboards.receipt_review(order) if texts.receipt_status(order) == 'pending' else None
    photo = store.to_jpeg(image)
    try:
        if len(caption) <= CAPTION_LIMIT:
            return client.send_photo(chat_id, photo, caption, markup)
        client.send_photo(chat_id, photo, f'🧾 {texts.short_ref(order)}')
        return send(chat_id, caption, markup)
    except client.TelegramError as error:
        log.warning('Telegram sendPhoto failed: %s', error)


@_guard
def order_created(order):
    for admin in config.admin_ids():
        send(admin, texts.order_card(order, admin=True, title='🆕 Yangi buyurtma'), keyboards.admin_order(order))
    customer = store.owner_id(order)
    if customer:
        send(customer, texts.order_card(order, title='✅ Buyurtmangiz qabul qilindi') +
             '\n\nZaklatni to‘lab, chek rasmini yuboring — admin tasdiqlagach band qilinadi.',
             keyboards.customer_order(order))


@_guard
def receipt_uploaded(order, image):
    for admin in config.admin_ids():
        send_receipt(admin, order, image, '🧾 Yangi chek — tekshiring')


@_guard
def receipt_reviewed(order):
    customer = store.owner_id(order)
    if not customer:
        return
    if texts.receipt_status(order) == 'approved':
        send(customer, f'✅ <b>{texts.short_ref(order)}</b> — zaklat tasdiqlandi!\n'
                       f'Qolgan {texts.money(order["total"] - order["paid"])} xizmat kuni to‘lanadi.\n'
                       'Rahmat! Haydovchi belgilangan vaqtda yetib boradi.')
    else:
        send(customer, texts.order_card(order, title='❌ Chek rad etildi') + '\n\nIltimos, yangi chek yuboring.',
             keyboards.customer_order(order))
