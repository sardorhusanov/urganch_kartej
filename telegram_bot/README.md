# Telegram bot and Mini App

The bot runs **inside the existing FastAPI backend** through a webhook (`POST /api/telegram/webhook`), so it works on Vercel without a separate server. The Mini App is the same website opened inside Telegram.

## What it does

**Customers**
- **🚘 Buyurtma berish** opens the Mini App booking flow. Orders placed there are linked to the customer's Telegram account. The name and language are prefilled from Telegram, and Telegram's back button moves between booking steps.
- **📋 Buyurtmalarim** shows recent orders: car, date, pickup and destination, total, 20% zaklat, paid/remaining and receipt status. It has no images.
- **💰 Narxlar** lists every car and route fare as text.
- **📞 Aloqa** shows the phone number and Instagram.
- **Receipt in chat:** tap **🧾 Chek yuborish** (or just send a photo when only one order is awaiting payment). The bot stores it exactly like a website upload.
- **Automatic messages:** order received, zaklat approved, receipt rejected (with the reason and a button to resend).

**Admins** (Telegram IDs in `KARTEJ_ADMIN_TELEGRAM_IDS`)
- **Instant alert for every new order**, with customer, phone, car, date, exact pickup/destination, total and zaklat.
  - **📍 Manzillar xaritada** sends both points as Telegram map pins.
  - **🧭 Yo‘nalish** opens the driving route in Google Maps.
- **Instant alert with the receipt photo** when a customer pays, with **✅ Tasdiqlash** / **❌ Rad etish**. Rejecting asks for a reason, which is sent to the customer.
- **📥 Buyurtmalar** lists upcoming orders with status icons (🕓 waiting for receipt · ⏳ needs review · ✅ zaklat paid).
- **⏳ Zaklat tekshiruvi** shows every receipt still waiting for review.
- **🛠 Admin panel** opens the dashboard inside Telegram and signs admins in with their Telegram account (no password). Use it to add cars, photos, addresses and fares.

Approving or rejecting in the bot uses the same backend logic as the dashboard. The deposit is recorded the same way in both places.

## Setup

1. Create a bot with [@BotFather](https://t.me/BotFather) (`/newbot`) and copy the token.
2. Find each admin's numeric Telegram ID, for example with [@userinfobot](https://t.me/userinfobot).
3. Add these environment variables in Vercel → Project → Settings → Environment Variables (Production), and to the ignored root `.env.local` for local use:

   | Variable | Example | Purpose |
   |---|---|---|
   | `TELEGRAM_BOT_TOKEN` | `123456:ABC…` | Bot token from BotFather |
   | `TELEGRAM_WEBHOOK_SECRET` | any long random string | Proves webhook calls come from Telegram |
   | `KARTEJ_ADMIN_TELEGRAM_IDS` | `12345678,87654321` | Who gets admin alerts and tools |
   | `KARTEJ_PUBLIC_URL` | `https://urganch-kartej.vercel.app` | HTTPS address of the site (default shown) |

4. Redeploy, then register the webhook, commands and the **Ilova** menu button once:

   ```sh
   uv run --locked --env-file .env.local python -m telegram_bot.setup
   ```

5. In BotFather, optionally run `/newapp` to add the Mini App to the bot's profile with the same URL.

Without `TELEGRAM_BOT_TOKEN`, the site behaves exactly as before and all notifications are skipped.

## Local development

Telegram can't reach `localhost`, so poll instead of using the webhook:

```sh
uv run --locked --env-file .env.local python -m telegram_bot.poll
```

Polling removes the webhook. Run the setup command again before using the deployed bot. Mini App buttons always open `KARTEJ_PUBLIC_URL`, because Telegram requires HTTPS.

## Files

- `router.py`: webhook and Mini App admin sign-in endpoints
- `handlers.py`: chat commands, buttons, receipt photos, approve/reject
- `notify.py`: alerts sent from the booking flow
- `texts.py`, `keyboards.py`: Uzbek texts, order cards, menus
- `webapp_auth.py`: Mini App `initData` signature check
- `client.py`: small Bot API client (standard library only)
- `setup.py`, `poll.py`: one-time setup and local polling

Tests: `uv run --locked python -m unittest discover -s backend/tests -v`.
