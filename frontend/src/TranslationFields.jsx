import React from 'react';
import {languages} from './languages';

const otherLanguages = Object.entries(languages).filter(([code]) => code !== 'uz');

export function readTranslations(fields) {
  const translations = {};
  for (const [code] of otherLanguages) {
    const name = fields.get('name-' + code)?.trim();
    if (name) translations[code] = {name};
  }
  return translations;
}

export default function TranslationFields() {
  return <details><summary>Boshqa tillardagi nomlar</summary>
    <p>Tarjima kiritilmasa, asosiy nom ishlatiladi.</p>
    {otherLanguages.map(([code, label]) => <label key={code}>{label}
      <input name={'name-' + code} lang={code} dir="auto" maxLength={80}/>
    </label>)}
  </details>;
}
