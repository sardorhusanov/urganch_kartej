import hashlib
import hmac
import io
import json
import os
import secrets
import tempfile
import time
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlencode

from fastapi.testclient import TestClient
from PIL import Image

from telegram_bot import webapp_auth

TOKEN = '123456:TEST-token'
SECRET = 'webhook-secret'
ADMIN, CUSTOMER, STRANGER = 1001, 2002, 3003


def init_data(user_id, first_name='Ali', auth_date=None, token=TOKEN):
    fields = {'auth_date': str(int(auth_date or time.time())), 'query_id': 'AAE',
              'user': json.dumps({'id': user_id, 'first_name': first_name, 'username': f'user{user_id}'})}
    check = '\n'.join(f'{k}={v}' for k, v in sorted(fields.items()))
    key = hmac.new(b'WebAppData', token.encode(), hashlib.sha256).digest()
    fields['hash'] = hmac.new(key, check.encode(), hashlib.sha256).hexdigest()
    return urlencode(fields)


def png():
    output = io.BytesIO()
    Image.new('RGB', (40, 30), 'white').save(output, 'PNG')
    return output.getvalue()


class InitDataTests(unittest.TestCase):
    def test_signature_and_freshness(self):
        with patch.dict(os.environ, {'TELEGRAM_BOT_TOKEN': TOKEN}):
            self.assertEqual(webapp_auth.validate_init_data(init_data(7))['id'], 7)
            self.assertIsNone(webapp_auth.validate_init_data(init_data(7, token='999:other')))
            self.assertIsNone(webapp_auth.validate_init_data(init_data(7).replace('Ali', 'Eve')))
            self.assertIsNone(webapp_auth.validate_init_data(init_data(7, auth_date=time.time() - 3 * 86400)))
        with patch.dict(os.environ, {'TELEGRAM_BOT_TOKEN': ''}):
            self.assertIsNone(webapp_auth.validate_init_data(init_data(7)))


class TelegramBotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import backend.main as main
        cls.main = main
        cls.directory = tempfile.TemporaryDirectory()
        cls.password = secrets.token_urlsafe(24)
        cls.environment = patch.dict(os.environ, {
            'KARTEJ_ADMIN_PASSWORD': cls.password, 'TELEGRAM_BOT_TOKEN': TOKEN, 'TELEGRAM_WEBHOOK_SECRET': SECRET,
            'KARTEJ_ADMIN_TELEGRAM_IDS': f'{ADMIN}', 'KARTEJ_PUBLIC_URL': 'https://kartej.example'}, clear=True)
        cls.environment.start()
        cls.data_patch = patch.object(main, 'DATA', Path(cls.directory.name)); cls.data_patch.start()
        main._initialized = False
        cls.client = TestClient(main.app); cls.client.__enter__()
        token = cls.client.post('/api/admin/login', json={'username': 'admin', 'password': cls.password}).json()['token']
        cls.admin_headers = {'Authorization': 'Bearer ' + token}
        cls.client.put('/api/admin/cars/malibu/route', headers=cls.admin_headers,
                       json={'start': 'Urganch', 'end': 'Xiva', 'amount': 500000})

    @classmethod
    def tearDownClass(cls):
        cls.client.__exit__(None, None, None)
        cls.main._initialized = False
        cls.data_patch.stop(); cls.environment.stop(); cls.directory.cleanup()

    def setUp(self):
        self.sent = []
        self.photos = []
        self.patches = [
            patch('telegram_bot.client.call', side_effect=self.fake_call),
            patch('telegram_bot.client.send_photo', side_effect=lambda chat, photo, caption='', markup=None, **_: self.photos.append((chat, caption, markup))),
            patch('telegram_bot.client.download_file', return_value=png()),
        ]
        for item in self.patches:
            item.start()

    def tearDown(self):
        for item in self.patches:
            item.stop()

    def fake_call(self, method, **params):
        self.sent.append((method, params))
        return {'message_id': 1} if method != 'getFile' else {}

    def messages(self, chat_id):
        return [p for m, p in self.sent if m == 'sendMessage' and p['chat_id'] == chat_id]

    def webhook(self, update, secret=SECRET):
        return self.client.post('/api/telegram/webhook', json=update, headers={'X-Telegram-Bot-Api-Secret-Token': secret})

    def message(self, user_id, text=None, **extra):
        message = {'message_id': 5, 'chat': {'id': user_id, 'type': 'private'}, 'from': {'id': user_id, 'first_name': 'Ali'}}
        if text is not None:
            message['text'] = text
        return self.webhook({'update_id': 1, 'message': {**message, **extra}})

    def press(self, user_id, data):
        return self.webhook({'update_id': 2, 'callback_query': {'id': 'cb', 'data': data, 'from': {'id': user_id},
                                                                 'message': {'message_id': 9, 'chat': {'id': user_id}}}})

    def order(self, user_id=CUSTOMER):
        places = {p['name']: p for p in self.client.get('/api/places').json()}
        payload = {'carId': 'malibu', 'customerName': 'Bot Test', 'phone': '+998901234567',
                   'date': str((datetime.now() + timedelta(days=3)).date()), 'time': '12:00',
                   'start': places['Urganch'], 'end': places['Xiva'], 'expectedTotal': 500000,
                   'exactStart': {'lat': 41.5506, 'lng': 60.6317, 'address': 'Urganch, Al-Xorazmiy 10'},
                   'exactEnd': {'lat': 41.3783, 'lng': 60.3639, 'address': 'Xiva, Ichan qal’a'}}
        headers = {'X-Telegram-Init-Data': init_data(user_id)} if user_id else {}
        response = self.client.post('/api/orders', json=payload, headers=headers)
        self.assertEqual(response.status_code, 201, response.text)
        return self.stored(response.json()['id'])

    def send_receipt(self, order, file_id='large'):
        """Tap "Chek yuborish", then reply to the bot's prompt with a photo, like a real customer."""
        self.press(CUSTOMER, f'up:{order["id"]}')
        prompt = self.messages(CUSTOMER)[-1]['text'].replace('<b>', '').replace('</b>', '')
        self.message(CUSTOMER, photo=[{'file_id': 'small'}, {'file_id': file_id}], reply_to_message={'text': prompt})

    def stored(self, order_id):
        with self.main.database() as db:
            return self.main.read_one(db, 'orders', order_id)

    def test_plain_photo_with_several_unpaid_orders_asks_which_one(self):
        self.order(); self.order()
        self.message(CUSTOMER, photo=[{'file_id': 'large'}])
        self.assertIn('qaysi buyurtma', self.messages(CUSTOMER)[-1]['text'])

    def test_id_command(self):
        self.message(STRANGER, '/id')
        self.assertIn(str(STRANGER), self.messages(STRANGER)[-1]['text'])

    def test_webhook_requires_secret(self):
        self.assertEqual(self.webhook({'update_id': 1}, secret='wrong').status_code, 403)
        self.assertEqual(self.webhook({'update_id': 1}).status_code, 200)

    def test_mini_app_order_is_linked_and_admin_gets_locations(self):
        order = self.order()
        self.assertEqual(order['telegram']['userId'], CUSTOMER)
        admin_message = self.messages(ADMIN)[-1]
        self.assertIn('Yangi buyurtma', admin_message['text'])
        self.assertIn('Al-Xorazmiy 10', admin_message['text'])
        self.assertIn('100 000 so‘m', admin_message['text'])
        buttons = [b for row in admin_message['reply_markup']['inline_keyboard'] for b in row]
        self.assertTrue(any('google.com/maps/dir' in b.get('url', '') for b in buttons))
        self.assertIn('qabul qilindi', self.messages(CUSTOMER)[-1]['text'])
        self.sent.clear()
        self.press(ADMIN, f'loc:{order["id"]}')
        venues = [p for m, p in self.sent if m == 'sendVenue']
        self.assertEqual([(v['latitude'], v['longitude']) for v in venues], [(41.5506, 60.6317), (41.3783, 60.3639)])

    def test_website_order_without_telegram_still_works(self):
        order = self.order(user_id=None)
        self.assertNotIn('telegram', order)
        forged = self.client.post('/api/orders', json={}, headers={'X-Telegram-Init-Data': 'hash=forged'})
        self.assertEqual(forged.status_code, 422)

    def test_menus_and_customer_privacy(self):
        self.message(ADMIN, '/start')
        admin_keys = json.dumps(self.messages(ADMIN)[-1]['reply_markup'], ensure_ascii=False)
        self.assertIn('Zaklat tekshiruvi', admin_keys)
        self.assertIn('https://kartej.example/admin', admin_keys)
        self.message(CUSTOMER, '/start')
        self.assertNotIn('Zaklat tekshiruvi', json.dumps(self.messages(CUSTOMER)[-1]['reply_markup'], ensure_ascii=False))
        order = self.order()
        self.sent.clear()
        self.message(STRANGER, '📋 Buyurtmalarim')
        self.assertIn('Hali buyurtmalaringiz yo‘q', self.messages(STRANGER)[-1]['text'])
        self.press(STRANGER, f'o:{order["id"]}')
        self.assertTrue(any(m == 'answerCallbackQuery' and p.get('show_alert') for m, p in self.sent))
        self.message(CUSTOMER, '📋 Buyurtmalarim')
        self.assertTrue(any(order['reference'][:11] in p['text'] for p in self.messages(CUSTOMER)))
        self.message(CUSTOMER, '💰 Narxlar')
        self.assertIn('Urganch → Xiva: <b>500 000 so‘m</b>', self.messages(CUSTOMER)[-1]['text'])

    def test_receipt_photo_then_admin_approves(self):
        order = self.order()
        self.send_receipt(order)
        self.assertEqual(self.stored(order['id'])['receipt']['status'], 'pending')
        self.assertEqual(self.photos[-1][0], ADMIN)
        self.assertIn('Yangi chek', self.photos[-1][1])
        receipt = self.stored(order['id'])['receipt']['id']
        self.press(CUSTOMER, f'ap:{order["id"]}:{receipt[:8]}')
        self.assertEqual(self.stored(order['id'])['receipt']['status'], 'pending')  # Customers can't approve.
        self.press(ADMIN, f'ap:{order["id"]}:{receipt[:8]}')
        approved = self.stored(order['id'])
        self.assertEqual(approved['receipt']['status'], 'approved')
        self.assertEqual(approved['paid'], approved['deposit'])
        self.assertIn('zaklat tasdiqlandi', self.messages(CUSTOMER)[-1]['text'])
        self.press(ADMIN, f'ap:{order["id"]}:{receipt[:8]}')
        self.assertTrue(any('allaqachon' in p.get('text', '') for m, p in self.sent if m == 'answerCallbackQuery'))

    def test_admin_rejects_with_reason_and_customer_can_resend(self):
        order = self.order()
        self.send_receipt(order)
        receipt = self.stored(order['id'])['receipt']['id']
        self.press(ADMIN, f'rj:{order["id"]}:{receipt[:8]}')
        prompt = self.messages(ADMIN)[-1]['text']
        self.assertIn(order['reference'], prompt)
        plain_prompt = prompt.replace('<b>', '').replace('</b>', '')
        self.message(ADMIN, 'Summa noto‘g‘ri', reply_to_message={'text': plain_prompt})
        rejected = self.stored(order['id'])
        self.assertEqual(rejected['receipt']['status'], 'rejected')
        self.assertEqual(rejected['receipt']['reason'], 'Summa noto‘g‘ri')
        self.assertIn('rad etildi', self.messages(CUSTOMER)[-1]['text'])
        self.send_receipt(order, 'again')
        self.assertEqual(self.stored(order['id'])['receipt']['status'], 'pending')

    def test_mini_app_admin_session(self):
        response = self.client.post('/api/telegram/admin-session', json={'initData': init_data(ADMIN)})
        self.assertEqual(response.status_code, 200)
        headers = {'Authorization': 'Bearer ' + response.json()['token']}
        self.assertEqual(self.client.get('/api/admin/orders', headers=headers).status_code, 200)
        self.assertEqual(self.client.post('/api/telegram/admin-session', json={'initData': init_data(CUSTOMER)}).status_code, 403)
        self.assertEqual(self.client.post('/api/telegram/admin-session', json={'initData': init_data(ADMIN, token='1:x')}).status_code, 403)


if __name__ == '__main__':
    unittest.main()
