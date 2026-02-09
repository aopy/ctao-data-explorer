# Deployment

## Kubernetes

Primary deployment target is on kubernetes (see [chart/](https://gitlab.cta-observatory.org/cta-computing/suss/scienceportal/prototypes/ctao-data-explorer/-/blob/master/chart/README.md) for Helm chart).



## Alternative deployment

### Server layout (example)

- **Reverse proxy**: Nginx (TLS, gzip, caching of static assets)
- **App**: Gunicorn+Uvicorn workers (`api.main:app`), systemd unit
- **DB**: PostgreSQL 14/15 with daily backups
- **Cache/queue**: Redis
- **Static frontend**: built in `js/` and served by Nginx

#### systemd unit (example)

```ini
[Unit]
Description=CTAO FastAPI backend (Gunicorn/Uvicorn)
After=network.target postgresql@15-main.service redis-server.service
Requires=postgresql@15-main.service redis-server.service

[Service]
User=ctao
WorkingDirectory=/opt/ctao/ctao-data-explorer
EnvironmentFile=/opt/ctao/ctao-data-explorer/.env
ExecStart=/opt/miniconda/envs/ctao-backend/bin/gunicorn -w 3 -k uvicorn.workers.UvicornWorker --bind 127.0.0.1:8000 api.main:app
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

#### Nginx (snippet)

```nginx
server {
  listen 443 ssl http2;
  server_name padc-ctao-data-explorer.obspm.fr;

  # TLS ...

  location /api/ { proxy_pass http://127.0.0.1:8000/; proxy_set_header Host $host; }
  location /docs { proxy_pass http://127.0.0.1:8000/docs; }
  location /redoc { proxy_pass http://127.0.0.1:8000/redoc; }

  # React static build
  root /opt/ctao/ctao-data-explorer/js/dist;
  try_files $uri /index.html;
}
```

**Notes**
- Place secrets in **EnvironmentFile** or systemd overrides; not in the unit file.
- Ensure `COOKIE_SECURE=true` behind TLS and set `COOKIE_DOMAIN` to the public hostname.


## Local development stack with docker compose

Just for reference of the first containerization approaches. Note that the Dockerfiles used by the kubernetes + Helm chart approach are in the root folder of this repository.

Only for local development, you will find:

- `docker-compose.yml` (in `docker/dev/`)
- `Dockerfile.backend` (in `docker/dev/`)
- `Dockerfile.frontend` (in `docker/dev/`)
- `requirements.txt`  (in root repository folder)
- `.env.docker` (in `docker/dev/`)

How to run:

### 1) Environment configuration
Make sure env file exists in the same directory as the `docker-compose.yml` and fill values

Notes: Set `PRODUCTION=false` in `.env.docker`

### 2) Start DB/Redis
```
docker compose -f docker/dev/docker-compose.yml up -d postgres redis
```

### 3) Run migrations
```
docker compose -f docker/dev/docker-compose.yml run --rm backend bash -lc 'alembic upgrade head'
```
### 4) Build frontend once (creates `./js/build`)
```
docker compose -f docker/dev/docker-compose.yml run --rm frontend npm ci
docker compose -f docker/dev/docker-compose.yml run --rm frontend npm run build
```
### 5) Start backend and frontend
```
docker compose -f docker/dev/docker-compose.yml up -d backend frontend
```
### 6) Open
Open http://localhost:3000

