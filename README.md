## Redis Chat

A minimal chat service backed by Redis. This project demonstrates using Redis for pub/sub, messaging persistence (optional), and lightweight web APIs/UI.

### Features
- **Redis-backed messaging**: publish/subscribe channels for realtime chat
- **Container-ready**: `docker-compose` for app + Redis
- **Tests**: pytest configured via `pytest.ini`

### Requirements
- Python 3.11+
- Redis 6+
- Optional: Docker and Docker Compose v2

### Quick start (local)
1) Create and activate a virtual environment

```bash
python -m venv venv
"venv/Scripts/activate"  # Windows (cmd/PowerShell)
# source venv/bin/activate  # macOS/Linux
```

2) Install dependencies

```bash
pip install -r requirements.txt
```

3) Start Redis

- Local install: ensure `redis-server` is running on `localhost:6379`
- Or use Docker:

```bash
docker run -p 6379:6379 --name redis -d redis:7-alpine
```

4) Run the app

```bash
python -m app
```

See `Redis.md` for notes and common Redis commands.

### Running with Docker Compose

This repository includes a `docker-compose.yml` to run both the app and Redis.

```bash
docker compose up --build
```

Then open the app at the URL printed in logs (commonly `http://localhost:8000` unless the app uses a different port).

To stop and clean up:

```bash
docker compose down -v
```

### Configuration

Environment variables (override as needed):

- `REDIS_URL` (default: `redis://localhost:6379/0`)
- `APP_HOST` (default: `0.0.0.0`)
- `APP_PORT` (default: `8000`)
- `APP_ENV` (default: `development`)

You can set them locally (Windows cmd):

```bat
set REDIS_URL=redis://localhost:6379/0
set APP_PORT=8000
```

PowerShell:

```powershell
$env:REDIS_URL = "redis://localhost:6379/0"
$env:APP_PORT = "8000"
```

Unix shells:

```bash
export REDIS_URL=redis://localhost:6379/0
export APP_PORT=8000
```

### Development

- Code lives under `app/`
- Adjust Dockerfile/compose as needed
- Keep `requirements.txt` in sync when adding libs

### Tests

```bash
pytest -q
```

### Project structure

```text
redis-chat/
  app/                  # application source
  tests/                # pytest tests
  Dockerfile            # container image for the app
  docker-compose.yml    # app + Redis services
  requirements.txt      # Python dependencies
  Redis.md              # Redis tips and useful commands
  pytest.ini            # pytest configuration
  README.md             # this file
```

### Troubleshooting
- **Cannot connect to Redis**: verify `REDIS_URL`, port mapping, or that `redis-server` is running.
- **Port already in use**: change `APP_PORT` or stop the conflicting process.
- **Dependency issues**: recreate the venv and reinstall requirements.

### License

MIT (or your choice). Update this section if you adopt a different license.


