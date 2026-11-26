/** @jsx localizedElement */
/** @jsxFrag React.Fragment */
import {localizedElement, orderCars} from "./localization";
import React, {useEffect, useState} from 'react';
import {CreditCard} from 'lucide-react';
import {api} from './api';
import {money} from './pricing';

export const receiptLabels = {
  pending: 'Chek tekshirilmoqda',
  approved: 'Zaklat tasdiqlandi',
  rejected: 'Chek rad etildi',
};

const storageKey = 'kartej-tracked-orders';

export function loadTrackedOrders() {
  try {
    const orders = JSON.parse(localStorage.getItem(storageKey) ?? '[]');
    return Array.isArray(orders) ? orders : [];
  } catch {
    return [];
  }
}

export function rememberOrder(order, previous) {
  const next = [order, ...previous.filter(item => item.id !== order.id)];
  try {
    localStorage.setItem(storageKey, JSON.stringify(next));
  } catch {
    // The current page can still track this order for the rest of the visit.
  }
  return next;
}

function OrderPayment({order}) {
  const [details, setDetails] = useState(order);
  const [busy, setBusy] = useState(false);
  const [loadError, setLoadError] = useState('');
  const [uploadError, setUploadError] = useState('');
  const path = `/orders/${order.id}`;

  useEffect(() => {
    if (busy) return;
    const controller = new AbortController();
    async function refresh() {
      try {
        setDetails(await api(`${path}/status`, {orderToken:order.trackingToken, signal:controller.signal}));
        setLoadError('');
      } catch (error) {
        if (!controller.signal.aborted) setLoadError('Holatni yangilab bo‘lmadi. Yana urinilmoqda.');
      }
    }

    refresh();
    const timer = setInterval(refresh, 5000);
    window.addEventListener('focus', refresh);
    return () => {
      controller.abort();
      clearInterval(timer);
      window.removeEventListener('focus', refresh);
    };
  }, [path, order.trackingToken, busy]);

  async function upload(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const body = new FormData(form);
    setBusy(true);
    setUploadError('');
    try {
      const result = await api(`${path}/receipt`, {method:'POST', body, orderToken:order.trackingToken});
      setDetails(result);
      form.reset();
    } catch (error) {
      setUploadError(error.message);
    } finally {
      setBusy(false);
    }
  }

  const status = details.receipt?.status;
  const canUpload = !status || status === 'rejected';

  return <div className="customer-payment-card">
    <div className="customer-payment-head">
      <div><h3>{orderCars(details)}</h3><small>{details.date} · {details.reference}</small></div>
      <strong className={`payment-status ${status === 'approved' ? 'paid' : status === 'pending' ? 'partial' : ''}`} role="status">
        {receiptLabels[status] ?? 'Chek kutilmoqda'}
      </strong>
    </div>
    {loadError && <p className="error">{loadError}</p>}
    {status === 'rejected' && <p className="notice">Sabab: {details.receipt.reason}</p>}
    <div className="payment-totals">
      <span>Zaklat <strong>{money(details.deposit)} so‘m</strong></span>
      <span>Qolgan balans <strong>{money(details.total - details.paid)} so‘m</strong></span>
    </div>
    {canUpload && <>
      <div className="payment-preview">
        <CreditCard size={25} aria-hidden="true"/>
        <div><b>Demo karta</b><p>0000 0000 0000 0000</p></div>
      </div>
      <p className="notice">Sinov rejimi. Bu karta raqamiga pul yubormang. Jarayonni sinash uchun namunaviy chek rasmini yuklang.</p>
      <form className="admin-form" onSubmit={upload}>
        <label className="receipt-file">To‘lov cheki <input name="photo" type="file" accept="image/jpeg,image/png,image/webp" required/>
          <small>JPEG, PNG yoki WebP · 4 MB gacha</small>
        </label>
        <button type="submit" className="button primary" disabled={busy}>{busy ? 'Yuborilmoqda…' : status === 'rejected' ? 'Yangi chek yuborish' : 'Chekni yuborish'}</button>
        {uploadError && <p className="error" role="alert">{uploadError}</p>}
      </form>
    </>}
  </div>;
}

export default function ReceiptPayment({orders}) {
  const [selected, setSelected] = useState('');
  if (!orders.length) return null;
  const order = orders.find(item => item.id === selected) ?? orders[0];

  return <section className="section customer-payment" id="payment">
    <span className="eyebrow">BUYURTMA VA TO‘LOV</span>
    <h2>Zaklat holati</h2>
    {orders.length > 1 && <label className="payment-select">Buyurtmani tanlang
      <select value={order.id} onChange={event => setSelected(event.target.value)}>
        {orders.map(item => <option key={item.id} value={item.id}>{orderCars(item)} · {item.date} · {item.reference.slice(0, 11)}</option>)}
      </select>
    </label>}
    <OrderPayment key={order.id} order={order}/>
  </section>;
}
