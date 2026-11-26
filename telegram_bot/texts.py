"""Uzbek message texts and order formatting for the bot chat (HTML parse mode)."""
from html import escape

from . import config

PHONE = '+998 93 465 05 05'
INSTAGRAM = 'https://www.instagram.com/urganch_kartej_xorazm/'

# Reply-keyboard button labels double as commands, so keep them in one place.
BTN_BOOK = '🚘 Buyurtma berish'
BTN_MY_ORDERS = '📋 Buyurtmalarim'
BTN_PRICES = '💰 Narxlar'
BTN_CONTACT = '📞 Aloqa'
BTN_ADMIN_ORDERS = '📥 Buyurtmalar'
BTN_ADMIN_RECEIPTS = '⏳ Zaklat tekshiruvi'
BTN_ADMIN_PANEL = '🛠 Admin panel'

RECEIPT_LABELS = {
    None: '🕓 Chek kutilmoqda',
    'pending': '⏳ Chek tekshirilmoqda',
    'approved': '✅ Zaklat tasdiqlandi',
    'rejected': '❌ Chek rad etildi',
}


def money(amount):
    return f'{amount:,}'.replace(',', ' ') + ' so‘m'


def short_ref(order):
    return order['reference'][:11]


def receipt_status(order):
    return (order.get('receipt') or {}).get('status')


def point(order, which):
    """Exact customer endpoint when confirmed, otherwise the tariff point."""
    return order.get('exact' + which.title()) or order.get(which) or {}


def place_line(location):
    text = escape(location.get('address') or location.get('name') or '—')
    area = ((location.get('classification') or {}).get('area') or {}).get('name')
    return f'{text} <i>({escape(area)})</i>' if area else text


def route_url(order):
    start, end = point(order, 'start'), point(order, 'end')
    if not all(isinstance(p.get(k), (int, float)) for p in (start, end) for k in ('lat', 'lng')):
        return None
    return ('https://www.google.com/maps/dir/?api=1&travelmode=driving'
            f'&origin={start["lat"]},{start["lng"]}&destination={end["lat"]},{end["lng"]}')


def order_card(order, admin=False, title=None):
    status = receipt_status(order)
    lines = []
    if title:
        lines.append(f'<b>{escape(title)}</b>')
    lines.append(f'🧾 <b>{escape(short_ref(order))}</b> · {RECEIPT_LABELS.get(status, status)}')
    if admin:
        lines.append(f'👤 {escape(order.get("customerName", ""))} · <code>{escape(order.get("phone", ""))}</code>')
        telegram = order.get('telegram') or {}
        if telegram.get('username'):
            lines.append(f'💬 @{escape(telegram["username"])}')
    lines.append(f'🚘 {escape(order.get("carName", ""))}')
    lines.append(f'📅 {escape(str(order.get("date", "")))} · {escape(str(order.get("time", "")))}')
    lines.append(f'📍 <b>Olib ketish:</b> {place_line(point(order, "start"))}')
    lines.append(f'🏁 <b>Borish:</b> {place_line(point(order, "end"))}')
    lines.append('')
    lines.append(f'💰 Jami: <b>{money(order["total"])}</b>')
    lines.append(f'🔐 Zaklat (20%): <b>{money(order["deposit"])}</b>')
    lines.append(f'💵 To‘langan: {money(order["paid"])} · Qolgan: {money(order["total"] - order["paid"])}')
    if status == 'rejected' and (order.get('receipt') or {}).get('reason'):
        lines.append(f'ℹ️ Sabab: {escape(order["receipt"]["reason"])}')
    return '\n'.join(lines)


def prices(cars, places):
    names = {place['name']: place for place in places}
    lines = ['💰 <b>Narxlar</b> — haydovchi bilan, bir yo‘nalish uchun', '']
    for car in cars:
        lines.append(f'🚘 <b>{escape(car["name"])}</b> · {escape(car.get("category", ""))} · {escape(car.get("detail", ""))}')
        rates = car.get('routeRates') or []
        if not rates:
            lines.append('   Tarif kiritilmagan')
        for rate in sorted(rates, key=lambda r: r['amount']):
            start = names.get(rate['from'], {}).get('name', rate['from'])
            end = names.get(rate['to'], {}).get('name', rate['to'])
            lines.append(f'   {escape(start)} → {escape(end)}: <b>{money(rate["amount"])}</b>')
        lines.append('')
    lines.append('Zaklat — jami narxning 20%. Qolgani xizmat kuni to‘lanadi.')
    return '\n'.join(lines)


def welcome(first_name, admin):
    name = escape(first_name or 'mehmon')
    text = (f'Assalomu alaykum, {name}! 👋\n\n'
            '<b>Urganch Kartej</b> — Xorazm bo‘ylab kartej xizmatlari: to‘ylar, mehmonlar va biznes safarlari uchun.\n\n'
            f'• {BTN_BOOK} — ilovada avtomobil va yo‘nalishni tanlang\n'
            f'• {BTN_MY_ORDERS} — buyurtma va zaklat holati\n'
            f'• {BTN_PRICES} — avtomobillar narxi\n'
            f'• {BTN_CONTACT} — biz bilan bog‘lanish')
    if admin:
        text += ('\n\n<b>Admin:</b>\n'
                 f'• {BTN_ADMIN_ORDERS} — yaqin buyurtmalar va manzillar\n'
                 f'• {BTN_ADMIN_RECEIPTS} — tekshirilishi kerak bo‘lgan cheklar\n'
                 f'• {BTN_ADMIN_PANEL} — avtomobil qo‘shish va narxlar')
    return text


def contact():
    # <code> makes the number copy with one tap in Telegram.
    return (f'📞 <b>Aloqa</b>\n\nTelefon: <code>{PHONE}</code>\nInstagram: {INSTAGRAM}\n\n'
            'Raqamni nusxalash uchun ustiga bosing. Savollaringiz bo‘lsa, qo‘ng‘iroq qiling yoki shu yerga yozing.')


RECEIPT_PROMPT_TAG = 'Chek:'


def receipt_prompt(order):
    # The reference inside this text lets a stateless webhook match the reply photo to the order.
    return (f'🧾 {RECEIPT_PROMPT_TAG} <b>{escape(order["reference"])}</b>\n\n'
            f'Zaklat: <b>{money(order["deposit"])}</b>\n'
            'To‘lov chekining rasmini shu xabarga javob qilib yuboring.\n\n'
            '<i>Sinov rejimi: demo kartaga pul yubormang, namunaviy rasm yuboring.</i>')


REJECT_PROMPT_TAG = 'Rad etish:'


def reject_prompt(order):
    return (f'❌ {REJECT_PROMPT_TAG} <b>{escape(order["reference"])}</b>\n'
            f'Receipt: {escape(order["receipt"]["id"])}\n\n'
            'Rad etish sababini shu xabarga javob qilib yozing.')


def webapp_url(path=''):
    return config.public_url() + path

