# SignalOS backend setup

## 1. Supabase project

Create one Supabase project for each deployment environment. In development, use a development
project rather than a local SQLite or Postgres substitute.

Official references: [Supabase password auth](https://supabase.com/docs/guides/auth/passwords),
[custom SMTP](https://supabase.com/docs/guides/auth/auth-smtp), and
[database connections](https://supabase.com/docs/guides/database/connecting-to-postgres).

In **Authentication → Providers**:

- keep Email enabled;
- disable Google and every unused social provider;
- keep email confirmation enabled;
- configure Site URL and the SignalOS mobile redirect URL;
- configure custom SMTP before inviting real users.

In **Authentication → Multi-Factor Authentication**, enable TOTP enrollment, challenge, and
verification. SignalOS allows ordinary read APIs at `aal1`, but broker mutations require an `aal2`
access token with a TOTP verification timestamp no older than five minutes. The mobile app should
challenge and verify the user's enrolled factor immediately before submitting, cancelling,
closing, or changing position protection, then send the refreshed access token. See
[Supabase MFA](https://supabase.com/docs/guides/auth/auth-mfa).

In **Authentication → Signing Keys**, use an asymmetric `ES256` or `RS256` signing key. The backend
validates access tokens locally with the project's public JWKS and intentionally does not accept a
legacy shared JWT secret. See [Supabase signing keys](https://supabase.com/docs/guides/auth/signing-keys).

The mobile app needs the Supabase project URL and publishable key for email authentication. The
backend does not need the publishable/anon key. It needs:

- `SIGNALOS_SUPABASE_URL`: Project URL from **Project Settings → API**;
- `SIGNALOS_DATABASE_URL`: SQLAlchemy/asyncpg URL based on the database connection shown by
  **Connect** in Supabase.

For a long-running API and workers, use the direct connection when IPv6 is available. Otherwise use
the Session pooler on port 5432. Prefix the URL with `postgresql+asyncpg://`. Do not use the
transaction pooler for this application because asyncpg prepared-statement behavior requires extra
pooler-specific configuration.

Example shape (replace every placeholder and URL-encode the password):

```dotenv
SIGNALOS_ENVIRONMENT=development
SIGNALOS_SUPABASE_URL=https://PROJECT_REF.supabase.co
SIGNALOS_DATABASE_URL=postgresql+asyncpg://postgres.PROJECT_REF:PASSWORD@POOLER_HOST:5432/postgres
```

Then run `uv run alembic upgrade head`. SignalOS does not call `create_all()` outside tests.
The migrations enable row-level security with no client policies on backend-owned tables. In
**Project Settings → API**, also disable the Data API for the `public` schema; mobile clients should
use Supabase Auth and call FastAPI for SignalOS domain data.

## 2. Backend secrets

Generate the internal operator key:

```sh
openssl rand -hex 32
```

Generate the envelope-encryption key used for the Bybit credential and Expo device tokens:

```sh
uv run python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Set the results as `SIGNALOS_API_KEY` and `SIGNALOS_CREDENTIAL_ENCRYPTION_KEY`. Keep old Fernet keys
in `SIGNALOS_CREDENTIAL_PREVIOUS_ENCRYPTION_KEYS` only during planned rotation.

## 3. Bybit connection

The user creates one Bybit API key and enters it during SignalOS onboarding. The backend verifies
the key before account sync. It must:

- be read-write;
- include Contract `Order`/`Position` and/or Spot `SpotTrade` permission;
- have no Withdraw, AccountTransfer, SubMemberTransfer, or SubMemberTransferList permission;
- be restricted to SignalOS egress IPs for production mainnet.

See Bybit's [API-key metadata](https://bybit-exchange.github.io/docs/v5/user/apikey-info) and
[place-order contract](https://bybit-exchange.github.io/docs/v5/order/create-order).

The key is encrypted before persistence and never returned by an API. Market/account analysis may
create proposals, but only `POST /v1/trade-proposals/{id}/submit` can write an order and it requires a
fresh order review, the exact proposal hash, recent MFA, and an idempotency key.
Executable v1 proposals use limit orders. Market-order submission is fail-closed until bounded
slippage is represented in the reviewed proposal itself.

After submission, `signalos-execution-worker` polls Bybit every five seconds. The API exposes
reconciled orders and positions and supports hash-bound, MFA-confirmed cancel, full reduce-only
close, and stop/target update actions. Every acknowledgement remains provisional until polling
observes Bybit's resulting order or position state.

## 4. Expo push notifications

Create/link the Expo EAS project used by the mobile app. Configure APNs credentials for iOS and FCM
V1 credentials for Android. A physical device and a development build are required to test push on
iOS; a paid Apple Developer account is required for APNs credentials.

Follow Expo's [push setup](https://docs.expo.dev/push-notifications/push-notifications-setup/) and
[server delivery/receipt guidance](https://docs.expo.dev/push-notifications/sending-notifications/).

Enable Expo enhanced push security and create an access token. Set it as:

```dotenv
SIGNALOS_EXPO_ACCESS_TOKEN=YOUR_EXPO_ACCESS_TOKEN
SIGNALOS_EXPO_RECEIPT_INTERVAL_SECONDS=900
```

The mobile app obtains its token with `getExpoPushTokenAsync({ projectId })` and registers it using:

```text
PUT /v1/me/notification-devices/{installation_uuid}
Authorization: Bearer <supabase_access_token>
```

SignalOS encrypts the token. Proposal creation sends an Expo notification; the notification worker
checks receipts and disables a token when Expo returns `DeviceNotRegistered`. Push delivery is not
guaranteed, so the in-app proposal list remains authoritative.

## 5. AI and optional services

`SIGNALOS_OPENROUTER_API_KEY` enables live specialist analysis. Without it, deterministic market,
account, profile, and API components can run, but the worker will not fabricate model-driven
proposals. It records a model-unavailable analysis outcome instead.

The market worker scans the full eligible Bybit USDT universe every 60 seconds and defaults to a
deeper five-candidate analysis every five minutes. Due Tokyo, London, New York, UTC-rollover, and
funding windows can trigger the analysis cycle sooner. Only completed candles are admitted. Tune
the bounded workload with `SIGNALOS_MARKET_ANALYSIS_*`; increasing it directly increases model and
Bybit request volume.

Temporal and Logfire are optional for the first run. Leave `SIGNALOS_TEMPORAL_ENABLED=false` and
`SIGNALOS_LOGFIRE_SEND=false` until their services/projects are configured.

## 6. Run and verify

```sh
cp .env.example .env
uv sync --extra dev --extra research
uv run alembic upgrade head
uv run pytest -q
uv run uvicorn signalos_backend.main:app --reload
```

Then run:

```sh
uv run signalos-market-worker
uv run signalos-execution-worker
uv run signalos-notification-worker
```

### Environment variables

| Variable | Required | Purpose |
|---|---:|---|
| `SIGNALOS_ENVIRONMENT` | yes | `development`, `staging`, or `production` at runtime |
| `SIGNALOS_SUPABASE_URL` | yes | JWT issuer and JWKS origin |
| `SIGNALOS_DATABASE_URL` | yes | Supabase Postgres SQLAlchemy/asyncpg connection |
| `SIGNALOS_API_KEY` | yes | Internal admin/research routes; not a mobile key |
| `SIGNALOS_CREDENTIAL_ENCRYPTION_KEY` | yes | Encrypts Bybit and Expo device secrets |
| `SIGNALOS_EXPO_ACCESS_TOKEN` | yes | Authenticates Expo push requests |
| `SIGNALOS_OPENROUTER_API_KEY` | for AI | Calls the configured producer/verifier models |
| `SIGNALOS_TEMPORAL_*` | no | Optional durable research workflows |
| `SIGNALOS_LOGFIRE_SEND` | no | Sends redacted traces when enabled |
| `SIGNALOS_BYBIT_*` | defaults | Bybit endpoints, timeout, and receive window |
| `SIGNALOS_EXECUTION_*` | defaults | Reconciliation cadence and MFA step-up lifetime |
| `SIGNALOS_MARKET_*` | defaults | Scan cadence and freshness thresholds |

Advanced derivatives profiles are eligible for a maximum mandate ceiling of 20×. This is not the
proposal leverage. Every opportunity receives a lower or equal deterministic value after SignalOS
applies the strategy limit, the model's requested value, Bybit's current symbol limit, stop
distance, available margin, current reconciled position notional, and same-direction exposure. A
separate identifier-free Personal Portfolio Advisor may reject or reduce the idea for that user's
profile; its output cannot raise a deterministic limit. Spot remains 1×.

## Timeseries

Do not enable TimescaleDB in the Supabase project. Supabase documents it as deprecated on
PostgreSQL 17 and supported only for older PostgreSQL 15 projects. SignalOS should use ordinary
normalized tables for profiles, proposals, orders, notification state, and latest-market state.

When historical candles become large enough to need partition management:

1. create a native PostgreSQL range-partitioned candle table by time;
2. use `pg_partman` to create/retain partitions;
3. schedule partition maintenance with `pg_cron`;
4. benchmark retention, compression, and query latency before considering a dedicated Timescale
   service.

References: [Supabase TimescaleDB status](https://supabase.com/docs/guides/database/extensions/timescaledb)
and [migration to pg_partman](https://supabase.com/docs/guides/database/migrating-to-pg-partman).
