"""Read helpers over the backend database. backend.main is imported lazily to avoid a circular import."""
import io
import json
from datetime import datetime

from fastapi import HTTPException
from PIL import Image


def backend():
    from backend import main
    return main


def all_orders():
    main = backend()
    with main.database() as db:
        return [json.loads(row[0]) for row in db.execute('SELECT data FROM orders ORDER BY rowid DESC')]


def get_order(order_id):
    main = backend()
    try:
        with main.database() as db:
            return main.read_one(db, 'orders', order_id)
    except HTTPException:
        return None


def order_id_from_reference(reference):
    return reference[3:].lower() if reference.upper().startswith('UK-') else None


def receipt_image(order_id):
    main = backend()
    with main.database() as db:
        row = db.execute('SELECT data FROM receipts WHERE order_id = ?', (order_id,)).fetchone()
    return bytes(row[0]) if row else None


def cars():
    return backend().cars()


def places():
    return backend().list_places()


def owner_id(order):
    return (order.get('telegram') or {}).get('userId')


def user_orders(user_id):
    return [order for order in all_orders() if owner_id(order) == user_id]


def awaiting_receipt(orders):
    return [order for order in orders if (order.get('receipt') or {}).get('status') in (None, 'rejected')]


def upcoming_orders():
    main = backend()
    today = datetime.now(main.TASHKENT).date().isoformat()
    orders = [order for order in all_orders() if str(order.get('date', '')) >= today]
    return sorted(orders, key=lambda order: (str(order.get('date')), str(order.get('time'))))


def pending_receipts():
    return [order for order in all_orders() if (order.get('receipt') or {}).get('status') == 'pending']


def to_jpeg(image_bytes):
    """Receipts are stored as WebP; Telegram photos are most reliable as JPEG."""
    with Image.open(io.BytesIO(image_bytes)) as image:
        output = io.BytesIO()
        image.convert('RGB').save(output, 'JPEG', quality=88)
        return output.getvalue()
