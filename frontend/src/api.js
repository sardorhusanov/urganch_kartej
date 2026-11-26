import {telegramInitData} from './telegram';

const sessionKey = 'kartej-admin-session';

export function getToken() {
  return sessionStorage.getItem(sessionKey);
}

export function setToken(token) {
  if (token) sessionStorage.setItem(sessionKey, token);
  else sessionStorage.removeItem(sessionKey);
}

export async function api(path, {method = 'GET', body, admin = false, signal, orderToken, binary = false} = {}) {
  const headers = {};
  if (orderToken) headers['X-Order-Token'] = orderToken;
  if (telegramInitData()) headers['X-Telegram-Init-Data'] = telegramInitData();
  if (admin && getToken()) headers.Authorization = `Bearer ${getToken()}`;
  if (body != null && !(body instanceof FormData)) {
    headers['Content-Type'] = 'application/json';
    body = JSON.stringify(body);
  }

  const response = await fetch(`/api${path}`, {method, body, headers, signal, cache: 'no-store'});
  if (response.status === 204) return;
  if (binary && response.ok) return response.blob();
  const data = await response.json().catch(() => null);
  if (!response.ok || data === null) {
    const error = new Error(typeof data?.detail === 'string' ? data.detail : 'So‘rovni bajarib bo‘lmadi. Ma’lumotlarni tekshiring.');
    error.status = response.status;
    if (admin && response.status === 401) {
      setToken(null);
      window.dispatchEvent(new Event('admin-session-expired'));
    }
    throw error;
  }
  return data;
}
