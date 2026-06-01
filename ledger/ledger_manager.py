"""SQLite append-only checkpoint ledger utilities."""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "ledger.db"

_LEDGER_EXTENDED_COLUMNS: tuple[tuple[str, str], ...] = (
    ("request_id", "TEXT"),
    ("response_id", "TEXT"),
    ("round_id", "INTEGER DEFAULT 1"),
    ("checkpoint_path", "TEXT"),
    ("model_version", "TEXT"),
    ("evidence_hash", "TEXT"),
)


def init_db() -> None:
    """Create or migrate the checkpoint ledger table."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS checkpoint_ledger (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                update_id TEXT UNIQUE,
                query_id TEXT,
                client_id TEXT,
                status TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                request_id TEXT,
                response_id TEXT,
                round_id INTEGER DEFAULT 1,
                checkpoint_path TEXT,
                model_version TEXT,
                evidence_hash TEXT
            )
            """
        )

        existing_columns = {
            row[1] for row in conn.execute("PRAGMA table_info(checkpoint_ledger)").fetchall()
        }
        for column_name, column_type in _LEDGER_EXTENDED_COLUMNS:
            if column_name not in existing_columns:
                conn.execute(
                    f"ALTER TABLE checkpoint_ledger ADD COLUMN {column_name} {column_type}"
                )


def log_update(
    update_id: str,
    query_id: str,
    client_id: str,
    status: str,
    *,
    request_id: str | None = None,
    response_id: str | None = None,
    round_id: int = 1,
    checkpoint_path: str | None = None,
    model_version: str | None = None,
    evidence_hash: str | None = None,
) -> bool:
    """Append an update event unless its idempotency key already exists."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                """
                INSERT INTO checkpoint_ledger (
                    update_id,
                    query_id,
                    client_id,
                    status,
                    request_id,
                    response_id,
                    round_id,
                    checkpoint_path,
                    model_version,
                    evidence_hash
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    update_id,
                    query_id,
                    client_id,
                    status,
                    request_id,
                    response_id,
                    round_id,
                    checkpoint_path,
                    model_version,
                    evidence_hash,
                ),
            )
        return True
    except sqlite3.IntegrityError:
        return False


def is_duplicate(update_id: str) -> bool:
    """Return True if an update_id has already been committed."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute(
            "SELECT 1 FROM checkpoint_ledger WHERE update_id = ? LIMIT 1",
            (update_id,),
        )
        return cursor.fetchone() is not None


if __name__ == "__main__":
    init_db()
    print("Success: SQLite append-only ledger initialized at /ledger/ledger.db")
