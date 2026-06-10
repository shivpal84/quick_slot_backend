import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional


DEFAULT_DB_PATH = Path(__file__).with_name("booking.db")


def get_db_path() -> str:
    return os.getenv("SLOT_BOOKING_DB", str(DEFAULT_DB_PATH))


def connect(db_path: Optional[str] = None) -> sqlite3.Connection:
    connection = sqlite3.connect(
        db_path or get_db_path(),
        timeout=10,
        isolation_level=None,
        check_same_thread=False,
    )
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 10000")
    return connection


@contextmanager
def get_connection(db_path: Optional[str] = None) -> Iterator[sqlite3.Connection]:
    connection = connect(db_path)
    try:
        yield connection
    finally:
        connection.close()


def initialize_database(db_path: Optional[str] = None) -> None:
    with get_connection(db_path) as connection:
        connection.execute("PRAGMA journal_mode = WAL")
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS venues (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                address TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS slots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                venue_id INTEGER NOT NULL REFERENCES venues(id) ON DELETE CASCADE,
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                UNIQUE (venue_id, start_time)
            );

            CREATE TABLE IF NOT EXISTS bookings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id),
                venue_id INTEGER NOT NULL REFERENCES venues(id),
                slot_id INTEGER NOT NULL REFERENCES slots(id),
                booking_date TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (venue_id, slot_id, booking_date)
            );

            CREATE INDEX IF NOT EXISTS idx_bookings_user
                ON bookings(user_id, booking_date);
            CREATE INDEX IF NOT EXISTS idx_bookings_venue_date
                ON bookings(venue_id, booking_date);
            """
        )
