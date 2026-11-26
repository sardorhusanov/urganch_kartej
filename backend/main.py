import hashlib
import hmac
import io
import json
import os
import re
import secrets
import threading
import time
from contextlib import asynccontextmanager
from datetime import date, datetime, time as event_time
from pathlib import Path
from typing import Annotated, Literal
from uuid import uuid4
from zoneinfo import ZoneInfo

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Response, UploadFile
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from PIL import Image, ImageOps
from pydantic import BaseModel, Field, StringConstraints, ValidationError

from .routing import router as routing_router
from .locations import router as locations_router, ExactLocation, confirmed_location
from .geography import classify
from .storage import open_database
from starlette.concurrency import run_in_threadpool

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(os.getenv("KARTEJ_DATA", ROOT / "backend" / "data"))
DEFAULT_PLACES = json.loads((ROOT / "frontend/src/places.json").read_text())
MAP_PIN_NAME = "Xaritada belgilangan manzil"
TASHKENT = ZoneInfo("Asia/Tashkent")
IMAGE_LIMIT = 4 * 1024 * 1024
AUTH = HTTPBearer(auto_error=False)


def database():
    return open_database(DATA)


_init_lock = threading.Lock()
_initialized = False


def initialize(app):
    global _initialized
    with _init_lock:
        if not _initialized:
            configure(app)
            _initialized = True


def configure(app):
    if not os.getenv("VERCEL"):
        DATA.mkdir(mode=0o700, parents=True, exist_ok=True)
    password_file = DATA / "admin-password"
    password = os.getenv("KARTEJ_ADMIN_PASSWORD")
    if not password and os.getenv("VERCEL"):
        raise RuntimeError("Set KARTEJ_ADMIN_PASSWORD before deployment.")
    if not password:
        try:
            with os.fdopen(os.open(password_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as output:
                output.write(secrets.token_urlsafe(24))
        except FileExistsError:
            pass
        password = password_file.read_text().strip()
    if len(password) < 12:
        raise RuntimeError("Admin password must contain at least 12 characters.")
    username = os.getenv("KARTEJ_ADMIN_USERNAME", "admin").strip()
    if not 1 <= len(username) <= 80:
        raise RuntimeError("Admin username must contain 1 to 80 characters.")
    app.state.username_digest = digest(username)
    app.state.password_digest = digest(password)
    with database() as db:
        postgres = bool(os.getenv("DATABASE_URL"))
        if postgres:
            db.execute("BEGIN IMMEDIATE")
        else:
            db.execute("PRAGMA journal_mode=WAL")
        ordinal = ", rowid BIGSERIAL UNIQUE" if postgres else ""
        blob = "BYTEA" if postgres else "BLOB"
        for table, key in (("places", "name_key"), ("cars", "id"), ("orders", "id")):
            db.execute(f"CREATE TABLE IF NOT EXISTS {table} ({key} TEXT PRIMARY KEY, data TEXT NOT NULL{ordinal})")
        for table, key in (("receipts", "order_id"), ("images", "id")):
            db.execute(f"CREATE TABLE IF NOT EXISTS {table} ({key} TEXT PRIMARY KEY, data {blob} NOT NULL)")
        db.execute("CREATE TABLE IF NOT EXISTS sessions (token TEXT PRIMARY KEY, expires BIGINT NOT NULL)")
        for place in DEFAULT_PLACES:
            db.execute("INSERT INTO places (name_key, data) VALUES (?, ?) ON CONFLICT(name_key) DO NOTHING",
                       (place["name"].casefold(), json.dumps(place)))
        for car in json.loads((ROOT / "frontend/src/fleet.json").read_text()):
            db.execute("INSERT INTO cars (id, data) VALUES (?, ?) ON CONFLICT(id) DO NOTHING",
                       (car["id"], json.dumps(car)))


@asynccontextmanager
async def lifespan(app):
    await run_in_threadpool(initialize, app)
    yield


app = FastAPI(title="Urganch Kartej", lifespan=lifespan)
app.include_router(routing_router)
app.include_router(locations_router)


@app.middleware("http")
async def ensure_initialized(request, call_next):
    if not _initialized:
        await run_in_threadpool(initialize, app)
    return await call_next(request)



def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def read_one(db, table, key):
    row = db.execute(f"SELECT data FROM {table} WHERE id = ?", (key,)).fetchone()
    if row is None:
        raise HTTPException(404, "Record not found")
    return json.loads(row[0])


def write_one(db, table, record):
    db.execute(f"INSERT INTO {table} (id, data) VALUES (?, ?) ON CONFLICT(id) DO UPDATE SET data = excluded.data",
               (record["id"], json.dumps(record)))


def admin_session(auth: Annotated[HTTPAuthorizationCredentials | None, Depends(AUTH)]):
    if auth:
        token = digest(auth.credentials)
        with database() as db:
            row = db.execute("SELECT expires FROM sessions WHERE token = ?", (token,)).fetchone()
        if row and row[0] > time.time():
            return token
    raise HTTPException(401, "Admin login required", headers={"WWW-Authenticate": "Bearer"})


class Login(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(max_length=1024)


@app.post("/api/admin/login")
def login(body: Login):
    username_matches = hmac.compare_digest(digest(body.username.strip()), app.state.username_digest)
    password_matches = hmac.compare_digest(digest(body.password), app.state.password_digest)
    if not (username_matches and password_matches):
        raise HTTPException(401, "Incorrect username or password")
    token = secrets.token_urlsafe(32)
    now = int(time.time())
    with database() as db:
        db.execute("DELETE FROM sessions WHERE expires <= ?", (now,))
        db.execute("INSERT INTO sessions VALUES (?, ?)", (digest(token), now + 8 * 3600))
    return {"token": token}


@app.delete("/api/admin/session", status_code=204)
def logout(token: Annotated[str, Depends(admin_session)]):
    with database() as db:
        db.execute("DELETE FROM sessions WHERE token = ?", (token,))


Admin = Depends(admin_session)
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=80)]


Language = Literal['en', 'ru', 'ar', 'zh', 'ko', 'fr', 'es', 'hi', 'pl', 'tr']
LANGUAGES = ('en', 'ru', 'ar', 'zh', 'ko', 'fr', 'es', 'hi', 'pl', 'tr')


class LocalizedName(BaseModel):
    name: str = Field(min_length=1, max_length=80)


def name_translations(body):
    return {code: {'name': body.translations[code].name if code in body.translations else body.name}
            for code in LANGUAGES}


class NewCar(BaseModel):
    translations: dict[Language, LocalizedName] = Field(default_factory=dict)
    name: Name
    category: Literal["Premium", "Biznes", "Komfort"]
    seats: int = Field(ge=1, le=30)


class RoutePrice(BaseModel):
    start: str
    end: str
    amount: int | None = Field(ge=1, le=1_000_000_000)


class Point(BaseModel):
    name: str = Field(max_length=80)
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)

    def location(self, places):
        if self.name == MAP_PIN_NAME:
            return self.model_dump()
        if self.name not in places:
            raise HTTPException(422, "Tanlangan manzil bu avtomobil uchun mavjud emas.")
        return places[self.name]


class NewPlace(Point):
    translations: dict[Language, LocalizedName] = Field(default_factory=dict)
    name: Name
    address: str | None = Field(default=None, min_length=2, max_length=500)


def read_places(db):
    places = [json.loads(row[0]) for row in db.execute("SELECT data FROM places ORDER BY rowid")]
    return [{**place, 'classification': classify(place['lat'], place['lng'])} for place in places]


@app.get("/api/places")
def list_places():
    with database() as db:
        return read_places(db)


def car_places(db, car):
    return {place["name"]: place for place in [*read_places(db), *car.get("places", [])]}


@app.post("/api/admin/cars/{car_id}/places", status_code=201, dependencies=[Admin])
def add_car_place(car_id: str, body: NewPlace):
    location = confirmed_location(ExactLocation(lat=body.lat, lng=body.lng, address=body.address or body.name))
    place = {**body.model_dump(), **location, "translations": name_translations(body)}
    key = body.name.casefold()
    if key == MAP_PIN_NAME.casefold():
        raise HTTPException(422, "Manzil uchun boshqa nom tanlang.")
    with database() as db:
        db.execute("BEGIN IMMEDIATE")
        car = read_one(db, "cars", car_id)
        if any(name.casefold() == key for name in car_places(db, car)):
            raise HTTPException(409, "Bu nomdagi manzil avtomobil ro‘yxatida mavjud.")
        car["places"] = [*car.get("places", []), place]
        write_one(db, "cars", car)
    return car


class BookingItem(BaseModel):
    carId: str = Field(min_length=1, max_length=80)
    quantity: int = Field(strict=True, ge=1, le=999)


class Booking(BaseModel):
    carId: str | None = Field(default=None, max_length=80)
    items: list[BookingItem] | None = Field(default=None, min_length=1, max_length=100)
    customerName: Name
    phone: str = Field(pattern=r"^\+998[0-9]{9}$")
    date: date
    time: event_time
    start: Point
    end: Point
    expectedTotal: int = Field(ge=1)
    exactStart: ExactLocation | None = None
    exactEnd: ExactLocation | None = None


class Payment(BaseModel):
    paid: int = Field(ge=0)


def calculate_quote(car, start, end):
    total = next((rate["amount"] for rate in car.get("routeRates", [])
                  if rate["from"] == start["name"] and rate["to"] == end["name"]), None)
    if total is None:
        raise HTTPException(409, "Bu yo‘nalish uchun tarif belgilanmagan.")
    return total, (total + 2) // 5


def encode_photo(photo):
    data = photo.file.read(IMAGE_LIMIT + 1)
    if len(data) > IMAGE_LIMIT:
        raise HTTPException(413, "Rasm 4 MB dan oshmasligi kerak.")
    try:
        with Image.open(io.BytesIO(data), formats=["JPEG", "PNG", "WEBP"]) as image:
            if image.width * image.height > 20_000_000:
                raise ValueError("Too many pixels")
            image = ImageOps.exif_transpose(image).convert("RGB")
            image.thumbnail((1600, 1600))
            output = io.BytesIO()
            image.save(output, "WEBP", quality=87)
            return output.getvalue()
    except (ValueError, OSError, Image.DecompressionBombError):
        raise HTTPException(422, "JPEG, PNG yoki WebP formatidagi rasmni tanlang.")


def save_photo(db, image):
    image_id = uuid4().hex
    db.execute("INSERT INTO images VALUES (?, ?)", (image_id, image))
    return f"/api/images/{image_id}"


@app.get("/api/images/{image_id}")
def get_image(image_id: str):
    with database() as db:
        row = db.execute("SELECT data FROM images WHERE id = ?", (image_id,)).fetchone()
    if not row:
        raise HTTPException(404)
    return Response(row[0], media_type="image/webp", headers={
        "Cache-Control": "public, max-age=604800, immutable",
        "X-Content-Type-Options": "nosniff",
    })


@app.get("/api/cars")
def cars():
    with database() as db:
        inventory = [json.loads(row[0]) for row in db.execute("SELECT data FROM cars ORDER BY rowid")]
        for car in inventory:
            car['places'] = [{**p, 'classification': classify(p['lat'], p['lng'])} for p in car.get('places', [])]
        return inventory


@app.post("/api/admin/cars", status_code=201, dependencies=[Admin])
def add_car(data: Annotated[str, Form()], photo: Annotated[UploadFile | None, File()] = None):
    try:
        body = NewCar.model_validate_json(data)
    except ValidationError:
        raise HTTPException(422, "Avtomobil ma’lumotlarini tekshiring.")
    image = encode_photo(photo) if photo else None
    car = {**body.model_dump(exclude={"seats"}), "id": uuid4().hex,
           "translations": name_translations(body), "detail": f"{body.seats} yo‘lovchi", "image": ""}
    with database() as db:
        if image:
            car["image"] = save_photo(db, image)
        write_one(db, "cars", car)
    return car


@app.put("/api/admin/cars/{car_id}/photo", dependencies=[Admin])
def replace_photo(car_id: str, photo: Annotated[UploadFile, File()]):
    image = encode_photo(photo)
    with database() as db:
        db.execute("BEGIN IMMEDIATE")
        car = read_one(db, "cars", car_id)
        previous = car["image"]
        car["image"] = save_photo(db, image)
        write_one(db, "cars", car)
        if previous.startswith("/api/images/"):
            db.execute("DELETE FROM images WHERE id = ?", (previous.rsplit("/", 1)[1],))
    return car


@app.put("/api/admin/cars/{car_id}/route", dependencies=[Admin])
def update_route(car_id: str, body: RoutePrice):
    with database() as db:
        db.execute("BEGIN IMMEDIATE")
        car = read_one(db, "cars", car_id)
        names = car_places(db, car)
        if body.start == body.end or body.start not in names or body.end not in names:
            raise HTTPException(422, "Avtomobil ro‘yxatidan ikki xil manzilni tanlang.")
        rates = [r for r in car.get("routeRates", []) if (r["from"], r["to"]) != (body.start, body.end)]
        if body.amount is not None:
            rates.append({"from": body.start, "to": body.end, "amount": body.amount})
        car["routeRates"] = rates
        write_one(db, "cars", car)
    return car


@app.post("/api/orders", status_code=201)
def create_order(body: Booking):
    if (body.exactStart is None) != (body.exactEnd is None):
        raise HTTPException(422, 'Boshlanish va borish manzillarini tasdiqlang.')
    exact_start = confirmed_location(body.exactStart) if body.exactStart else None
    exact_end = confirmed_location(body.exactEnd) if body.exactEnd else None
    if body.time.tzinfo is not None or datetime.combine(body.date, body.time, TASHKENT) <= datetime.now(TASHKENT):
        raise HTTPException(422, "Kelajakdagi sana va vaqtni tanlang.")
    with database() as db:
        db.execute("BEGIN IMMEDIATE")
        requested = body.items
        if requested is None and body.carId:
            requested = [BookingItem(carId=body.carId, quantity=1)]
        if not requested or (body.items and body.carId) or len({item.carId for item in requested}) != len(requested):
            raise HTTPException(422, "Avtomobil tanlovini tekshiring.")
        items = []
        route = None
        total = 0
        for item in requested:
            car = read_one(db, "cars", item.carId)
            places = car_places(db, car)
            start, end = body.start.location(places), body.end.location(places)
            if route and route != (start, end):
                raise HTTPException(409, "Avtomobillar uchun bir xil manzillarni tanlang.")
            route = (start, end)
            unit_price, _ = calculate_quote(car, start, end)
            subtotal = unit_price * item.quantity
            total += subtotal
            items.append({"carId": car["id"], "carName": car["name"], "quantity": item.quantity,
                          "translations": car.get("translations", {}), "unitPrice": unit_price, "subtotal": subtotal})
        for saved_point, exact_point in ((start, exact_start), (end, exact_end)):
            if exact_point:
                tariff_area = classify(saved_point['lat'], saved_point['lng']).get('area')
                if not tariff_area or tariff_area['id'] not in [node['id'] for node in exact_point['classification']['path']]:
                    raise HTTPException(422, 'Aniq manzil tanlangan tarif hududiga mos emas. Mos yo‘nalishni tanlang.')
        deposit = (total + 2) // 5
        description = ", ".join(f"{item['carName']} × {item['quantity']}" for item in items)
        if total != body.expectedTotal:
            raise HTTPException(409, "Narx yangilandi. Yangi summani tekshirib, qayta yuboring.")
        key = uuid4().hex
        tracking_token = secrets.token_urlsafe(32)
        order = {**body.model_dump(mode="json", exclude={"expectedTotal", "items", "carId"}), "id": key,
                 "reference": f"UK-{key.upper()}", "createdAt": datetime.now(TASHKENT).isoformat(),
                 "time": body.time.strftime("%H:%M"), "carName": description, "items": items, "carId": items[0]["carId"],
                 "start": {**start, "classification": classify(start['lat'], start['lng'])},
                 "end": {**end, "classification": classify(end['lat'], end['lng'])},
                 "exactStart": exact_start, "exactEnd": exact_end, "total": total, "deposit": deposit, "paid": 0,
                 "trackingHash": digest(tracking_token)}
        write_one(db, "orders", order)
    return {**tracking_summary(order), "trackingToken": tracking_token}


def tracking_summary(order):
    return {key: order[key] for key in ("id", "reference", "carName", "date", "total", "deposit", "paid")} | {
        "receipt": order.get("receipt"),
        "localizedCars": {lang: ", ".join(
            f"{item.get('translations', {}).get(lang, {}).get('name', item['carName'])} × {item['quantity']}"
            for item in order["items"]) for lang in LANGUAGES} if order.get("items") else {},
    }


def admin_summary(order):
    return {key: value for key, value in order.items() if key != "trackingHash"}


def tracked_order(db, order_id, token):
    order = read_one(db, "orders", order_id)
    if not token or not hmac.compare_digest(order.get("trackingHash", ""), digest(token)):
        raise HTTPException(404, "Buyurtma topilmadi.")
    return order


TrackingToken = Annotated[str | None, Header(alias="X-Order-Token", max_length=100)]


@app.get("/api/orders/{order_id}/status")
def track_order(order_id: str, response: Response, token: TrackingToken = None):
    response.headers["Cache-Control"] = "no-store"
    with database() as db:
        return tracking_summary(tracked_order(db, order_id, token))


@app.post("/api/orders/{order_id}/receipt")
def upload_receipt(order_id: str, response: Response, photo: Annotated[UploadFile, File()], token: TrackingToken = None):
    response.headers["Cache-Control"] = "no-store"
    with database() as db:
        tracked_order(db, order_id, token)
    image = encode_photo(photo)
    with database() as db:
        db.execute("BEGIN IMMEDIATE")
        order = tracked_order(db, order_id, token)
        if order.get("receipt", {}).get("status") in {"pending", "approved"}:
            raise HTTPException(409, "Bu buyurtma uchun chek allaqachon yuborilgan.")
        order["receipt"] = {"id": uuid4().hex, "status": "pending", "submittedAt": datetime.now(TASHKENT).isoformat()}
        db.execute("INSERT INTO receipts VALUES (?, ?) ON CONFLICT(order_id) DO UPDATE SET data = excluded.data",
                   (order_id, image))
        write_one(db, "orders", order)
    return tracking_summary(order)


@app.get("/api/admin/orders/{order_id}/receipt", dependencies=[Admin])
def view_receipt(order_id: str):
    with database() as db:
        row = db.execute("SELECT data FROM receipts WHERE order_id = ?", (order_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Chek topilmadi.")
    return Response(row[0], media_type="image/webp", headers={
        "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff",
    })


class ReceiptDecision(BaseModel):
    receiptId: str = Field(max_length=80)
    status: Literal["approved", "rejected"]
    reason: str = Field(default="", max_length=500)


@app.patch("/api/admin/orders/{order_id}/receipt", dependencies=[Admin])
def review_receipt(order_id: str, body: ReceiptDecision):
    reason = body.reason.strip()
    if body.status == "rejected" and not reason:
        raise HTTPException(422, "Rad etish sababini yozing.")
    with database() as db:
        db.execute("BEGIN IMMEDIATE")
        order = read_one(db, "orders", order_id)
        receipt = order.get("receipt", {})
        if receipt.get("status") != "pending" or receipt.get("id") != body.receiptId:
            raise HTTPException(409, "Chek holati yangilangan. Buyurtmani qayta yuklang.")
        receipt.update(status=body.status, reason=reason, reviewedAt=datetime.now(TASHKENT).isoformat())
        if body.status == "approved":
            order["paid"] = max(order["paid"], order["deposit"])
        write_one(db, "orders", order)
    return admin_summary(order)


@app.get("/api/admin/orders", dependencies=[Admin])
def orders():
    with database() as db:
        return [admin_summary(json.loads(row[0])) for row in db.execute("SELECT data FROM orders ORDER BY rowid DESC")]


@app.patch("/api/admin/orders/{order_id}/payment", dependencies=[Admin])
def update_payment(order_id: str, body: Payment):
    with database() as db:
        db.execute("BEGIN IMMEDIATE")
        order = read_one(db, "orders", order_id)
        if body.paid > order["total"]:
            raise HTTPException(422, "To‘lov buyurtma summasidan oshmasligi kerak.")
        if order.get("receipt", {}).get("status") == "approved" and body.paid < order["deposit"]:
            raise HTTPException(422, "Tasdiqlangan zaklatdan kam summa kiritib bo‘lmaydi.")
        order["paid"] = body.paid
        write_one(db, "orders", order)
    return admin_summary(order)


@app.get("/admin", include_in_schema=False)
def admin_page():
    from fastapi.responses import FileResponse
    return FileResponse(ROOT / "frontend" / "dist" / "index.html")


if (ROOT / "frontend" / "dist").is_dir():
    app.mount("/", StaticFiles(directory=ROOT / "frontend" / "dist", html=True), name="frontend")
