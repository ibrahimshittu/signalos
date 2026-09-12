from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path

from alembic import command
from alembic.config import Config


def test_initial_migration_upgrades_and_downgrades(tmp_path: Path) -> None:
    database_path = tmp_path / "migration.db"
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{database_path}")

    command.upgrade(config, "head")

    with closing(sqlite3.connect(database_path)) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
    assert {
        "account_snapshots",
        "broker_connections",
        "broker_contexts",
        "broker_credentials",
        "broker_executions",
        "broker_orders",
        "broker_positions",
        "broker_reconciliation_checkpoints",
        "execution_action_reviews",
        "execution_actions",
        "investment_profiles",
        "market_instruments",
        "market_latest_tickers",
        "market_scan_candidates",
        "market_scan_runs",
        "order_reviews",
        "personalized_investment_policies",
        "notification_deliveries",
        "push_devices",
        "trade_proposals",
        "user_memories",
    } <= tables

    command.check(config)

    command.downgrade(config, "base")

    with closing(sqlite3.connect(database_path)) as connection:
        remaining = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
    assert remaining <= {"alembic_version"}
