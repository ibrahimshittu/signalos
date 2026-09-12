# SignalOS backend

SignalOS is a personalized investment studio: Supabase authenticates users and stores domain data,
Bybit supplies account/market data and accepts only user-confirmed orders, Pydantic AI produces
evidence-gated proposals, and Expo notifies the user when a proposal is ready.

Agents cannot access broker credentials or submit orders. A user must open a short-lived immutable
order review in SignalOS, complete Supabase MFA, and explicitly submit its exact proposal hash.

## First run

1. Complete [the Supabase, Bybit, and Expo setup guide](docs/setup.md).
2. Copy `.env.example` to `.env` and fill every required value.
3. Install, migrate, and run:

```sh
uv sync --extra dev --extra research
uv run alembic upgrade head
uv run uvicorn signalos_backend.main:app --reload
```

In separate terminals, start market analysis, broker reconciliation, and Expo receipt
reconciliation:

```sh
uv run signalos-market-worker
uv run signalos-execution-worker
uv run signalos-notification-worker
```

Verify the API at `http://localhost:8001/v1/health` and its development documentation at
`http://localhost:8001/docs`.

## Runtime contract

- Supabase Auth and Postgres are required in development, staging, and production.
- SQLite and the test identity header are available only when `SIGNALOS_ENVIRONMENT=test`.
- Email/password is the only v1 sign-in provider. Configure confirmation and custom SMTP in
  Supabase; the backend validates the resulting access token against Supabase JWKS.
- Enable Supabase TOTP MFA. Submit, cancel, full-close, and protection-change endpoints require an
  `aal2` access token whose second factor was verified within the last five minutes.
- One encrypted Bybit key is connected during onboarding. It must be read-write with spot and/or
  contract order permission, but no wallet transfer or withdrawal permission.
- Expo push is a delivery hint. The proposal feed in PostgreSQL is the source of truth.
- Alembic is the only runtime schema writer; application startup does not create Supabase tables.

## Commands

| Command | Purpose |
|---|---|
| `uv run pytest -q` | Run the offline test suite |
| `uv run ruff check .` | Run static checks |
| `uv run ruff format --check .` | Verify formatting |
| `uv run alembic upgrade head` | Apply Supabase schema migrations |
| `uv run alembic check` | Detect ORM/migration drift |
| `uv run signalos-market-worker --once` | Run one mainnet scan and eligible analysis cycle |
| `uv run signalos-market-worker` | Run continuous scans, analysis, proposals, and notifications |
| `uv run signalos-execution-worker` | Reconcile Bybit orders, executions, and positions every 5 seconds |
| `uv run signalos-notification-worker --once` | Reconcile Expo receipts once |
| `docker compose up --build` | Run API and all workers against Supabase |

## Safety boundaries

- Model-facing tools are read-only and never receive broker or Expo secrets.
- Bybit, Expo, and operator secrets are write-only at the API/configuration boundary, encrypted or
  held in process memory, and scrubbed from traces.
- The 20× leverage value is an absolute ceiling for eligible advanced derivatives profiles, never a
  default. Each opportunity is sized again from its stop, model confidence, Bybit symbol limit,
  account equity, available margin, freshly reconciled position notional, directional exposure,
  and correlation. Stale position state produces no proposal. The model cannot loosen those
  deterministic boundaries.
- A separate Personal Portfolio Advisor sees an identifier-free view of one user's explicit
  profile, learned preferences, and open positions. It may reject or reduce a global market idea;
  it cannot increase confidence, leverage, loss limits, or permissions.
- Submission uses a unique Bybit `orderLinkId`. Transport ambiguity becomes `submission_unknown`;
  SignalOS does not blindly retry and risk a duplicate order.
- Bybit order acknowledgements are provisional. A dedicated worker polls broker truth every five
  seconds and stores partial fills, fills, executions, open positions, and closures in Supabase.
- Executable v1 proposals use bounded limit prices. Market-order review is rejected until an exact
  maximum-slippage term can be included in the immutable proposal hash.
- Push notifications contain only a proposal ID and navigation type. They never contain API keys or
  trigger an order.
- CI uses fakes and recorded responses and never writes to Bybit mainnet.

## Time-series storage

Use Supabase PostgreSQL 17 without TimescaleDB. Supabase has deprecated TimescaleDB on PostgreSQL
17; when raw candles require partitioning, add native range partitions managed by `pg_partman` and
`pg_cron`. Do not introduce a second time-series database until measured retention or query-load
requirements justify the operational cost. See [the setup guide](docs/setup.md#timeseries).
