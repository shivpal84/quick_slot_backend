import os
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    database_path = tmp_path / "test.db"
    monkeypatch.setenv("SLOT_BOOKING_DB", str(database_path))

    from main import app

    with TestClient(app) as test_client:
        yield test_client


def future_date() -> str:
    return (date.today() + timedelta(days=1)).isoformat()


def test_lists_seeded_venues_and_slots(client):
    venues_response = client.get("/venues")
    assert venues_response.status_code == 200
    assert len(venues_response.json()) == 4
    assert all(venue["slot_count"] == 16 for venue in venues_response.json())

    slots_response = client.get(
        "/venues/1/slots",
        params={"date": future_date()},
    )
    assert slots_response.status_code == 200
    slots = slots_response.json()["slots"]
    assert len(slots) == 16
    assert slots[0]["start_time"] == "06:00"
    assert slots[-1]["end_time"] == "22:00"
    assert all(slot["status"] == "available" for slot in slots)


def test_booking_lifecycle(client):
    payload = {"venue_id": 1, "date": future_date(), "start_time": "09:00"}

    created = client.post("/bookings", headers={"X-User-Id": "1"}, json=payload)
    assert created.status_code == 201
    booking_id = created.json()["id"]

    duplicate = client.post("/bookings", headers={"X-User-Id": "2"}, json=payload)
    assert duplicate.status_code == 409

    slots = client.get(
        "/venues/1/slots",
        params={"date": future_date()},
    ).json()["slots"]
    assert next(slot for slot in slots if slot["start_time"] == "09:00")["status"] == "booked"

    bookings = client.get("/users/1/bookings", headers={"X-User-Id": "1"})
    assert bookings.status_code == 200
    assert [booking["id"] for booking in bookings.json()] == [booking_id]

    cancelled = client.delete(
        f"/bookings/{booking_id}",
        headers={"X-User-Id": "1"},
    )
    assert cancelled.status_code == 204


def test_rejects_invalid_requests(client):
    invalid_time = client.post(
        "/bookings",
        headers={"X-User-Id": "1"},
        json={"venue_id": 1, "date": future_date(), "start_time": "09:30"},
    )
    assert invalid_time.status_code == 422

    unknown_user = client.post(
        "/bookings",
        headers={"X-User-Id": "999"},
        json={"venue_id": 1, "date": future_date(), "start_time": "10:00"},
    )
    assert unknown_user.status_code == 401

    forbidden = client.get("/users/2/bookings", headers={"X-User-Id": "1"})
    assert forbidden.status_code == 403


def test_concurrent_booking_allows_exactly_one_winner(client):
    payload = {"venue_id": 1, "date": future_date(), "start_time": "12:00"}

    def book(user_id):
        return client.post(
            "/bookings",
            headers={"X-User-Id": str(user_id)},
            json=payload,
        ).status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        statuses = list(executor.map(book, (1, 2)))

    assert sorted(statuses) == [201, 409]
