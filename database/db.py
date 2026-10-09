"""Database connection helpers. Foreign keys are switched on for every connection."""
import sqlite3
from pathlib import Path

import config


def connect(db_path: Path | str | None = None, read_only: bool = False) -> sqlite3.Connection:
    path = Path(db_path or config.DB_PATH)
    if read_only:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, check_same_thread=False)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(config.SCHEMA_PATH.read_text(encoding="utf-8"))
