# INVINTELL Retail Intelligence — Backend (FastAPI + PostgreSQL)

## 1. Python version

Python **3.11+** is required.

## 2. Virtual environment setup

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

## 3. Install dependencies

```powershell
pip install -r requirements.txt
```

## 4. PostgreSQL configuration

Create a database (default name `invintell`):

```sql
CREATE DATABASE invintell;
```

## 5. Environment variables

```powershell
Copy-Item .env.example .env
```

Edit `.env`:

```
DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/invintell
SECRET_KEY=<long random secret>
ACCESS_TOKEN_EXPIRE_MINUTES=30
FRONTEND_URL=http://localhost:5173
```

## 6. Database migration

```powershell
alembic upgrade head
```

## 7. Seed database

```powershell
python -m app.utils.seed
```

Demo login: `admin@invintell.com` / `admin123`. The script is idempotent — safe to rerun.

## 8. Start FastAPI

```powershell
uvicorn app.main:app --reload --port 8000
```

## 9. API documentation

Interactive docs: https://inventell-backend-rth.onrender.com/docs

Health check: `GET /api/health` → `{"status": "ok"}`

## 10. Frontend connection

In `frontend/.env` (see `frontend/.env.example`):

```
VITE_API_URL= https://inventell-backend-rth.onrender.com/
```

Then run the frontend:

```powershell
cd ../frontend
npm install
npm run dev
```

## Scope notes

Single store (`Main Street Store`) + single warehouse (`Main Warehouse`).
CCTV/YOLO, live streaming, external AI APIs and payment gateways are **not**
implemented yet — CCTV-derived dashboard values are served from analyzed-event
records so the computer-vision pipeline can replace them later.

## Store Monitor (testing-video CCTV pipeline)

Testing videos live in `media/test_videos/` (`camera_01.mp4`, `camera_02.mp4` —
git-ignored, served by FastAPI, never bundled into the frontend):

```
TEST VIDEO → OpenCV → person detection → tracking → foot point
→ homography → 2D coordinates → React (CCTV + 2D map)
```

* Person detection: YOLOv8 (`PERSON` class) when `ultralytics` is installed,
  otherwise motion-based OpenCV fallback (no downloads required).
* Tracking: stable temporary IDs (ByteTrack-compatible interface in
  `app/cv/tracker.py`).
* `POST /api/store-monitor/start` processes a video in the background and
  caches per-timestamp tracks as JSON; the frontend polls
  `tracks/map/metrics/events/zones?timestamp=` in sync with video playback.
* Dots on the 2D map come only from real tracks — with no processing results
  the UI shows "Detection engine not connected" instead of simulated data.
* Docs: `app/cv/` module + https://inventell-backend-rth.onrender.com/docs (`store-monitor` tag).
