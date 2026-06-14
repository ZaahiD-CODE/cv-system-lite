# AGENTS.md — CV System

## Project overview

Real-time object detection, tracking, and counting system. Python backend (FastAPI + YOLO12 + OpenCV), Jinja2 frontend, SQLite database.

**Repo**: `/root/cv_system/`
**Domain**: `vision.vlesssec.ru`
**Default admin**: `admin` / password in `.env` (`CV_ADMIN_PASSWORD`)

## Commands

```bash
# Install (first time)
./install.sh

# Run dev server
source venv/bin/activate
python3 run_web.py          # http://localhost:8000

# Run tests
python3 test_all.py         # unit tests (detector, tracker, counter, source, analytics)
python3 test_integration.py # integration (config, streams, pipeline)
python3 test_web.py         # API endpoint tests (uses FastAPI TestClient)

# Systemd service (production)
systemctl restart cv-system
systemctl status cv-system
journalctl -u cv-system -f  # live logs
```

## Architecture

```
src/                        # CV pipeline (standalone, no web dependency)
  core/detector.py          # YOLO12 wrapper, auto GPU detection
  core/tracker.py           # Centroid-based multi-object tracker
  core/counter.py           # Zone (polygon) and line crossing counting
  sources/                  # VideoSource, RTSPSource, CameraSource
  training_engine.py        # YOLO fine-tuning engine (background threads)

web/                        # FastAPI web application
  app.py                    # Main app, routes, MJPEG streaming, WebSocket
  auth.py                   # JWT auth (python-jose + passlib/bcrypt)
  database.py               # SQLAlchemy models + init_db() with migrations
  routers/                  # API endpoints (auth, streams, users, training, stats, system)
  templates/                # Jinja2 HTML templates (all i18n via JS t() function)
  static/                   # CSS + JS (shared app.js with i18n, theme, auth)
```

## Key patterns

### Database migrations
No migration framework. `init_db()` in `web/database.py` runs at startup:
- `Base.metadata.create_all()` for new tables
- `PRAGMA table_info()` to check columns before `ALTER TABLE ADD COLUMN`
- Safe to run repeatedly — idempotent checks

### MJPEG streaming
`/api/stream/{id}/mjpeg` returns `multipart/x-mixed-replace` content type. Frontend uses plain `<img>` tag (no JS decoding). `new Image()` only loads one frame — never use for MJPEG.

### Custom model naming
Trained models: `{base_stem}_{object_name}.pt` (e.g. `yolo12n_каска.pt`). Object name sanitized: lowercase, spaces/hyphens → underscores.

### Model selectors
All model dropdowns fetch from `GET /api/training/models` (not `/api/stats/system`). Returns standard + custom models. `populateModelSelect(selectId, selectedValue)` in `app.js`.

### i18n
Translation dict + `t(key)` function in `app.js`. Language in `localStorage`. Each template calls `t()` for all visible strings. Language change triggers `location.reload()`.

### Theme
`applyTheme(theme)` in `app.js` overrides CSS custom properties (`--bg-primary`, `--bg-card`, `--border`, `--text-primary`, `--text-secondary`). Theme in `localStorage`. Called on every page load.

## Gotchas

- `bcrypt>=5.0` breaks `passlib` — pin to `bcrypt==4.1.3`
- Starlette `TemplateResponse` newer API: `TemplateResponse(request, name)` not `TemplateResponse({"request": request})`
- FastAPI routers use `@router.get()` not `@app.get()` — `app` not in scope in router files
- `fetch()` without `API` helper needs explicit `Authorization` header
- Canvas responsive: `width:100%;height:auto;display:block` + `line-height:0` on container
- `event.target` is undefined when calling event handlers programmatically — use explicit element selection
- MJPEG streams block `cv2.VideoCapture.read()` — service gets stuck in `deactivating` state. Workaround: `kill -9 PID` before `systemctl start`
- `.git` bloats if `.pt` model files are committed — always keep in `.gitignore`
- Network speed API must return raw bytes (not rounded MB) for frontend speed calculation

## Deployment

- **Nginx**: `/etc/nginx/sites-available/cv-system` — reverse proxy to localhost:8000 with WebSocket support
- **SSL**: Let's Encrypt via certbot (auto-renew)
- **Systemd**: `cv-system.service` — `Type=simple`, `Restart=always`, `RestartSec=5`
- **Models**: Downloaded to `/root/cv_system/models/` during install (not in git)
- **Database**: `cv_system.db` in project root (not in git)
