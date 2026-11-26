import TranslationFields, {readTranslations} from './TranslationFields';
import React, {useState} from 'react';
import {Plus} from 'lucide-react';
import LocationPicker from './LocationPicker';

export default function AddressForm({onAdd, onCancel}) {
  const [location, setLocation] = useState(null), [dirty, setDirty] = useState(false);
  const [feedback, setFeedback] = useState(''), [saving, setSaving] = useState(false);
  async function submit(event) {
    event.preventDefault();
    if (!location || dirty) return;
    const fields = new FormData(event.currentTarget);
    setSaving(true); setFeedback('');
    try {
      await onAdd({translations: readTranslations(fields), name: fields.get('name').trim(), address: location.address, lat: location.lat, lng: location.lng});
    } catch (error) {setFeedback(error.message);}
    finally {setSaving(false);}
  }
  return <form className="admin-form admin-car-address-form" onSubmit={submit}>
    <label>Manzil nomi<input name="name" minLength={2} maxLength={80} required placeholder="Masalan, to‘yxona yoki mahalla" disabled={saving}/></label>
    <TranslationFields/><LocationPicker value={location} onConfirm={setLocation} onDirty={setDirty} disabled={saving}/>
    <div className="admin-address-actions">
      <button className="button primary" type="submit" disabled={saving || !location || dirty}><Plus size={18}/>Manzilni saqlash</button>
      <button className="car-select" type="button" onClick={onCancel} disabled={saving}>Bekor qilish</button>
    </div>
    {feedback && <p role="status" className="admin-feedback">{feedback}</p>}
  </form>;
}
