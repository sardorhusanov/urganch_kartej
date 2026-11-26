import React, {useState} from 'react';
import {ArrowRight, Camera, CarFront, ChevronDown, Pencil, Plus, Route, Trash2} from 'lucide-react';
import {money} from './pricing';
import AddressForm from './AddressForm';

export default function VehiclePricing({car, places, onUpdate, onPhoto}) {
  const [section, setSection] = useState('routes');
  const [editor, setEditor] = useState(null);
  const [adding, setAdding] = useState(null);
  const [feedback, setFeedback] = useState('');
  const [saving, setSaving] = useState(false);
  const rates = car.routeRates ?? [];
  const availablePlaces = [...places, ...(car.places ?? [])];

  function navigate(target) {
    setSection(target);
    setEditor(null);
    setAdding(null);
    setFeedback('');
  }

  function openEditor(rate) {
    setEditor(rate ? {...rate, editing: true} : {from: '', to: '', amount: '', editing: false});
    setFeedback('');
  }

  async function save(action, message) {
    setSaving(true);
    setFeedback('');
    try {
      await action();
      setEditor(null);
      setFeedback(message);
    } catch (error) {
      setFeedback(error.message);
    } finally {
      setSaving(false);
    }
  }

  function saveRoute(event) {
    event.preventDefault();
    const {from, to, amount, editing} = editor;
    if (from === to) return setFeedback('Ikki xil manzilni tanlang.');
    if (!editing && rates.some(rate => rate.from === from && rate.to === to)) {
      return setFeedback('Bu yo‘nalish allaqachon bor. Narxni o‘zgartirish uchun Tahrirlash tugmasini bosing.');
    }
    save(() => onUpdate(car.id, 'route', {start: from, end: to, amount: Number(amount)}), 'Yo‘nalish narxi saqlandi.');
  }

  async function addAddress(address) {
    await onUpdate(car.id, 'places', address);
    setEditor(current => ({...current, [adding]: address.name}));
    setAdding(null);
  }

  function removeRoute(rate) {
    if (window.confirm(`${rate.from} → ${rate.to} tarifini o‘chirasizmi?`)) {
      save(() => onUpdate(car.id, 'route', {start: rate.from, end: rate.to, amount: null}), 'Tarif o‘chirildi.');
    }
  }

  function savePhoto(event) {
    event.preventDefault();
    const form = event.currentTarget;
    save(async () => {
      await onPhoto(car.id, new FormData(form));
      form.reset();
    }, 'Avtomobil rasmi yangilandi.');
  }

  return <details className="fleet-card">
    <summary className="fleet-heading">
      <span className="fleet-thumb">{car.image ? <img src={car.image} alt="" loading="lazy"/> : <CarFront/>}</span>
      <span className="fleet-name"><strong>{car.name}</strong><small>{car.category} · {car.detail}</small></span>
      <span className="fare-count">{rates.length} yo‘nalish</span><ChevronDown className="fleet-chevron" size={18}/>
    </summary>
    <div className="fleet-body">
      <div className="fleet-switch" role="group" aria-label="Avtomobil sozlamalari">
        <button aria-pressed={section === 'routes'} disabled={saving || Boolean(adding)} onClick={() => navigate('routes')}><Route size={16}/>Yo‘nalishlar</button>
        <button aria-pressed={section === 'photo'} disabled={saving || Boolean(adding)} onClick={() => navigate('photo')}><Camera size={16}/>Avtomobil rasmi</button>
      </div>
      {section === 'routes' && !editor && <>
        <div className="fare-head"><h3>Yo‘nalish tariflari</h3><button className="button primary" disabled={saving} onClick={() => openEditor(null)}><Plus size={16}/>Yo‘nalish qo‘shish</button></div>
        {rates.length ? <ul className="fare-list">{rates.map(rate => <li key={JSON.stringify([rate.from, rate.to])}>
          <span className="fare-path">{rate.from} <ArrowRight size={16} aria-label="dan"/> {rate.to}</span>
          <strong>{money(rate.amount)} so‘m</strong>
          <span className="fare-actions">
            <button className="car-select" disabled={saving} onClick={() => openEditor(rate)}><Pencil size={15}/>Tahrirlash</button>
            <button className="fare-delete" disabled={saving} title="Tarifni o‘chirish" aria-label={`${rate.from} → ${rate.to} tarifini o‘chirish`} onClick={() => removeRoute(rate)}><Trash2 size={16}/></button>
          </span>
        </li>)}</ul> : <p className="fare-empty">Bu avtomobilni band qilish uchun birinchi yo‘nalish va uning narxini kiriting.</p>}
      </>}
      {section === 'routes' && editor && <div className="fare-editor">
        <h3>{editor.editing ? 'Narxni tahrirlash' : 'Yo‘nalish qo‘shish'}</h3>
        <form className="admin-form" onSubmit={saveRoute}>
          <div className="admin-fields">{[['from','Qayerdan'], ['to','Qayerga']].map(([key, label]) => <div key={key}>
            <label>{label}<select required disabled={editor.editing || saving || Boolean(adding)} value={editor[key]} onChange={e => setEditor({...editor, [key]: e.target.value})}>
              <option value="">Manzilni tanlang</option>{availablePlaces.map(place => <option key={place.name}>{place.name}</option>)}
            </select></label>
            {!editor.editing && <button className="fare-link" type="button" disabled={saving || Boolean(adding)} onClick={() => setAdding(key)}>+ Yangi manzil</button>}
          </div>)}</div>
          <label>Yo‘nalish narxi (so‘m)<input type="number" min="1" max="1000000000" required disabled={saving || Boolean(adding)} value={editor.amount} onChange={e => setEditor({...editor, amount: e.target.value})}/></label>
          {!adding && <div className="fare-actions"><button className="button primary" disabled={saving}>Saqlash</button><button type="button" className="car-select" disabled={saving} onClick={() => navigate('routes')}>Bekor qilish</button></div>}
        </form>
        {adding && <><h4>{adding === 'from' ? 'Yangi boshlanish manzili' : 'Yangi borish manzili'}</h4><AddressForm onAdd={addAddress} onCancel={() => setAdding(null)}/></>}
      </div>}
      {section === 'photo' && <form className="admin-form fleet-photo" onSubmit={savePhoto}>
        {car.image && <img src={car.image} alt={car.name}/>}
        <label>Yangi rasm<input type="file" name="photo" accept="image/jpeg,image/png,image/webp" required/><small>JPEG, PNG yoki WebP · 4 MB gacha</small></label>
        <button className="button primary" disabled={saving}>Rasmni saqlash</button>
      </form>}
      {feedback && <p className="admin-feedback" role="status">{feedback}</p>}
    </div>
  </details>;
}
