from datetime import time
from typing import Optional

from database import get_connection, initialize_database


USERS = (
    (1, "Alice"),
    (2, "Bob"),
    (3, "Charlie"),
)

VENUES = (
    ("Central Sports Arena", "12 Park Street"),
    ("Riverside Badminton Club", "85 River Road"),
    ("Downtown Tennis Center", "210 Market Avenue"),
    ("Northside Community Hall", "44 North Lane"),
)


def hour_text(hour: int) -> str:
    return time(hour=hour).strftime("%H:%M")


def seed_database(db_path: Optional[str] = None) -> None:
    initialize_database(db_path)

    with get_connection(db_path) as connection:
        connection.execute("BEGIN")
        try:
            connection.executemany(
                "INSERT OR IGNORE INTO users(id, name) VALUES (?, ?)",
                USERS,
            )
            connection.executemany(
                "INSERT OR IGNORE INTO venues(name, address) VALUES (?, ?)",
                VENUES,
            )

            venues = connection.execute("SELECT id FROM venues").fetchall()
            slots = [
                (venue["id"], hour_text(hour), hour_text(hour + 1))
                for venue in venues
                for hour in range(6, 22)
            ]
            connection.executemany(
                """
                INSERT OR IGNORE INTO slots(venue_id, start_time, end_time)
                VALUES (?, ?, ?)
                """,
                slots,
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise


if __name__ == "__main__":
    seed_database()
    print("Database seeded with users, venues, and hourly slots.")
