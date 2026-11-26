// Telegram Mini App integration. Outside Telegram every export is a harmless no-op.
export const webApp = typeof window !== 'undefined' ? window.Telegram?.WebApp : undefined;
export const inTelegram = Boolean(webApp?.initData);

export function telegramInitData() {
  return inTelegram ? webApp.initData : '';
}

export function telegramUser() {
  return inTelegram ? webApp.initDataUnsafe?.user ?? null : null;
}

if (inTelegram) {
  document.documentElement.classList.add('in-telegram');
  try {
    webApp.ready();
    webApp.expand();
    webApp.setHeaderColor?.('#ffffff');
    webApp.setBackgroundColor?.('#ffffff');
    webApp.disableVerticalSwipes?.();
  } catch {}
}

// Show Telegram's native back button on inner pages.
export function syncBackButton(visible, back) {
  if (!inTelegram || !webApp.BackButton) return () => {};
  if (visible) {
    webApp.BackButton.show();
    webApp.BackButton.onClick(back);
  } else {
    webApp.BackButton.hide();
  }
  return () => webApp.BackButton.offClick(back);
}
