"""Keep automated tests isolated from the required Supabase runtime configuration."""

import os

os.environ.setdefault("SIGNALOS_ENVIRONMENT", "test")
os.environ.setdefault("SIGNALOS_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
