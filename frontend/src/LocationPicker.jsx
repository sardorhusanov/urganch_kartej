/** @jsx localizedElement */
/** @jsxFrag React.Fragment */
import {localizedElement} from "./localization";
import React, {useEffect, useRef, useState, useId} from 'react';
import {LocateFixed, Search, CheckCircle2} from 'lucide-react';
import {api} from './api';
import LocationMap from './maps/LocationMap';
import './locations.css';

const emptyResults = [];
export default function LocationPicker({title = 'Aniq manzil', value, initialPoint, onConfirm, onDirty = () => {}, disabled = false}) {
  const id = useId();
  const [config, setConfig] = useState(null), [configError, setConfigError] = useState('');
  const [draft, setDraft] = useState(value ?? null), [dirty, setDirty] = useState(false);
  const [query, setQuery] = useState('');
  const [results, setResults] = useState(emptyResults), [searched, setSearched] = useState(false);
  const [searching, setSearching] = useState(false), [locating, setLocating] = useState(false);
  const [resolving, setResolving] = useState(false), [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');
  const selection = useRef(0), search = useRef(null), mounted = useRef(true);
  const gpsRequest = useRef(0);
  const updateDirty = next => {setDirty(next); onDirty(next);};
  useEffect(() => {
    mounted.current = true;
    const controller = new AbortController();
    api('/locations/config', {signal: controller.signal}).then(setConfig).catch(e => {if (e.name !== 'AbortError') setConfigError('Xarita sozlamalarini yuklab bo‘lmadi.');});
    return () => {mounted.current = false; controller.abort(); search.current?.abort(); selection.current++; gpsRequest.current++;};
  }, []);

  async function choose(point) {
    search.current?.abort(); setSearching(false); setResults(emptyResults); setSearched(false);
    const version = ++selection.current;
    gpsRequest.current++;
    setLocating(false);
    updateDirty(true); setMessage(''); setResolving(true);
    const next = {lat: point.lat, lng: point.lng, address: point.address ?? '', source: point.source ?? 'search', accuracy: point.accuracy ?? null};
    setDraft(next);
    if (!point.address && config?.addressSearch) {
      try {
        const result = await api(`/locations/reverse?lat=${point.lat}&lng=${point.lng}`);
        if (mounted.current && version === selection.current) setDraft({...next, address: result.address});
      } catch {
        if (mounted.current && version === selection.current) setMessage('Manzil topilmadi. Ko‘cha, uy raqami yoki mo‘ljalni yozing.');
      }
    }
    if (mounted.current && version === selection.current) setResolving(false);
  }

  async function find() {
    if (query.trim().length < 2 || disabled) return;
    search.current?.abort();
    const controller = new AbortController(); search.current = controller;
    setSearching(true); setMessage(''); setSearched(false); setResults(emptyResults);
    try {
      const data = await api(`/locations/search?q=${encodeURIComponent(query.trim())}`, {signal: controller.signal});
      if (search.current === controller && mounted.current) {setResults(data.results); setSearched(true);}
    } catch (e) {
      if (e.name !== 'AbortError' && mounted.current) setMessage(e.message);
    } finally {
      if (search.current === controller && mounted.current) setSearching(false);
    }
  }
  function gps() {
    if (!navigator.geolocation) {setMessage('Brauzeringiz GPS joylashuvini qo‘llab-quvvatlamaydi.'); return;}
    const version = ++gpsRequest.current;
    setLocating(true); setMessage('');
    navigator.geolocation.getCurrentPosition(position => {
      if (!mounted.current || gpsRequest.current !== version) return;
      choose({lat: position.coords.latitude, lng: position.coords.longitude, accuracy: position.coords.accuracy, source: 'gps'});
    }, error => {
      if (!mounted.current || gpsRequest.current !== version) return;
      setLocating(false);
      setMessage(error.code === 1 ? 'GPS ruxsati berilmadi. Manzilni qidiring yoki xaritadan tanlang.' : 'GPS joylashuvi aniqlanmadi. Qayta urinib ko‘ring yoki xaritadan tanlang.');
    }, {enableHighAccuracy: true, timeout: 12000, maximumAge: 0});
  }
  function edit(patch) {
    selection.current++; gpsRequest.current++;
    setLocating(false); setResolving(false); setMessage(''); updateDirty(true);
    setDraft(previous => ({source: 'manual', address: '', ...previous, ...patch, classification: undefined}));
  }
  async function confirm() {
    setSaving(true); setMessage('');
    try {
      const confirmed = await api('/locations/confirm', {method: 'POST', body: draft});
      if (!mounted.current) return;
      await onConfirm(confirmed);
      setDraft(confirmed); updateDirty(false);
    } catch (e) {if (mounted.current) setMessage(e.message);}
    finally {if (mounted.current) setSaving(false);}
  }
  const valid = draft && Number.isFinite(draft.lat) && Number.isFinite(draft.lng) && Math.abs(draft.lat) <= 90 && Math.abs(draft.lng) <= 180 && draft.address.trim().length >= 2;
  const locked = disabled || saving;
  return <fieldset className="location-picker" disabled={locked}>
    <legend>{title}</legend>
    {config?.addressSearch ? <div className="location-search">
      <label htmlFor={`${id}-query`}>{config?.businessSearch ? 'Ko‘cha, uy raqami yoki tashkilot nomi' : 'Shahar, ko‘cha yoki uy raqami'}</label>
      <div className="location-search-row">
        <input id={`${id}-query`} maxLength={200} value={query} placeholder="Masalan, Turon to‘yxonasi yoki Xonqa 67A" onChange={e => {setQuery(e.target.value); search.current?.abort(); setSearching(false); setSearched(false); setResults(emptyResults);}} onKeyDown={e => {if(e.key === 'Enter'){e.preventDefault(); find();}}}/>
        <button type="button" className="car-select" disabled={query.trim().length < 2 || searching} onClick={find}><Search size={17}/>{searching ? 'Qidirilmoqda…' : 'Qidirish'}</button>
      </div>
    </div> : <p role="status">{configError || (config ? 'Qidiruv hozircha mavjud emas. Xaritada nuqtani tanlang va manzilni yozing.' : 'Qidiruv yuklanmoqda…')}</p>}
    {results.length > 0 && <ol className="location-results">{results.map((p, i) => <li key={`${p.lat}-${p.lng}-${i}`}><button type="button" onClick={() => choose(p)}><strong>{i + 1}. {p.name}</strong>{p.name !== p.address && <span>{p.address}</span>}</button></li>)}</ol>}
    {searched && !results.length && <p role="status">Xorazm bo‘yicha natija topilmadi. Boshqa manzilni kiriting yoki xaritadan tanlang.</p>}
    <button type="button" className="car-select location-gps" disabled={locating} onClick={gps}><LocateFixed size={18}/>{locating ? 'Joylashuv aniqlanmoqda…' : 'Hozirgi joylashuvim'}</button>
    <LocationMap point={draft ?? initialPoint} results={results} onPick={p => {if (!locked) choose(p);}} onResult={p => {if (!locked) choose(p);}}/>
    <small className="boundary-credit">{config?.addressSearch && <>Powered by <a href="https://www.geoapify.com/">Geoapify</a> · </>} <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">© OpenStreetMap</a> · <a href="/api/locations/boundaries">Chegara ma’lumotlari</a></small>
    <p className="location-help">Manzilni belgilash uchun xaritani bosing yoki belgini suring.</p>
    <details className="coordinate-entry"><summary>Koordinatalarni kiritish</summary><div className="location-coordinates">
      <label>Kenglik (lat)<input type="number" step="any" min="-90" max="90" value={draft?.lat ?? ''} onChange={e => edit({lat: e.target.value === '' ? null : Number(e.target.value), source: 'manual', accuracy: null})}/></label>
      <label>Uzunlik (lng)<input type="number" step="any" min="-180" max="180" value={draft?.lng ?? ''} onChange={e => edit({lng: e.target.value === '' ? null : Number(e.target.value), source: 'manual', accuracy: null})}/></label>
    </div></details>
    <label>To‘liq manzil yoki mo‘ljal<input maxLength={500} value={draft?.address ?? ''} placeholder="Ko‘cha, uy raqami, kirish yoki mo‘ljal" onChange={e => edit({address: e.target.value})}/></label>
    {draft?.accuracy != null && <small>GPS aniqligi: taxminan {Math.round(draft.accuracy)} metr. Belgini tekshiring.</small>}
    {resolving && <p role="status">Manzil aniqlanmoqda…</p>}
    {message && <p className="location-message" role="status">{message}</p>}
    {!dirty && draft?.classification && <p className="location-confirmed"><CheckCircle2 size={18}/>Manzil tasdiqlandi · {draft.classification.area.name}</p>}
    <div className="location-actions">
      <button type="button" className="button primary" disabled={!valid || !dirty || resolving || locating} onClick={confirm}>{saving ? 'Tasdiqlanmoqda…' : 'Manzilni tasdiqlash'}</button>
      {dirty && <button type="button" className="car-select" onClick={() => {selection.current++; gpsRequest.current++; setLocating(false); setDraft(value ?? null); updateDirty(false); setMessage(''); setResolving(false);}}>Bekor qilish</button>}
    </div>
  </fieldset>;
}
