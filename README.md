# Urganch Kartej

React customer site and FastAPI admin dashboard for chauffeur-driven event bookings. The backend owns the shared car catalog, route pricing, orders, manual zaklat records, and uploaded photos.

## Project layout

- `frontend/`: React source, public assets, Vite configuration, npm manifests, and build output (`dist/`).
- `backend/`: FastAPI application and local data.
- `pyproject.toml` and `uv.lock`: backend dependencies and their locked versions.
- `.venv/`: backend virtual environment managed by uv (not committed).
- `api/`: Vercel Python entry point.
- `telegram_bot/`: Telegram bot and Mini App integration, served by the backend through a webhook. See [its README](telegram_bot/README.md) for setup.
- `vercel.json`: deployment configuration, with the project root kept at this directory.

## Run locally

From the project directory, with [uv](https://docs.astral.sh/uv/getting-started/installation/) and Node 22+ installed. uv manages Python 3.12 using `.python-version`:

```sh
uv sync --locked
npm install --prefix frontend
npm run build --prefix frontend
uv run --locked uvicorn backend.main:app --reload
```

No manual virtual-environment activation is needed. Add or remove backend dependencies with `uv add <package>` or `uv remove <package>`; commit both `pyproject.toml` and `uv.lock`. Use `uv sync --locked` after pulling changes. To intentionally upgrade dependencies, run `uv lock --upgrade` followed by `uv sync --locked`.

Open [the customer site](http://127.0.0.1:8000/) or [the admin dashboard](http://127.0.0.1:8000/admin). FastAPI serves both from the same origin. The API schema is at [`/docs`](http://127.0.0.1:8000/docs).

The default admin username is `admin`. Set `KARTEJ_ADMIN_USERNAME` before starting FastAPI to choose a different username. On first start, FastAPI generates an admin password in `backend/data/admin-password`. Read it locally with `cat backend/data/admin-password` and use it to sign in. Set `KARTEJ_ADMIN_PASSWORD` (at least 12 characters) to use your own password. Admin sessions last eight hours. Keep the password and database files private.

For frontend development, leave FastAPI running and run `npm run dev --prefix frontend` in another terminal. Vite proxies `/api` to port 8000 by default. Set `KARTEJ_API_URL` if the API runs elsewhere. Run `npm test --prefix frontend` for the pricing tests.

## Bookings and pricing

- Admin can add cars and choose a JPEG, PNG, or WebP photo up to 4 MB. To replace a photo, expand **Manzillar va narxlar** on the car. The server checks and converts the file before storing it.
- In **Avtomobillar → Manzillar va narxlar**, add a pickup or destination for that car by giving it a name and placing a map pin or entering coordinates. The saved address is selected automatically and appears for customers who choose that car.
- Admin sets a fixed fare for each car, pickup, and destination. Customers can book routes with a saved fare. The deposit is 20% of that fare.
- FastAPI recalculates the quote when the customer submits. If the price changed, the customer reviews the updated total before trying again. Orders retain their quoted price and 20% zaklat.
- After booking, the customer sees a clearly labeled demo card and can upload a JPEG, PNG, or WebP receipt screenshot up to 4 MB. The **Zaklat holati** section restores the tracking entry on the same browser and checks for decisions automatically.
- In **Buyurtmalar**, admins can filter pending receipts, preview the private image, and approve or reject it with a reason. Approval records the deposit. Rejected receipts can be replaced. This demo flow does not initiate or verify any real transfers.

## Data and hosting

SQLite stores bookings, car-specific addresses, admin sessions, rates, and images in `backend/data/kartej.sqlite3`. Use `KARTEJ_DATA` to select a different persistent directory. The initial fleet comes from `frontend/src/fleet.json`. Previous browser-only demo records stay in the browser and are not imported.

Location maps use OpenStreetMap and Geoapify. The existing OSRM routing endpoint remains available for clients that use it; set `KARTEJ_ROUTING_URL` to choose its server. Built-in model image credits are in `frontend/public/images/sources.json`.

Vercel installs the backend dependencies from the root `pyproject.toml` and `uv.lock`; keep the Vercel project root at this directory.

On Vercel, the frontend is served from Vite’s build output and `api/index.py` serves FastAPI. Configure `DATABASE_URL` with PostgreSQL and `KARTEJ_ADMIN_PASSWORD` in the Production environment. The API initializes its tables and seeds the fleet on first use. The application currently uses one admin account and manual transfers.

## Exact locations and OpenStreetMap and Geoapify

The customer booking flow supports address/building lookup, a separate business-name search, map clicks, draggable pins, and browser GPS requested only after pressing **Hozirgi joylashuvim**. Users review/edit the address and explicitly confirm each endpoint. GPS accuracy is displayed; a GPS permission refusal, provider timeout, or missing API key leaves manual address/coordinate entry available. Changing a point or address invalidates its confirmation. Admins use the same picker when adding a car-specific address.

Coordinates are classified by the backend against `backend/geography/xorazm.geojson`, independently of the map provider. Users never select an area. See [boundary data and accuracy](backend/geography/README.md) for the 11 districts / 3 cities, provenance, provisional city outlines, versioning, and future nested custom areas. This is a working service-area dataset, not a certified administrative boundary dataset.

Existing directional route tariffs remain in use. Exact endpoints are stored separately as `exactStart` / `exactEnd`, including the address, coordinates, source, optional GPS accuracy, classification path, and boundary version. Where possible, confirming a location selects a saved tariff endpoint in that area. The server rejects exact points outside the selected tariff's area (descendant areas are allowed), preventing an unrelated low-priced route from being used. No new district-based prices are invented. Drivers/admins see exact endpoints and OpenStreetMap links. Older orders/clients remain supported.

### Keys and activation

Create a project at [Geoapify](https://myprojects.geoapify.com/) and set its server-side key as `GEOAPIFY_API_KEY` in Vercel Production. Redeploy to enable forward and reverse geocoding. Leaflet displays OpenStreetMap tiles and supports GPS and manual pins even before the key is configured. Search uses a regional bounding box and the backend validates returned coordinates against the Xorazm polygons.

For local development, put the variables into the ignored root `.env.local` and start:

```sh
uv run --locked --env-file .env.local uvicorn backend.main:app --reload
npm run dev --prefix frontend
```

Only the provider name and capability flags are returned by `/api/locations/config`. Search/geocoding keys and raw provider responses are never sent to the frontend, logged, or persisted. Search and reverse-geocoding responses are not cached. The confirmation response itself is not a standalone saved record: it is persisted when an address or booking is submitted.

Endpoints: `GET /api/locations/config`, `GET /api/locations/areas`, `GET /api/locations/boundaries`, `GET /api/locations/search?q=...&kind=address|business`, `GET /api/locations/reverse?lat=...&lng=...`, `POST /api/locations/classify`, and `POST /api/locations/confirm`.

Run backend geometry, provider-error, persistence, and booking tests with:

```sh
uv sync --locked
uv run --locked python -m unittest discover -s backend/tests -v
```
