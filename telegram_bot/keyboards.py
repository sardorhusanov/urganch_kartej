"""Reply and inline keyboards. Mini App buttons only work in private chats over HTTPS."""
from . import texts


def web_app(path=''):
    return {'url': texts.webapp_url(path)}


def main_menu(admin=False):
    rows = [
        [{'text': texts.BTN_BOOK, 'web_app': web_app('/booking')}],
        [{'text': texts.BTN_MY_ORDERS}, {'text': texts.BTN_PRICES}],
        [{'text': texts.BTN_CONTACT}],
    ]
    if admin:
        rows.append([{'text': texts.BTN_ADMIN_ORDERS}, {'text': texts.BTN_ADMIN_RECEIPTS}])
        rows.append([{'text': texts.BTN_ADMIN_PANEL, 'web_app': web_app('/admin')}])
    return {'keyboard': rows, 'resize_keyboard': True, 'is_persistent': True,
            'input_field_placeholder': 'Bo‘limni tanlang'}


def inline(rows):
    return {'inline_keyboard': [row for row in rows if row]}


def customer_order(order):
    status = texts.receipt_status(order)
    rows = []
    if status in (None, 'rejected'):
        rows.append([{'text': '🧾 Chek yuborish', 'callback_data': f'up:{order["id"]}'}])
    rows.append([{'text': '📱 Ilovada ochish', 'web_app': web_app('/#payment')}])
    return inline(rows)


def admin_order(order):
    status = texts.receipt_status(order)
    rows = [[{'text': '📍 Manzillar xaritada', 'callback_data': f'loc:{order["id"]}'}]]
    route = texts.route_url(order)
    if route:
        rows.append([{'text': '🧭 Yo‘nalish (Google Maps)', 'url': route}])
    if status:
        rows.append([{'text': '🖼 Chekni ko‘rish', 'callback_data': f'rc:{order["id"]}'}])
    if status == 'pending':
        rows.append(review_row(order))
    return inline(rows)


def review_row(order):
    # callback_data is limited to 64 bytes: 32-char order id + receipt id prefix.
    receipt = order['receipt']['id'][:8]
    return [{'text': '✅ Tasdiqlash', 'callback_data': f'ap:{order["id"]}:{receipt}'},
            {'text': '❌ Rad etish', 'callback_data': f'rj:{order["id"]}:{receipt}'}]


def receipt_review(order):
    return inline([review_row(order), [{'text': '📍 Manzillar', 'callback_data': f'loc:{order["id"]}'},
                                       {'text': '📄 Buyurtma', 'callback_data': f'o:{order["id"]}'}]])


def order_list(orders, label):
    return inline([[{'text': label(order), 'callback_data': f'o:{order["id"]}'}] for order in orders])


def force_reply(placeholder):
    return {'force_reply': True, 'input_field_placeholder': placeholder}
