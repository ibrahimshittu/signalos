# SignalOS

A personal investment studio: connected portfolios, market reviews, and proposals you control.

The Expo app uses Supabase email authentication and FastAPI for real account data. Market workers
screen Bybit and evaluate eligible strategies. Orders require an exact proposal, fresh review,
recent MFA, and explicit confirmation. Agents cannot access broker credentials or place orders.
Withdrawals and transfers are not permitted.

## Requirements

- Python 3.12+ and [uv](https://docs.astral.sh/uv/getting-started/installation/).
- Node.js 22.13+ and npm. For iOS: macOS, Xcode 26.4+, and an installed simulator runtime.
  See the [Expo SDK 57 requirements](https://docs.expo.dev/versions/v57.0.0/).
- A Supabase development project and an Expo access token.
- A Bybit account to connect; an OpenRouter key for model-backed analysis.

Use a native development build, not Expo Go, for the full app. Web is useful for layout checks,
not native acceptance. No manually activated Python venv is needed: `uv` selects `backend/.venv`.

## 1. Install and configure

From the repository root:

```sh
cd backend
uv sync --extra dev --extra research
test -f .env || cp .env.example .env
cd ../mobile
npm ci
test -f .env || cp .env.example .env
```

Keep existing `.env` files. Do not commit them or copy backend secrets into the mobile app.

### Backend — `backend/.env`

Fill the placeholders in the example. Required runtime values:

| Variable | What to supply |
| --- | --- |
| `SIGNALOS_ENVIRONMENT` | `development` locally |
| `SIGNALOS_SUPABASE_URL` | Your Supabase project URL |
| `SIGNALOS_DATABASE_URL` | Supabase Postgres URL with a `postgresql+asyncpg://` prefix |
| `SIGNALOS_API_KEY` | Generated internal operator secret; never a mobile key |
| `SIGNALOS_CREDENTIAL_ENCRYPTION_KEY` | Generated Fernet key, kept stable across restarts |
| `SIGNALOS_EXPO_ACCESS_TOKEN` | Expo token for enhanced push security; required by current runtime validation |

Generate the operator secret and encryption key from `backend/`, then put the results in `.env`:

```sh
openssl rand -hex 32
uv run python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Use a direct database connection where IPv6 is available, or the **Session pooler on port 5432**.
URL-encode special characters in the password. This asyncpg setup is not configured for the
transaction pooler. See [Supabase connection options](https://supabase.com/docs/guides/database/connecting-to-postgres).
SQLite is for isolated tests only, not the running app.

Keep these defaults to begin:

```dotenv
UVICORN_PORT=8001
SIGNALOS_API_BASE_URL=http://localhost:8001
SIGNALOS_TEMPORAL_ENABLED=false
SIGNALOS_LOGFIRE_SEND=false
```

`SIGNALOS_API_BASE_URL` is used by optional research workflow clients. It does not bind the server
or configure the phone. Temporal is optional; the workers below do not require it. Add
`SIGNALOS_OPENROUTER_API_KEY` for live AI analysis. Missing configuration produces an unavailable
result, not a fabricated proposal.

### Mobile — `mobile/.env`

```dotenv
EXPO_PUBLIC_SIGNALOS_API_URL=http://127.0.0.1:8001
EXPO_PUBLIC_SUPABASE_URL=https://YOUR_PROJECT_REF.supabase.co
EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY=sb_publishable_YOUR_KEY
```

For a physical iPhone, replace `127.0.0.1` with your Mac's LAN address, for example
`http://192.168.1.20:8001`. Keep both devices on the same trusted network and allow local network
access. Restart Metro after changing environment variables.

Only the Supabase **publishable** key belongs here. Never expose database passwords, secret/service
role keys, Bybit secrets, or operator keys through `EXPO_PUBLIC_*`.

### Supabase Auth

Use the same project in both files. Enable Email, disable unused social providers, and configure
SMTP for delivery to real users. Allow these native redirect URLs in Auth URL Configuration:

```text
signalos://auth/callback
signalos://auth/recovery
```

Configure an asymmetric signing key and TOTP MFA for protected broker actions. Do not bypass MFA
or verification to make order submission work. See the [backend setup guide](backend/docs/setup.md)
and [Supabase redirect documentation](https://supabase.com/docs/guides/auth/redirect-urls).

## 2. Apply database migrations

From the repository root:

```sh
cd backend
uv run --env-file .env alembic upgrade head
```

Verify that the database URL targets your development project first. API startup does not create
the production schema automatically.

## 3. Start the API and workers

Run each block in a **separate terminal**, starting at the repository root.

**API — port 8001**

```sh
cd backend
uv run --env-file .env uvicorn signalos_backend.main:app --host 0.0.0.0 --port 8001 --reload
```

Check [health](http://127.0.0.1:8001/v1/health) and [API docs](http://127.0.0.1:8001/docs).
Binding `0.0.0.0` allows a phone on your trusted LAN to connect; do not expose the development
server to the public internet.

**Market scanning and proposal analysis**

```sh
cd backend
uv run --env-file .env signalos-market-worker --environment testnet
```

**Order and position reconciliation**

```sh
cd backend
uv run --env-file .env signalos-execution-worker --environment testnet
```

**Notification retries and receipts**

```sh
cd backend
uv run --env-file .env signalos-notification-worker
```

These examples explicitly use **Testnet**. Use `--environment mainnet` on both market and execution
workers for a connected Live account. Bybit Demo Trading is separate and is not supported by the
current connector. Do not use a Demo key as a Testnet key.

The API does not launch workers. Stop each process with `Ctrl+C`. Workers accept `--once` for one
cycle; market analysis makes real provider/model requests and can incur costs.

### What updates, and when?

| Activity | Default behavior |
| --- | --- |
| Market screening | Runs a cycle, then waits 60 seconds |
| Deeper strategy review | Normally due every 300 seconds; initial, manual, and session events can prompt it sooner |
| Orders and positions | Reconciliation cycle, then a 5-second wait |
| Push retries and receipts | Processing cycle, then a 900-second wait |

Work takes time, so these are not exact wall-clock schedules. Intervals are configurable in
`backend/.env.example`. Fetching a saved portfolio/review is not the same as starting a scan.
Use Studio's proposal-check action for a review request, Markets for a public market scan, and
portfolio refresh to sync balances. A scan does not guarantee an eligible proposal.

## 4. Build and open the mobile app

In another terminal, from the repository root:

```sh
cd mobile
npm run ios
```

For a connected iPhone, use `npx expo run:ios --device` instead. For subsequent JavaScript-only
changes, start the current development client with:

```sh
cd mobile
npm run start:ios
```

Do not start a second Metro server if the build command already started one. Native dependencies,
config plugins, and entitlements require a rebuild; a JavaScript reload is not enough.

If signing fails, open `mobile/ios/SignalOS.xcworkspace` in Xcode. Under **Signing & Capabilities**,
select your development team and enable automatic signing. The bundle identifier is
`com.signalos.app`; keep it consistent with `mobile/app.json`. Let Xcode register the
device/profile, then retry. Do not copy another team's identity.

If an older app opens with a missing-native-module error, use `npm run start:ios`, which targets
the current app-specific scheme. See [mobile troubleshooting](mobile/README.md).

## Telemetry and push

To send traces, add this to `backend/.env` and restart the API and all workers:

```dotenv
SIGNALOS_LOGFIRE_SEND=true
LOGFIRE_TOKEN=YOUR_PROJECT_WRITE_TOKEN
```

Use **your SignalOS project** token, not another application's token. It determines the
destination. Look for `signalos-backend`, `signalos-market-worker`, `signalos-execution-worker`,
and `signalos-notification-worker`. API traces alone do not prove workers are running.

For push delivery, link the real SignalOS EAS project, configure APNs/FCM, rebuild the client, then
enable notifications in Account. Follow the [push checklist](mobile/README.md#proposal-notifications).
A bundle export or Expo ticket does not prove a physical device received a notification.

## Verify changes

From the repository root, run backend tests with an isolated database:

```sh
SIGNALOS_ENVIRONMENT=test SIGNALOS_DATABASE_URL=sqlite+aiosqlite:///:memory: SIGNALOS_LOGFIRE_SEND=false backend/.venv/bin/pytest backend/tests -q
backend/.venv/bin/ruff check backend/src backend/tests
cd mobile
npm test -- --silent
EXPO_NO_DOTENV=1 npm run lint
npm run typecheck
```

On a development device, check email sign-in, keyboard visibility, provider connection, portfolio
refresh, review details, reduced motion, and large text. Test order submission only against an
explicitly chosen Testnet account with fresh MFA and reviewed terms.

## Current boundaries

This is an integrated development application, not a claim of production readiness.

- Executable proposals require an evidence-approved, promoted strategy. An empty registry is a
  setup block, not evidence of AI rejection. Price-only evaluation does not validate execution
  replay; do not bypass promotion gates.
- Live news, CPI releases, ETF flows, and macro calendars are not operationally connected.
- The drawdown reference is not an implemented automatic drawdown-protection service.
- Account deletion still needs a backend retention/deletion policy. Clearing local state is not
  account deletion.
- Push delivery, signing, and order workflows need physical-device/Testnet acceptance.

See the [backend README](backend/README.md) and [mobile README](mobile/README.md). Real service errors and
empty states are shown honestly; no mock financial data is substituted.
