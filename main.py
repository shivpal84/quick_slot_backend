import sqlite3
from contextlib import asynccontextmanager
from datetime import date, time
from typing import Any, Dict, List

from fastapi import FastAPI, Header, HTTPException, Response, status
from pydantic import BaseModel, Field

from database import get_connection
from seed import seed_database


class BookingRequest(BaseModel):
    venue_id: int = Field(gt=0)
    date: date
    start_time: time


def serialize_time(value: time) -> str:
    return value.strftime("%H:%M")


def require_user(user_id: int) -> Dict[str, Any]:
    with get_connection() as connection:
        user = connection.execute(
            "SELECT id, name FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    if user is None:
        raise HTTPException(status_code=401, detail="Unknown user")
    return dict(user)


def authenticated_user(x_user_id: int = Header(..., alias="X-User-Id")) -> Dict[str, Any]:
    return require_user(x_user_id)


@asynccontextmanager
async def lifespan(_: FastAPI):
    seed_database()
    yield


app = FastAPI(
    title="Slot Booking API",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/venues")
def list_venues() -> List[Dict[str, Any]]:
    with get_connection() as connection:
        venues = connection.execute(
            """
            SELECT v.id, v.name, v.address, COUNT(s.id) AS slot_count
            FROM venues v
            LEFT JOIN slots s ON s.venue_id = v.id
            GROUP BY v.id
            ORDER BY v.id
            """
        ).fetchall()
    return [dict(venue) for venue in venues]


@app.get("/venues/{venue_id}/slots")
def list_slots(venue_id: int, date: date) -> Dict[str, Any]:
    with get_connection() as connection:
        venue = connection.execute(
            "SELECT id, name, address FROM venues WHERE id = ?",
            (venue_id,),
        ).fetchone()
        if venue is None:
            raise HTTPException(status_code=404, detail="Venue not found")

        slots = connection.execute(
            """
            SELECT
                s.id,
                s.start_time,
                s.end_time,
                CASE WHEN b.id IS NULL THEN 'available' ELSE 'booked' END AS status
            FROM slots s
            LEFT JOIN bookings b
                ON b.slot_id = s.id AND b.booking_date = ?
            WHERE s.venue_id = ?
            ORDER BY s.start_time
            """,
            (date.isoformat(), venue_id),
        ).fetchall()

    return {
        "venue": dict(venue),
        "date": date.isoformat(),
        "slots": [dict(slot) for slot in slots],
    }


@app.post("/bookings", status_code=status.HTTP_201_CREATED)
def create_booking(
    request: BookingRequest,
    x_user_id: int = Header(..., alias="X-User-Id"),
) -> Dict[str, Any]:
    user = require_user(x_user_id)
    if request.date < date.today():
        raise HTTPException(status_code=422, detail="Booking date cannot be in the past")

    start_time = serialize_time(request.start_time)
    with get_connection() as connection:
        venue = connection.execute(
            "SELECT id, name FROM venues WHERE id = ?",
            (request.venue_id,),
        ).fetchone()
        if venue is None:
            raise HTTPException(status_code=404, detail="Venue not found")

        slot = connection.execute(
            """
            SELECT id, start_time, end_time
            FROM slots
            WHERE venue_id = ? AND start_time = ?
            """,
            (request.venue_id, start_time),
        ).fetchone()
        if slot is None:
            raise HTTPException(
                status_code=422,
                detail="Invalid start_time; choose an hourly slot from 06:00 through 21:00",
            )

        try:
            connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute(
                """
                INSERT INTO bookings(user_id, venue_id, slot_id, booking_date)
                VALUES (?, ?, ?, ?)
                """,
                (user["id"], request.venue_id, slot["id"], request.date.isoformat()),
            )
            booking_id = cursor.lastrowid
            connection.commit()
        except sqlite3.IntegrityError as error:
            connection.rollback()
            if "UNIQUE constraint failed" in str(error):
                raise HTTPException(status_code=409, detail="Slot already booked")
            raise

    return {
        "id": booking_id,
        "user": user,
        "venue": dict(venue),
        "date": request.date.isoformat(),
        "start_time": slot["start_time"],
        "end_time": slot["end_time"],
        "status": "confirmed",
    }


@app.get("/users/{user_id}/bookings")
def list_user_bookings(
    user_id: int,
    x_user_id: int = Header(..., alias="X-User-Id"),
) -> List[Dict[str, Any]]:
    user = require_user(x_user_id)
    if user["id"] != user_id:
        raise HTTPException(status_code=403, detail="Cannot view another user's bookings")

    with get_connection() as connection:
        bookings = connection.execute(
            """
            SELECT
                b.id,
                b.booking_date AS date,
                b.created_at,
                v.id AS venue_id,
                v.name AS venue_name,
                v.address AS venue_address,
                s.start_time,
                s.end_time
            FROM bookings b
            JOIN venues v ON v.id = b.venue_id
            JOIN slots s ON s.id = b.slot_id
            WHERE b.user_id = ?
            ORDER BY b.booking_date, s.start_time
            """,
            (user_id,),
        ).fetchall()
    return [dict(booking) for booking in bookings]


@app.delete("/bookings/{booking_id}", status_code=status.HTTP_204_NO_CONTENT)
def cancel_booking(
    booking_id: int,
    x_user_id: int = Header(..., alias="X-User-Id"),
) -> Response:
    user = require_user(x_user_id)

    with get_connection() as connection:
        booking = connection.execute(
            "SELECT id, user_id FROM bookings WHERE id = ?",
            (booking_id,),
        ).fetchone()
        if booking is None:
            raise HTTPException(status_code=404, detail="Booking not found")
        if booking["user_id"] != user["id"]:
            raise HTTPException(status_code=403, detail="Cannot cancel another user's booking")

        connection.execute("BEGIN IMMEDIATE")
        connection.execute("DELETE FROM bookings WHERE id = ?", (booking_id,))
        connection.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)
