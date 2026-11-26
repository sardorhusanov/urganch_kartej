import React, {useEffect, useState} from 'react';
import {api} from './api';
import {receiptLabels} from './ReceiptPayment';

export default function ReceiptReview({order, onReview}) {
  const [preview, setPreview] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [rejecting, setRejecting] = useState(false);
  const receipt = order.receipt;
  const pending = receipt.status === 'pending';

  useEffect(() => () => {
    if (preview) URL.revokeObjectURL(preview);
  }, [preview]);

  async function openReceipt() {
    setBusy(true);
    setError('');
    try {
      const blob = await api(`/admin/orders/${order.id}/receipt`, {admin:true, binary:true});
      setPreview(URL.createObjectURL(blob));
    } catch (error) {
      setError(error.message);
    } finally {
      setBusy(false);
    }
  }

  async function decide(status, reason = '') {
    setBusy(true);
    setError('');
    try {
      await onReview(order.id, {receiptId:receipt.id, status, reason});
      setRejecting(false);
    } catch (error) {
      setError(error.message);
    } finally {
      setBusy(false);
    }
  }

  return <section className="receipt-review">
    <h3>To‘lov cheki</h3>
    <p>{receiptLabels[receipt.status]}</p>
    {receipt.reason && <p className="notice">{receipt.reason}</p>}
    {preview ? <a className="receipt-preview" href={preview} target="_blank" rel="noreferrer">
      <img src={preview} alt="Yuborilgan to‘lov cheki"/>
    </a> : <button type="button" className="car-select" disabled={busy} onClick={openReceipt}>Chekni ko‘rish</button>}
    {pending && <div className="admin-address-actions">
      <button className="button primary" type="button" disabled={busy || !preview} onClick={() => decide('approved')}>Tasdiqlash</button>
      <button className="car-select" type="button" disabled={busy || !preview} onClick={() => setRejecting(value => !value)}>Rad etish</button>
    </div>}
    {pending && rejecting && <form className="admin-form" onSubmit={event => {
      event.preventDefault();
      decide('rejected', new FormData(event.currentTarget).get('reason'));
    }}>
      <label>Rad etish sababi<textarea name="reason" maxLength={500} required rows={3}/></label>
      <button className="button primary" type="submit" disabled={busy}>Rad etishni saqlash</button>
    </form>}
    {error && <p className="error" role="alert">{error}</p>}
  </section>;
}
