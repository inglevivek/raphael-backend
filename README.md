# Raphael Backend

One-line summary  
A robust, production-ready Python backend for the Raphael application — providing the REST/HTTP API, data persistence, background workers, and utilities used by the Raphael frontend and services.

## Table of contents
- [What is this](#what-is-this)
- [Tech stack](#tech-stack)
- [Features](#features)
- [Architecture overview](#architecture-overview)
- [How it fits together](#how-it-fits-together)
- [Prerequisites](#prerequisites)
- [Quickstart (development)](#quickstart-development)
- [Running in Docker](#running-in-docker)
- [Configuration / environment variables](#configuration--environment-variables)
- [Database migrations](#database-migrations)
- [Testing](#testing)
- [Linting & formatting](#linting--formatting)
- [Continuous integration](#continuous-integration)
- [Deployment](#deployment)
- [API documentation](#api-documentation)
- [Common tasks & commands](#common-tasks--commands)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [Security](#security)
- [License & contact](#license--contact)
- [Appendix: example .env.example](#appendix-example-envexample)

## What is this
A backend service that exposes the Raphael application's HTTP API, handles authentication and authorization, persists domain data to a database, and performs asynchronous tasks (background jobs). It is designed for local development and production deployment behind a load balancer.

## Tech stack
- Language: Python (>=3.10 recommended)
- Framework / runtime: (replace with actual framework) e.g. FastAPI + Uvicorn, Django, or Flask + Gunicorn
- Database: (replace) e.g. PostgreSQL
- Migrations: Alembic (SQLAlchemy) or Django migrations
- Task queue (optional): Celery / Redis or RQ
- Notable libraries: SQLAlchemy or Django ORM, Pydantic (or DRF serializers), Alembic, pytest

## Features
- Authentication endpoints (login, refresh tokens, logout)
- CRUD APIs for core domain models
- Pagination, filtering, and sorting on list endpoints
- Request/response schema validation
- Database migrations and seed data utilities
- Background job processing (optional)
- Auto-generated API docs (FastAPI) or browsable API (DRF)

## Architecture overview
Typical layout (adjust to repo layout: `app/` or `src/`):

```
app/ or src/        # main application package
  api/              # HTTP handlers / routers / views
  models/           # ORM models and schema definitions
  services/         # Business logic, transactional boundaries
  db/               # DB session, connection helpers, migrations hooks
  core/             # config, logging, startup/shutdown hooks
  tasks/            # background job tasks (Celery, RQ)
  tests/            # pytest suite
  scripts/          # dev utilities (seed, fixtures, maintenance)
```

How it fits together: On startup the app reads configuration from environment variables, initializes DB and queue clients, and mounts HTTP routers. Incoming requests are handled by `api` routers that call into `services` for business logic; `services` use `models` and `db` helpers for persistence. Background workers import `services` to reuse core logic.

## Prerequisites
- Python 3.10+
- PostgreSQL (or your chosen DB)
- Redis (if using Celery/RQ)
- Git
- Docker (optional, for containerized development)

## Quickstart (development)
1. Clone
```bash
git clone https://github.com/inglevivek/raphael-backend.git
cd raphael-backend
```

2. Create virtual environment and install
```bash
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
# or, if using poetry:
# poetry install
```

3. Copy env example and configure
```bash
cp .env.example .env
# Edit .env to set DB and other secrets
```

4. Run migrations
- Alembic (SQLAlchemy):
```bash
alembic upgrade head
```
- Django:
```bash
python manage.py migrate
```

5. Run the app (choose the command for your framework)
- FastAPI + Uvicorn:
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
- Django:
```bash
python manage.py runserver 0.0.0.0:8000
```
- Flask:
```bash
export FLASK_APP=app
flask run --host=0.0.0.0 --port=8000
```

6. Run tests
```bash
pytest -q
```

## Running in Docker
Example docker-compose for development (adjust to your Dockerfile and service names):

```yaml
version: "3.8"
services:
  web:
    build: .
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000
    volumes:
      - ./:/app
    env_file:
      - .env
    ports:
      - "8000:8000"
    depends_on:
      - db
  db:
    image: postgres:15
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: raphael
    volumes:
      - pgdata:/var/lib/postgresql/data
volumes:
  pgdata:
```

Add a production-grade Dockerfile and multi-stage builds for a smaller image.

## Configuration / environment variables
Create `.env.example` with appropriate variables. Common variables:

- APP_ENV=development
- SECRET_KEY=replace-with-secure-secret
- DATABASE_URL=postgresql://postgres:password@db:5432/raphael
- REDIS_URL=redis://redis:6379/0
- SENTRY_DSN=
- DEBUG=true

Ensure secrets are never committed to the repo; add `.env` to `.gitignore`.

## Database migrations
- SQLAlchemy + Alembic:
  - Initialize: `alembic init alembic`
  - Create revision: `alembic revision --autogenerate -m "initial"`
  - Apply: `alembic upgrade head`
- Django:
  - `python manage.py makemigrations`
  - `python manage.py migrate`

## Testing
- Tests reside in `tests/`
- Run:
```bash
pytest -q
```
- Coverage (example):
```bash
pytest --cov=app --cov-report=term-missing
```

## Linting & formatting
- Format: `black .`
- Lint: `ruff .`
- Type check (optional): `mypy`
- Pre-commit hooks: `pre-commit install`

## Continuous integration
Add a CI workflow (e.g., GitHub Actions `.github/workflows/ci.yml`) that runs:
- Install dependencies
- Run linters (ruff, black check)
- Run tests
- Run type-checks (optional)

Example CI steps:
- Set up Python
- pip install -r requirements.txt
- pytest
- ruff check
- black --check

## Deployment
- Build and push a Docker image to your registry
- Deploy to your cloud provider (AWS ECS / EKS, Google Cloud Run, DigitalOcean, or Kubernetes)
- Ensure runtime env vars (DATABASE_URL, SECRET_KEY, etc.) are injected securely
- Use HTTPS and a load balancer in front of service
- Monitor logs and health checks, configure readiness/liveness probes if on Kubernetes

## API documentation
- FastAPI: OpenAPI/Swagger UI at `/docs`, ReDoc at `/redoc`
- Django REST Framework: browsable API; consider `drf-spectacular` or `drf-yasg` for OpenAPI generation

## Common tasks & commands
- Install deps: `pip install -r requirements.txt`
- Run dev server: `uvicorn app.main:app --reload`
- Run tests: `pytest`
- Run migrations: `alembic upgrade head` or `python manage.py migrate`
- Start worker: `celery -A app.worker worker --loglevel=info`

## Troubleshooting
- Database connection error:
  - Verify `DATABASE_URL` and DB accessibility.
- Migrations failing:
  - Ensure migration files exist and DB user has privileges.
- Tests failing:
  - Run locally with `-k` to narrow tests; use `-s` to view print/debug info.

## Contributing
- Fork the repo and create a feature branch:
```bash
git checkout -b feat/short-description
```
- Run tests and linters locally before pushing
- Open a PR with a clear description and testing steps
- Use small, focused commits and descriptive messages

## Security
- Do not commit secrets. Keep `.env` in `.gitignore`.
- Rotate secrets if accidentally leaked.
- Review dependencies for vulnerabilities regularly.

## License & contact
- License: MIT
- Maintainer: Vivek Ingle vivekingle513@gmail.com

## Appendix: example .env.example
```env
APP_ENV=development
SECRET_KEY=changeme
DATABASE_URL=postgresql://postgres:postgres@db:5432/raphael
REDIS_URL=redis://redis:6379/0
SENTRY_DSN=
DEBUG=true
```

## Notes & TODOs for repository owners
- Replace placeholders with concrete framework-specific commands and configuration.
- Add a Dockerfile and production-ready compose/manifest if you want containerized deployments.
- Add `.github/workflows/ci.yml` to run CI checks automatically.
- Consider adding `ARCHITECTURE.md` with a high-level diagram for maintainers.
