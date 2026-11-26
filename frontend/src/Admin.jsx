import TranslationFields, {readTranslations} from './TranslationFields';
import React, {useEffect, useState} from 'react';
import {CalendarDays, CarFront, ChevronDown, CreditCard, MapPin, Plus} from 'lucide-react';
import {categories} from './catalog';
import {money} from './pricing';
import {api, getToken, setToken} from './api';
import {inTelegram, telegramInitData} from './telegram';
import './admin.css';
import VehiclePricing from './VehiclePricing';
import ReceiptReview from './ReceiptReview';
import {receiptLabels} from './ReceiptPayment';

const currency = amount => `${money(amount)} so‘m`;
const paymentStatuses = {
  unpaid: 'To‘lanmagan',
  partial: 'Qisman to‘langan',
  paid: 'To‘langan',
};

function paymentStatus(order) {
  if (order.paid >= order.deposit) return 'paid';
  return order.paid > 0 ? 'partial' : 'unpaid';
}

function VehicleForm({onAdd}) {
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [saving, setSaving] = useState(false);
  async function submit(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const fields = new FormData(form);
    const body = new FormData();
    body.set('data', JSON.stringify({
      translations: readTranslations(fields), name: fields.get('name'), category: fields.get('category'),
      seats: Number(fields.get('seats')),
    }));
    const photo = fields.get('photo');
    if (photo.size) body.set('photo', photo);
    setSaving(true);
    setError('');
    setSuccess('');
    try {
      const car = await onAdd(body);
      setSuccess(`${car.name} katalogga qo‘shildi.`);
      form.reset();
    } catch (error) {
      setError(error.message);
    } finally {
      setSaving(false);
    }
  }

  return <form className="admin-panel admin-form admin-add-car" onSubmit={submit}>
    <h2>Avtomobil qo‘shish</h2>
    <label>Avtomobil nomi<input name="name" placeholder="Masalan, Chevrolet Tahoe" required maxLength={80}/></label>
    <TranslationFields/><div className="admin-fields">
      <label>Toifa<select name="category">{categories.map(category => <option key={category}>{category}</option>)}</select></label>
      <label>Yo‘lovchilar soni<input name="seats" type="number" min="1" max="30" step="1" defaultValue="3" required/></label>
    </div>
    <label>Avtomobil rasmi (ixtiyoriy)<input name="photo" type="file" accept="image/jpeg,image/png,image/webp"/><small>JPEG, PNG yoki WebP · 4 MB gacha</small></label>
    {error && <p className="error" role="alert">{error}</p>}
    <button className="button primary" type="submit" disabled={saving}><Plus size={18}/> Katalogga qo‘shish</button>
    {success && <p className="admin-feedback" role="status">{success}</p>}
  </form>;
}

function Location({label, point}) {
  const coordinates = `${point.lat.toFixed(5)}, ${point.lng.toFixed(5)}`;
  return <div className="admin-location"><MapPin size={18} aria-hidden="true"/>
    <div><small>{label}</small><strong>{point.address || point.name}</strong>
      {point.classification?.area && <small>{point.classification.path.map(area => area.name).join(" · ")}</small>}
      <a href={`https://www.openstreetmap.org/?mlat=${point.lat}&mlon=${point.lng}#map=16/${point.lat}/${point.lng}`} target="_blank" rel="noreferrer" aria-label={`${label} xaritada: ${coordinates}`}>{coordinates}</a>
    </div>
  </div>;
}

function Order({order, onPayment, onReview}) {
  const [feedback, setFeedback] = useState('');
  const status = paymentStatus(order);
  const [saving, setSaving] = useState(false);
  async function savePayment(event) {
    event.preventDefault();
    const amount = Number(new FormData(event.currentTarget).get('paid'));
    setSaving(true);
    try {
      await onPayment(order.id, amount);
      setFeedback('To‘lov saqlandi.');
    } catch (error) {
      setFeedback(error.message);
    } finally {
      setSaving(false);
    }
  }

  return <details className="admin-order">
    <summary>
      <span><small>{order.reference}</small><strong>{order.carName}</strong></span>
      <span>{order.date} · {order.time}</span>
      <span className="admin-summary-end"><span className={`payment-status ${order.receipt?.status === "pending" ? "partial" : status}`}>{receiptLabels[order.receipt?.status] ?? paymentStatuses[status]}</span><ChevronDown size={18} aria-hidden="true"/></span>
    </summary>
    <div className="admin-order-body">
      <div className="admin-customer"><b>{order.customerName}</b><a href={`tel:${order.phone}`}>{order.phone}</a></div>
      <div className="admin-fields">
        <Location label="Qayerdan" point={order.exactStart || order.start}/>
        <Location label="Qayerga" point={order.exactEnd || order.end}/>
      </div>
      <dl className="admin-prices">
        {order.items?.map(item => <div key={item.carId}><dt>{item.carName} · {item.quantity} × {currency(item.unitPrice)}</dt><dd>{currency(item.subtotal)}</dd></div>)}
        <div><dt>Buyurtma summasi</dt><dd>{currency(order.total)}</dd></div>
        <div><dt>Kerakli zaklat</dt><dd>{currency(order.deposit)}</dd></div>
        <div><dt>Olingan to‘lov</dt><dd>{currency(order.paid)}</dd></div>
        <div><dt>Qolgan zaklat</dt><dd>{currency(Math.max(0, order.deposit - order.paid))}</dd></div>
        <div><dt>Umumiy qoldiq</dt><dd>{currency(order.total - order.paid)}</dd></div>
      </dl>
      {order.receipt && <ReceiptReview key={order.receipt.id} order={order} onReview={onReview}/>}
      <form className="admin-payment" onSubmit={savePayment}>
        <label>Jami olingan to‘lov (so‘m)<input key={order.paid} name="paid" type="number" min="0" max={order.total} step="1" defaultValue={order.paid} required/></label>
        <button className="button primary" type="submit" disabled={saving}>To‘lovni saqlash</button>
      </form>
      {feedback && <p className="admin-feedback" role="status">{feedback}</p>}
    </div>
  </details>;
}

function AdminLogin({onLogin}) {
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(inTelegram);
  // Inside the Telegram Mini App, admins listed on the server sign in with their Telegram account.
  useEffect(() => {
    if (!inTelegram) return;
    api('/telegram/admin-session', {method: 'POST', body: {initData: telegramInitData()}})
      .then(session => { setToken(session.token); onLogin(); })
      .catch(err => setError(err.status === 403 ? 'Bu Telegram hisobi admin emas. Login va parol bilan kiring.' : 'Serverga ulanib bo‘lmadi.'))
      .finally(() => setSaving(false));
  }, []);
  async function submit(event) {
    event.preventDefault();
    setSaving(true);
    setError('');
    try {
      const fields = new FormData(event.currentTarget);
      const username = fields.get('username').trim();
      const password = fields.get('password');
      const session = await api('/admin/login', {method: 'POST', body: {username, password}});
      setToken(session.token);
      onLogin();
    } catch (err) {
      setError(err.status === 401 ? 'Login yoki parol noto‘g‘ri.' : 'Serverga ulanib bo‘lmadi.');
    } finally {
      setSaving(false);
    }
  }

  return <main className="admin-main admin-login">
    <form className="admin-panel admin-form" onSubmit={submit}>
      <h1>Admin panel</h1>
      <label>Foydalanuvchi nomi<input name="username" type="text" autoComplete="username" autoCapitalize="none" spellCheck={false} maxLength={80} required/></label>
      <label>Admin paroli<input name="password" type="password" autoComplete="current-password" required/></label>
      {error && <p className="error" role="alert">{error}</p>}
      <button className="button primary" type="submit" disabled={saving}>Kirish</button>
      <a className="admin-link" href="/">Mijozlar sahifasi</a>
    </form>
  </main>;
}

export default function Admin() {
  const [orders, setOrders] = useState([]);
  const [cars, setCars] = useState([]);
  const [places, setPlaces] = useState([]);
  const [tab, setTab] = useState('orders');
  const [filter, setFilter] = useState('all');
  const [loadError, setLoadError] = useState(false);
  const [ready, setReady] = useState(false);
  const [authenticated, setAuthenticated] = useState(() => Boolean(getToken()));
  const visibleOrders = orders.filter(order => filter === 'all' || (filter === 'review' ? order.receipt?.status === 'pending' : paymentStatus(order) === filter));
  const pendingReceipts = orders.filter(order => order.receipt?.status === 'pending').length;
  const waiting = orders.filter(order => paymentStatus(order) !== 'paid').length;

  useEffect(() => {
    document.title = 'Admin panel · Urganch Kartej';
    const expire = () => {
      setAuthenticated(false);
      setReady(false);
      setOrders([]);
    };
    window.addEventListener('admin-session-expired', expire);
    return () => window.removeEventListener('admin-session-expired', expire);
  }, []);

  async function refresh(signal) {
    try {
      const [inventory, bookings, addresses] = await Promise.all([
        api('/cars', {signal}),
        api('/admin/orders', {admin: true, signal}),
        api('/places', {signal}),
      ]);
      setCars(inventory);
      setOrders(bookings);
      setPlaces(addresses);
      setLoadError(false);
      setReady(true);
    } catch (error) {
      if (error.name !== 'AbortError') setLoadError(true);
    }
  }

  useEffect(() => {
    if (!authenticated) return;
    const controller = new AbortController();
    refresh(controller.signal);
    return () => controller.abort();
  }, [authenticated]);

  useEffect(() => {
    if (!authenticated || !ready || tab !== 'orders') return;
    const controller = new AbortController();
    let loading = false;
    async function refreshOrders() {
      if (loading || document.hidden) return;
      loading = true;
      try {
        const latest = await api('/admin/orders', {admin:true, signal:controller.signal});
        if (!controller.signal.aborted) setOrders(latest);
      } catch {
        // The existing order list remains available while the connection recovers.
      } finally {
        loading = false;
      }
    }
    const timer = setInterval(refreshOrders, 5000);
    window.addEventListener('focus', refreshOrders);
    return () => {
      controller.abort();
      clearInterval(timer);
      window.removeEventListener('focus', refreshOrders);
    };
  }, [authenticated, ready, tab]);

  async function logout() {
    try {
      await api('/admin/session', {method:'DELETE', admin:true});
    } finally {
      setToken(null);
      setAuthenticated(false);
      setReady(false);
      setOrders([]);
    }
  }

  async function addCar(body) {
    const car = await api('/admin/cars', {method:'POST', body, admin:true});
    setCars(current => [...current, car]);
    return car;
  }

  async function updateCar(id, section, body) {
    const methods = {route: 'PUT', photo: 'PUT', places: 'POST'};
    const car = await api(`/admin/cars/${id}/${section}`, {method: methods[section], body, admin:true});
    setCars(current => current.map(vehicle => vehicle.id === id ? car : vehicle));
  }

  async function reviewReceipt(id, body) {
    const order = await api(`/admin/orders/${id}/receipt`, {method:'PATCH', body, admin:true});
    setOrders(current => current.map(item => item.id === id ? order : item));
  }

  async function recordPayment(id, paid) {
    const order = await api(`/admin/orders/${id}/payment`, {
      method: 'PATCH', body: {paid}, admin: true,
    });
    setOrders(current => current.map(item => item.id === id ? order : item));
  }

  if (!authenticated) return <AdminLogin onLogin={() => setAuthenticated(true)}/>;

  return <>
    <header className="admin-header">
      <a className="brand" href="/admin"><span className="brand-icon"><CarFront size={24}/></span><span>URGANCH <b>KARTEJ</b><small>ADMIN PANEL</small></span></a>
      <div className="admin-header-actions"><a className="header-action" href="/">Mijozlar sahifasi</a><button className="header-action" onClick={() => logout().catch(() => {})}>Chiqish</button></div>
    </header>
    <main className="admin-main">
      <h1>Admin panel</h1>
      <button className="car-select admin-refresh" onClick={() => refresh()}>Yangilash</button>
      {loadError && <p className="error" role="alert">Serverdan ma’lumotlarni olib bo‘lmadi.</p>}
      {!ready && !loadError && <p role="status">Yuklanmoqda…</p>}
      {ready && <>
      <div className="admin-stats">
        <div><CalendarDays/><span>Buyurtmalar<strong>{orders.length}</strong></span></div>
        <div><CreditCard/><span>Zaklat kutilmoqda<strong>{waiting}</strong></span></div>
        <div><CarFront/><span>Avtomobillar<strong>{cars.length}</strong></span></div>
      </div>
      <div className="admin-tabs" role="group" aria-label="Admin bo‘limlari">
        <button aria-pressed={tab === 'orders'} onClick={() => setTab('orders')}>Buyurtmalar</button>
        <button aria-pressed={tab === 'cars'} onClick={() => setTab('cars')}>Avtomobillar</button>
        <button aria-pressed={tab === 'add-car'} onClick={() => setTab('add-car')}>Avtomobil qo‘shish</button>
      </div>

      {tab === 'orders' && <section className="admin-panel">
        <div className="admin-section-head">
          <div><h2>Buyurtmalar</h2>{pendingReceipts > 0 && <p className="admin-feedback">Tekshiriladigan cheklar: {pendingReceipts}</p>}</div>
          <label>Zaklat holati<select value={filter} onChange={event => setFilter(event.target.value)}>
            <option value="all">Barchasi</option>
            <option value="review">Chek tekshirilmoqda</option>
            {Object.entries(paymentStatuses).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select></label>
        </div>
        {visibleOrders.length ? visibleOrders.map(order =>
          <Order key={order.id} order={order} onPayment={recordPayment} onReview={reviewReceipt}/>
        ) : <p className="admin-empty">{orders.length ? 'Bu holatda buyurtma yo‘q.' : 'Hali buyurtmalar yo‘q. Mijozlar sahifasidan so‘rov saqlang.'}</p>}
      </section>}
      {tab === 'add-car' && <VehicleForm onAdd={addCar}/>}
      {tab === 'cars' && <section className="admin-panel">
          <h2>Avtomobillar ({cars.length})</h2>
          <ul className="admin-vehicles">
            {cars.map(car => <li key={car.id}>
              <VehiclePricing car={car} places={places} onUpdate={updateCar} onPhoto={(id, body) => updateCar(id, "photo", body)}/>
            </li>)}
          </ul>
      </section>}
      </>}
    </main>
  </>;
}
