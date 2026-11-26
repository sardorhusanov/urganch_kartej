import React from 'react';
import messages from './translations.json';
import {languages} from './languages';

const admin = location.pathname.replace(/\/$/, '') === '/admin';
let language = 'uz';
try {
  const saved = localStorage.getItem('customer-language');
  if (!admin && Object.hasOwn(languages, saved)) language = saved;
} catch {}

export function currentLanguage() { return language; }

export function selectLanguage(next) {
  language = next;
  try { localStorage.setItem('customer-language', next); } catch {}
  applyLanguage();
}

function applyLanguage() {
  document.documentElement.lang = language;
  document.documentElement.dir = language === 'ar' ? 'rtl' : 'ltr';
}
applyLanguage();

export function translate(value) {
  if (typeof value !== 'string' || language === 'uz') return value;
  const key = value.trim();
  const translated = messages[language]?.[key];
  return typeof translated === 'string' ? value.replace(key, () => translated) : value;
}

export function orderCars(order) {
  return order.localizedCars?.[language] || order.carName;
}

export function displayName(record) {
  return record?.translations?.[language]?.name || record?.name;
}

// Translate presentation strings as React creates elements, keeping form values,
// API arguments, user input, and component state in their original representation.
export function localizedElement(type, props, ...children) {
  if (language === 'uz' || (typeof type !== 'string' && type !== React.Fragment)) {
    return React.createElement(type, props, ...children);
  }
  const attributes = {...props};
  for (const name of ['placeholder','aria-label','title','alt']) {
    if (attributes[name]) attributes[name] = translate(attributes[name]);
  }
  if (type === 'option' && attributes.value == null && typeof children[0] === 'string') {
    attributes.value = children[0];
  }
  return React.createElement(type, attributes, ...children.map(translate));
}
