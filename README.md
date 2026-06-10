# Slot Booking API

A FastAPI service backed by SQLite. It seeds four venues, three hardcoded users,
and 16 hourly slots per venue (06:00-22:00).

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python seed.py
uvicorn main:app --reload
```

Interactive API documentation is available at `http://127.0.0.1:8000/docs`.

## Users

Use one of these IDs in the `X-User-Id` header:

| ID | Name |
|---:|---|
| 1 | Alice |
| 2 | Bob |
| 3 | Charlie |

## Example requests

```bash
curl http://127.0.0.1:8000/venues

curl "http://127.0.0.1:8000/venues/1/slots?date=2026-06-15"

curl -X POST http://127.0.0.1:8000/bookings \
  -H "Content-Type: application/json" \
  -H "X-User-Id: 1" \
  -d '{"venue_id":1,"date":"2026-06-15","start_time":"09:00"}'

curl -H "X-User-Id: 1" \
  http://127.0.0.1:8000/users/1/bookings

curl -X DELETE -H "X-User-Id: 1" \
  http://127.0.0.1:8000/bookings/1
```

Successful creation returns `201`. A competing booking for the same venue,
date, and slot returns `409`. Invalid input returns `422`.

## Tests

```bash
pytest
```
