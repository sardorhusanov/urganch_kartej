import {languages, flags} from './languages';
/** @jsx localizedElement */
/** @jsxFrag React.Fragment */
import {localizedElement, currentLanguage, orderCars, selectLanguage, displayName, translate, routeArrow} from "./localization";
import React, {useState, useEffect, useRef} from 'react';
import {createRoot} from 'react-dom/client';
import {CarFront, MapPin, CalendarDays, Check, Clock3, ShieldCheck, ChevronDown, X, Menu, CreditCard, Users, CheckCircle2, Instagram, Phone, ArrowRight, ArrowLeft, Heart, Plane, Briefcase} from 'lucide-react';
import './style.css';
import './booking.css';
import {places as defaultPlaces,quote,money} from './pricing';
import {categories} from './catalog';
import defaultCars from './fleet.json';
import {api} from './api';
import Admin from './Admin';
import ReceiptPayment, {loadTrackedOrders, rememberOrder} from './ReceiptPayment';
import LocationPicker from './LocationPicker';


function ContactLinks() {
 return <div className="contact-links">
  <a href="tel:+998934650505"><Phone size={18} aria-hidden="true"/><span dir="ltr">+998 93 465 05 05</span></a>
  <a className="instagram-link" href="https://www.instagram.com/urganch_kartej_xorazm/" target="_blank" rel="noopener noreferrer" aria-label="Instagram: urganch_kartej_xorazm"><span className="instagram-logo"><Instagram size={23} aria-hidden="true"/></span></a>
 </div>;
}

function CarImage({car, decorative = false}) {
 const [failed, setFailed] = useState(false);
 if (!car.image || failed) return <span className="vehicle-placeholder"><CarFront aria-hidden="true"/></span>;
 return <img src={car.image} alt={decorative ? '' : car.name} loading="lazy" onError={() => setFailed(true)}/>;
}

const occasions = [
 {icon: Heart, title: 'To‘y va tantanalar', text: 'Kelin-kuyov kortejidan mehmonlarni kutib olishgacha — bir uslubdagi avtomobillar.'},
 {icon: Plane, title: 'Mehmonlar va sayyohlar', text: 'Xorazmga kelganlar uchun: aeroport, vokzal, Xiva va Urganch bo‘ylab haydovchi bilan.'},
 {icon: Briefcase, title: 'Biznes va delegatsiyalar', text: 'Uchrashuvlar, hamkorlar va rasmiy tashriflar uchun ishonchli va o‘z vaqtida xizmat.'},
];

const bookingSteps = ['Yo‘nalish va sana', 'Avtomobillar', 'Aniq manzillar', 'Tekshirish'];
const stepHashes = ['route', 'cars', 'locations', 'review'];
function loadBookingDraft() {
 try { return JSON.parse(sessionStorage.getItem('booking-draft')) || {}; } catch { return {}; }
}
function App(){
 const [language, setLanguage] = useState(currentLanguage);

 const [draft] = useState(loadBookingDraft);
 const [bookingPage, setBookingPage] = useState(location.pathname.replace(/\/$/, '') === '/booking');
 const [step, setStep] = useState(Math.max(0, stepHashes.indexOf(location.hash.slice(1))));
 function navigateBooking(nextStep = 0) {
   history.pushState(null, '', '/booking#' + stepHashes[nextStep]);
   setBookingPage(true); setStep(nextStep); setMenu(false); setError('');
   window.scrollTo({top: 0, behavior: 'instant'});
 }
 function navigateHome(hash = '') {
   history.pushState(null, '', '/' + hash); setBookingPage(false); setMenu(false);
   requestAnimationFrame(() => hash ? document.querySelector(hash)?.scrollIntoView() : window.scrollTo(0, 0));
 }
 useEffect(() => {
   const sync = () => {
     if (location.pathname === '/' && location.hash === '#booking') {navigateBooking(); return;}
     setBookingPage(location.pathname.replace(/\/$/, '') === '/booking');
     setStep(Math.max(0, stepHashes.indexOf(location.hash.slice(1))));
   };
   sync(); window.addEventListener('popstate', sync); window.addEventListener('hashchange', sync);
   return () => {window.removeEventListener('popstate', sync); window.removeEventListener('hashchange', sync);};
 }, []);

 const [cars, setCars] = useState(defaultCars);
 const [trackedOrders, setTrackedOrders] = useState(loadTrackedOrders);
 const [sharedPlaces, setSharedPlaces] = useState(defaultPlaces);
 const [catalogReady, setCatalogReady] = useState(false);
 const [catalogError, setCatalogError] = useState('');
 const [submitError, setSubmitError] = useState('');
 const [saving, setSaving] = useState(false);
 async function loadCars(signal) {
   try {
     const [inventory, addresses] = await Promise.all([api('/cars', {signal}), api('/places', {signal})]);
     setCars(inventory);
     setSharedPlaces(addresses);
     setCatalogReady(true);
     setCatalogError('');
   } catch (error) {
     if (error.name === 'AbortError') return;
     setCatalogError('Katalogni yuklab bo‘lmadi. Qayta urinib ko‘ring.');
     setCatalogReady(false);
   }
 }
 useEffect(() => {
   const controller = new AbortController();
   const refresh = () => loadCars(controller.signal);
   refresh();
   window.addEventListener('focus', refresh);
   return () => {
     controller.abort();
     window.removeEventListener('focus', refresh);
   };
 }, []);
 const [quantities, setQuantities] = useState(draft.quantities || {});
 const [filter,setFilter]=useState('Barchasi'),[start,setStart]=useState(draft.start || defaultPlaces[0]),[end,setEnd]=useState(draft.end || defaultPlaces[1]),[active,setActive]=useState(null),[date,setDate]=useState(draft.date || ''),[time,setTime]=useState(draft.time || '10:00'),[modal,setModal]=useState(false),[name,setName]=useState(''),[phone,setPhone]=useState(''),[error,setError]=useState(''),[menu,setMenu]=useState(false),[savedOrder,setSavedOrder]=useState(null);
 const dialogRef=useRef(null);
 const [scrolled, setScrolled] = useState(false);
 useEffect(() => {
   const update = () => setScrolled(window.scrollY > 24);
   update(); window.addEventListener('scroll', update, {passive: true});
   return () => window.removeEventListener('scroll', update);
 }, []);
 const selectedCars = cars.filter(vehicle => quantities[vehicle.id] > 0);
 const car = selectedCars[0] ?? cars[0];
 const places = [...sharedPlaces, ...(car.places ?? [])];
 const [exactLocations, setExactLocations] = useState(draft.exactLocations || {start: null, end: null});
 const [locationDirty, setLocationDirty] = useState({start: false, end: false});
 useEffect(() => {
   if (!bookingPage || step !== 2 || !active) return;
   const editor = document.querySelector('.location-editor:not([hidden])');
   const mobile = window.matchMedia('(max-width:760px)').matches;
   const oldOverflow = document.body.style.overflow;
   if (mobile) document.body.style.overflow = 'hidden';
   editor?.querySelector('button')?.focus({preventScroll:true});
   function keyboard(event) {
     if (event.key === 'Escape') setActive(null);
     if (mobile && event.key === 'Tab') {
       const controls = [...editor.querySelectorAll('button:not(:disabled), input:not(:disabled), summary, a[href]')].filter(element => element.getClientRects().length);
       const first = controls[0], last = controls[controls.length - 1];
       if (event.shiftKey && document.activeElement === first) {event.preventDefault(); last?.focus();}
       if (!event.shiftKey && document.activeElement === last) {event.preventDefault(); first?.focus();}
     }
   }
   document.addEventListener('keydown', keyboard);
   return () => {
     document.body.style.overflow = oldOverflow;
     document.removeEventListener('keydown', keyboard);
     document.getElementById('route-' + active)?.focus({preventScroll:true});
   };
 }, [bookingPage, step, active]);
 function matchesTariff(point, exact) {
   const areaId = places.find(p => p.name === point.name && p.lat === point.lat && p.lng === point.lng)?.classification?.area?.id;
   return exact?.classification?.path.some(area => area.id === areaId);
 }
 const locationsReady = matchesTariff(start, exactLocations.start) && matchesTariff(end, exactLocations.end) && !locationDirty.start && !locationDirty.end;
 function confirmExact(which, point) {
   setExactLocations(previous => ({...previous, [which]: point}));
   setActive(null);
   setLocationDirty(previous => ({...previous, [which]: false}));
   const current = which === 'start' ? start : end;
   if (!matchesTariff(current, point)) {
     const candidate = places.find(p => matchesTariff(p, point));
     if (candidate) (which === 'start' ? setStart : setEnd)(candidate);
   }
 }
 function samePlace(vehicle, point) {
   return [...sharedPlaces, ...(vehicle.places ?? [])].some(p => p.name === point.name && p.lat === point.lat && p.lng === point.lng);
 }
 function basketPrice(origin, destination) {
   if (!origin || !destination || !selectedCars.length) return null;
   let total = 0;
   for (const vehicle of selectedCars) {
     const fare = quote(vehicle, origin, destination);
     if (!fare || !samePlace(vehicle, origin) || !samePlace(vehicle, destination)) return null;
     total += fare.total * quantities[vehicle.id];
   }
   const deposit = Math.round(total / 5);
   return {total, deposit, remainder: total - deposit};
 }
 const price = basketPrice(start, end);
 const commonRates = (car.routeRates ?? []).flatMap(rate => {
   const fare = basketPrice(places.find(p => p.name === rate.from), places.find(p => p.name === rate.to));
   return fare ? [{...rate, amount: fare.total}] : [];
 });
 const description = selectedCars.map(c => c.name + ' × ' + quantities[c.id]).join(', ');
 function changeQuantity(id, change) {
   setQuantities(previous => ({...previous, [id]: Math.max(0, Math.min(999, (previous[id] ?? 0) + change))}));
 }
 function quantityControls(vehicle) {
   const quantity = quantities[vehicle.id] ?? 0;
   if (!quantity) return <button disabled={bookingPage && (!quote(vehicle, start, end) || !samePlace(vehicle, start) || !samePlace(vehicle, end))} className="car-select" onClick={() => changeQuantity(vehicle.id, 1)}>Qo‘shish</button>;
   return <span className="quantity-control"><button aria-label={displayName(vehicle) + ' ' + translate('sonini kamaytirish')} onClick={() => changeQuantity(vehicle.id, -1)}>−</button><b>{quantity}</b><button disabled={quantity >= 999} aria-label={displayName(vehicle) + ' ' + translate('sonini oshirish')} onClick={() => changeQuantity(vehicle.id, 1)}>+</button></span>;
 }
 const today=new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Tashkent',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
 useEffect(()=>{if(!modal)return;const old=document.body.style.overflow;document.body.style.overflow='hidden';dialogRef.current?.focus();const handler=e=>{if(e.key==='Escape'&&!saving)setModal(false);if(e.key==='Tab'){const items=dialogRef.current.querySelectorAll('button,input,select,a[href]');const first=items[0],last=items[items.length-1];if(e.shiftKey&&document.activeElement===first){e.preventDefault();last.focus();}else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first.focus();}}};document.addEventListener('keydown',handler);return()=>{document.body.style.overflow=old;document.removeEventListener('keydown',handler);document.querySelector('.review-form button[type=submit]')?.focus({preventScroll:true});};},[modal, saving]);
 const selectPlace=(v,which)=>{const p=places.find(p=>p.name===v);if(p)(which==='start'?setStart:setEnd)(p);};
 useEffect(() => {
   try { sessionStorage.setItem('booking-draft', JSON.stringify({quantities, start, end, date, time, exactLocations})); } catch {}
 }, [quantities, start, end, date, time, exactLocations]);
 function continueBooking() {
   if (step === 0 && (!date || !time || new Date(`${date}T${time}:00+05:00`).getTime() <= Date.now())) {
     setError('Kelajakdagi sana va vaqtni tanlang.'); return;
   }
   if (step === 1 && (!catalogReady || !price)) {setError('Yo‘nalishingiz uchun tarifli avtomobil tanlang.'); return;}
   if (step === 2 && !locationsReady) {setError('Olib ketish va borish manzillarini tasdiqlang.'); return;}
   navigateBooking(step + 1);
 }
 const submit = async e => {
   e.preventDefault();
   if (!date || !time || new Date(`${date}T${time}:00+05:00`).getTime() <= Date.now()) {
     navigateBooking(0); setError('Kelajakdagi sana va vaqtni tanlang.'); return;
   }
   if (!price || !catalogReady) {navigateBooking(1); setError('Tarifli avtomobil tanlang.'); return;}
   if (!locationsReady) {navigateBooking(2); setError('Ikkala manzilni tasdiqlang.'); return;}

   const customerName = name.trim();
   if (customerName.length < 2) {
     setSubmitError('Ismingizni kiriting.');
     return;
   }
   if (saving || !price || !locationsReady) return;
   setSaving(true);
   setSubmitError('');
   try {
     const order = await api('/orders', {method:'POST', body:{
       items: selectedCars.map(c => ({carId: c.id, quantity: quantities[c.id]})), customerName, phone, date, time,
       start, end, exactStart: exactLocations.start, exactEnd: exactLocations.end, expectedTotal: price.total,
     }});
     setSavedOrder(order);
     setTrackedOrders(rememberOrder(order, trackedOrders));
     setModal(true);
     sessionStorage.removeItem('booking-draft');
   } catch (error) {
     if (error.status === 409) await loadCars();
     setSubmitError(error.status ? error.message : 'Buyurtmani yuborib bo‘lmadi. Qayta urinib ko‘ring.');
   } finally {
     setSaving(false);
   }
 };
 const catalog = ( <section id="cars" className="section"><div className="section-heading"><div><span className="eyebrow">SIZNING KUNINGIZ, SIZNING TANLOVINGIZ</span><h2>Qaysi avtomobil sizga mos?</h2></div><p>Har bir did va tantana uchun.<br/>Modellarni tanlang va sonini belgilang.</p></div><div className="filters">{['Barchasi',...categories].map(f=><button key={f} onClick={()=>setFilter(f)} className={filter===f?'selected':''}>{f}{f==='Barchasi'&&<span>{cars.length}</span>}</button>)}<span className="catalog-note">{cars.length} avtomobil</span></div><div className="cars">{cars.filter(c=>filter==='Barchasi'||c.category===filter).map(c=><article key={c.id} className={`car-card ${quantities[c.id]?'chosen':''}`}><div className={`car-image ${c.image.endsWith('.png')?'studio':''}`}><CarImage car={c}/>{c.tag && <span className="car-tag">{c.tag}</span>}<span className="category">{c.category}</span></div><div className="car-body"><h3>{displayName(c)}</h3><p><Users size={15}/>{c.detail}<span>Haydovchi bilan</span></p><div className="car-bottom"><div><b className={(bookingPage ? quote(c, start, end) : c.routeRates?.length) ? "" : "no-price"}>{bookingPage ? (quote(c, start, end) ? money(quote(c, start, end).total) : "Bu yo‘nalishda tarif yo‘q") : c.routeRates?.length ? money(Math.min(...c.routeRates.map(rate => rate.amount))) : "Tarif kiritilmagan"}</b> {Boolean(c.routeRates?.length) && <small>{bookingPage ? (quote(c, start, end) ? "so‘m" : "") : "so‘mdan"}</small>}</div>{quantityControls(c)}</div></div></article>)}</div></section>);
 return <><header className={`site-header ${!bookingPage && !scrolled && !menu ? 'over-hero' : ''}`}><div className="header-inner"><a href="/" onClick={e => {e.preventDefault(); navigateHome();}} className="brand"><span className="brand-icon"><CarFront size={22}/></span><span>URGANCH <b>KARTEJ</b><small>HAR BIR LAHZA QADRLI</small></span></a><nav className={`site-nav ${menu?'open':''}`}><a href="/#cars" onClick={e => {e.preventDefault(); navigateHome("#cars");}}>Avtomobillar</a><a href="/booking" onClick={e => {e.preventDefault(); navigateBooking();}}>Yo‘nalish va narx</a><a href="/#how" onClick={e => {e.preventDefault(); navigateHome("#how");}}>Qanday ishlaydi?</a>{trackedOrders.length > 0 && <a href="/#payment" onClick={e => {e.preventDefault(); navigateHome("#payment");}}>Zaklat holati</a>}</nav><div className="header-tools"><label className="language-picker"><select className="customer-language" aria-label="Til" value={language} onChange={event => {selectLanguage(event.target.value); setLanguage(event.target.value);}}>
 {Object.entries(languages).map(([code, label]) => <option key={code} lang={code} value={code}>{`${flags[code]}  ${label}`}</option>)}</select></label><a className="header-action" href="/booking" onClick={e => {e.preventDefault(); navigateBooking();}}>Buyurtma berish</a><button className="menu-button icon-button" aria-label="Menyuni ochish" aria-expanded={menu} onClick={()=>setMenu(!menu)}>{menu ? <X/> : <Menu/>}</button></div></div></header>
{bookingPage ? <main className="booking-page"><section className="section booking-workspace"><a className="back-home" href="/" onClick={e => {e.preventDefault(); navigateHome();}}><ArrowLeft size={16} className="flip-rtl" aria-hidden="true"/>Bosh sahifa</a><h1>Buyurtma berish</h1><nav className="booking-progress" aria-label="Buyurtma bosqichlari">{bookingSteps.map((label, index) => <button key={label} aria-current={step === index ? 'step' : undefined} disabled={index > step} onClick={() => navigateBooking(index)}><span>{index + 1}</span>{label}</button>)}</nav><div className="booking-grid"><div className="booking-content"><div hidden={step !== 0} className="route-panel"><h2>Yo‘nalish va sana</h2><p className="step-help">Qaysi yo‘nalishda va qachon xizmat kerak?</p><div className="route-options">{Boolean(commonRates.length) && <label className="priced-route">Tarifli yo‘nalishlar
   <select value={commonRates.findIndex(rate => rate.from === start.name && rate.to === end.name)} onChange={event => {
     const rate = commonRates[Number(event.target.value)];
     selectPlace(rate.from, 'start');
     selectPlace(rate.to, 'end');
   }}>
     <option value={-1} disabled>Yo‘nalishni tanlang</option>
     {commonRates.map((rate, index) => <option key={index} value={index}>{displayName(places.find(p => p.name === rate.from)) || rate.from} {routeArrow()} {displayName(places.find(p => p.name === rate.to)) || rate.to} · {money(rate.amount)} so‘m</option>)}
   </select></label>}<div className="route-fields">{[['start','Qayerdan?',start],['end','Qayerga?',end]].map(([which,label,p])=><label className={`location-field ${active===which?'focused':''}`} key={which}><span className={`point ${which}`}/><span><small>{label}</small><select aria-label={label} value={p.name} onChange={e=>selectPlace(e.target.value,which)}>{!places.some(v=>v.name===p.name)&&<option>{p.name}</option>}{places.map(v=><option key={v.name} value={v.name}>{displayName(v)}</option>)}</select></span><ChevronDown size={16}/></label>)}</div></div>
 <div className="event-fields"><label><span><CalendarDays size={16}/> Tadbir sanasi</span><input id="event-date" aria-label="Tadbir sanasi" type="date" min={today} value={date} onChange={e=>setDate(e.target.value)} required/></label><label><span><Clock3 size={16}/> Boshlanish vaqti</span><input aria-label="Boshlanish vaqti" type="time" value={time} onChange={e=>setTime(e.target.value)} required/></label></div></div><div hidden={step !== 1} className="booking-catalog">{catalog}
</div><div hidden={step !== 2} className="route-panel"><h2>Aniq manzillar</h2><p className="step-help">Haydovchi uchun olib ketish va borish joylarini belgilang.</p><div className="endpoint-list" role="group" aria-label="Yo‘nalish manzillari">
 {['start', 'end'].map(which => {
   const point = exactLocations[which];
   const needsTariff = point && !matchesTariff(which === 'start' ? start : end, point);
   const label = which === 'start' ? 'Olib ketish' : 'Borish';
   let detail = point?.address || 'Manzilni tanlash uchun bosing';
   if (locationDirty[which]) detail = 'O‘zgarishlarni tasdiqlang';
   else if (needsTariff) detail = 'Hudud uchun tarifni tanlang';
   return <button id={`route-${which}`} key={which} type="button" aria-pressed={active === which} onClick={() => setActive(which)}>
     <span className={`endpoint-dot ${which}`} aria-hidden="true"/>
     <span className="endpoint-text"><strong>{label}</strong><span>{detail}</span></span>
     {point && !locationDirty[which] && !needsTariff && <CheckCircle2 size={18} aria-label="Tasdiqlandi"/>}
   </button>;
 })}
 </div>
 {['start','end'].map(which => <div key={which} hidden={active !== which} className="location-editor" role={active === which ? 'region' : undefined} aria-label={which === 'start' ? 'Olib ketish manzili' : 'Borish manzili'}><button className="editor-close car-select" onClick={() => setActive(null)}>Yopish <X size={16}/></button>
   <LocationPicker title={which === 'start' ? 'Qayerdan olib ketamiz?' : 'Qayerga borasiz?'} key={which} initialPoint={which === 'start' ? start : end} value={exactLocations[which]} onConfirm={point => confirmExact(which, point)} onDirty={dirty => setLocationDirty(previous => ({...previous, [which]: dirty}))}/>
 </div>)}
 </div><div hidden={step !== 3} className="route-panel"><h2>Tekshirish va band qilish</h2><div className="review-details"><h3>Buyurtma tafsilotlari</h3><p>{date} · {time}</p><div><strong>Olib ketish</strong><p>{exactLocations.start?.address}</p></div><div><strong>Borish</strong><p>{exactLocations.end?.address}</p></div><button className="car-select" onClick={() => navigateBooking(2)}>Manzillarni o‘zgartirish</button></div><form className="review-form" onSubmit={submit}><label>Ismingiz<input autoComplete="name" required minLength={2} maxLength={80} value={name} onChange={e=>setName(e.target.value)} placeholder="Ismingizni kiriting"/></label><label>Telefon raqamingiz<input type="tel" dir="ltr" autoComplete="tel" required pattern="\+998[0-9]{9}" title="+998 va 9 ta raqam, masalan +998901234567" value={phone} onChange={e=>setPhone(e.target.value)} placeholder="+998901234567"/></label><div className="payment-preview"><CreditCard/><div><b>Karta orqali zaklat</b><p>{price ? money(price.deposit) + ' ' + translate('so‘m · jami narxning 20%') : "Tarif belgilanmagan"}</p></div></div><p className="notice">So‘rov yuborilgach, demo karta va chek yuklash bo‘limi ochiladi.</p>{submitError && <p className="error" role="alert">{submitError}</p>}<button className="button primary full" type="submit" disabled={saving || !price || !locationsReady || !catalogReady}>{saving ? "Yuborilmoqda…" : "So‘rovni yuborish"}</button></form></div>{error && <p className="error" role="alert">{error}</p>}<div className="booking-actions">{step > 0 && <button className="button secondary" onClick={() => navigateBooking(step - 1)}>Orqaga</button>}{step < 3 && <button className="button primary" onClick={continueBooking}>Davom etish</button>}</div></div> <aside className="summary booking-summary">{!selectedCars.length ? <div className="booking-empty">
 <CarFront size={30} aria-hidden="true"/><h3>Avtomobil tanlang</h3><p>Narxni ko‘rish uchun katalogdan avtomobil qo‘shing.</p><a className="button primary" href="/booking#cars" onClick={e => {e.preventDefault(); navigateBooking(1);}}>Avtomobillarni ko‘rish</a>
 </div> : <><div className="summary-top"><span>BUYURTMANGIZ</span><span className="demo-label">{price ? "Belgilangan tarif" : "Tarif belgilanmagan"}</span></div>{selectedCars.map(vehicle => <div key={vehicle.id} className="summary-car"><CarImage car={vehicle} decorative/><div><h3>{displayName(vehicle)}</h3><small>{quote(vehicle,start,end) ? money(quote(vehicle,start,end).total) + ' ' + translate('so‘m / dona') : 'Bu yo‘nalishda tarif yo‘q'}</small>{quantityControls(vehicle)}</div></div>)}<a className="basket-link" href="/booking#cars" onClick={e => {e.preventDefault(); navigateBooking(1);}}>{selectedCars.length ? 'Yana avtomobil qo‘shish' : 'Avtomobil tanlash'}</a>{price ? <><div className="price-lines"><div><span>{displayName(start)} {routeArrow()} {displayName(end)}</span></div></div><div className="total"><span>Jami</span><b>{money(price.total)} <small>so‘m</small></b></div><div className="deposit"><div><span><ShieldCheck size={18}/> Hozir to‘lanadigan zaklat</span><b>20%</b></div><strong>{money(price.deposit)} <small>so‘m</small></strong><p>Qolgan {money(price.remainder)} so‘m — xizmat kuni.</p></div></> : <p className="notice">{!selectedCars.length ? "Buyurtmani boshlash uchun katalogdan avtomobil qo‘shing." : commonRates.length ? "Barcha tanlangan avtomobillar uchun ro‘yxatdan yo‘nalish tanlang." : "Tanlangan avtomobillar uchun umumiy tarifli yo‘nalish yo‘q. Avtomobil tanlovini o‘zgartiring."}</p>}<p className="summary-note"><ShieldCheck size={15}/> Zaklat holati chek tekshirilgach yangilanadi.</p></>}{catalogError && <p className="error" role="alert">{catalogError} <button type="button" onClick={() => loadCars()}>Qayta yuklash</button></p>}</aside></div><div className="mobile-booking-total"><span>Jami <b>{price ? money(price.total) + ' ' + translate('so‘m') : 'Avtomobil tanlang'}</b></span>{step < 3 && <button className="button primary" onClick={continueBooking}>Davom etish</button>}</div></section></main> : <main><section className="hero"><div className="hero-media" aria-hidden="true"><img src="/images/hero-convoy.jpg" alt="" fetchPriority="high"/></div><div className="hero-inner"><div className="hero-copy"><div className="eyebrow"><span/> XORAZM BO‘YLAB KARTEJ XIZMATI</div><h1>Unutilmas kun.<br/><em>Munosib avtomobil.</em></h1><p>To‘ylar, mehmonlar va biznes safarlari uchun haydovchili avtomobillar.<br className="desktop"/> Avtomobil tanlang, yo‘nalishni belgilang — qolganini bizga ishoning.</p><div className="hero-actions"><a className="button primary" href="#cars" onClick={e => {e.preventDefault(); navigateHome("#cars");}}>Avtomobil tanlash</a><a className="text-link" href="/booking" onClick={e => {e.preventDefault(); navigateBooking();}}>Buyurtma berish <ArrowRight size={16} className="flip-rtl" aria-hidden="true"/></a></div></div></div></section>
 <section className="section occasions"><div className="section-heading centered"><div><span className="eyebrow">XIZMATLARIMIZ</span><h2>Har bir safar uchun munosib avtomobil</h2></div></div><div className="occasion-grid">{occasions.map(({icon: Icon, title, text}) => <article key={title}><span className="occasion-icon"><Icon size={22} aria-hidden="true"/></span><h3>{title}</h3><p>{text}</p></article>)}</div></section>
{catalog}
<section className="section home-booking"><div className="cta-band"><div><h2>Kuningizni rejalashtiring</h2><p>Yo‘nalish va sanani belgilang, avtomobillarni tanlang.</p></div><a className="button primary" href="/booking" onClick={e => {e.preventDefault(); navigateBooking();}}>Buyurtmani boshlash <ArrowRight size={18} className="flip-rtl" aria-hidden="true"/></a></div></section> <ReceiptPayment key={trackedOrders[0]?.id} orders={trackedOrders}/>
 <section id="how" className="section how"><div><span className="eyebrow">ODDIY VA TUSHUNARLI</span><h2>Buyurtma berish tartibi</h2></div><div className="steps"><article><CalendarDays/><h3>Yo‘nalish va sanani belgilang</h3><p>Shahar yoki tuman, xizmat kuni va vaqtini tanlang.</p></article><article><CarFront/><h3>Avtomobilni tanlang</h3><p>Tantanangizga mos avtomobilni tanlang.</p></article><article><MapPin/><h3>Manzilni ko‘rsating</h3><p>Boshlanish va borish manzilini tanlab, belgilangan narxni ko‘ring.</p></article><article><ShieldCheck/><h3>Zaklat bilan band qiling</h3><p>Demo chekni yuboring va zaklat holatini shu sahifada kuzating.</p></article></div></section></main>}<footer className="site-footer"><div className="footer-inner"><div className="footer-about"><a href="/" onClick={e => {e.preventDefault(); navigateHome();}} className="brand footer-brand"><span className="brand-icon"><CarFront size={20}/></span><span>URGANCH <b>KARTEJ</b></span></a><p>Go‘zal kuningizning go‘zal boshlanishi.</p></div><nav className="footer-links" aria-label="Urganch Kartej"><a href="/#cars" onClick={e => {e.preventDefault(); navigateHome("#cars");}}>Avtomobillar</a><a href="/booking" onClick={e => {e.preventDefault(); navigateBooking();}}>Yo‘nalish va narx</a><a href="/#how" onClick={e => {e.preventDefault(); navigateHome("#how");}}>Qanday ishlaydi?</a></nav><ContactLinks/></div><div className="footer-bottom"><small>© {new Date().getFullYear()} Urganch Kartej</small><a className="admin-link" href="/admin">Admin panel</a></div></footer>
 {modal&&<div className="modal-backdrop" onClick={e=>{if(e.target===e.currentTarget&&!saving)setModal(false)}}><div className="modal" role="dialog" aria-modal="true" aria-labelledby="modal-title" tabIndex={-1} ref={dialogRef}><button className="close icon-button" aria-label="Yopish" disabled={saving} onClick={()=>setModal(false)}><X/></button><CheckCircle2 className="success-icon" size={48}/><h2 id="modal-title">So‘rov saqlandi</h2><p>{name}, buyurtma so‘rovingiz saqlandi.</p><div className="request-id">{savedOrder.reference}<span>Zaklat kutilmoqda</span></div><dl><div><dt>Avtomobillar</dt><dd>{orderCars(savedOrder)}</dd></div><div><dt>Sana va vaqt</dt><dd>{date} · {time}</dd></div><div><dt>Telefon</dt><dd>{phone}</dd></div><div><dt>Zaklat</dt><dd>{money(savedOrder.deposit)} so‘m</dd></div></dl><a className="button primary full" href="/#payment" onClick={e => {e.preventDefault(); setModal(false); navigateHome("#payment");}}>Zaklat va chekni yuborish</a></div></div>}
 </>;
}
createRoot(document.getElementById('root')).render(location.pathname.replace(/\/$/, '') === '/admin' ? <Admin/> : <App/>);
