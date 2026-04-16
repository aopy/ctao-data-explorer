# Deployment

## Kubernetes deployment (recommended)
The primary and supported deployment method is on Kubernetes. This is the only deployment method that is actively maintained and validated in CI.

The application is deployed using a Helm chart (see [chart/](https://gitlab.cta-observatory.org/cta-computing/suss/scienceportal/prototypes/ctao-data-explorer/-/blob/master/chart/README.md)).

### Requirements
* A Kubernetes cluster (tested with standard CNCF‑compatible clusters)
* Helm v3
* HAProxy ingress controller

### GitOps-based staging, pre-production and production deployment
Production deployments follow GitOps principles and are managed using FluxCD.
The application is first deployed to staging in the CTAO-SDMC Kubernetes AIV test cluster, where charts and images are validated. Once validated, the same immutable artifacts (Helm charts and container images) are promoted seamlessly to pre‑production and production environments.

### Release and deployment flow

#### Package release
After a package release, container images and the Helm chart are built and published to their respective registries.
Images and charts are treated as immutable artifacts.

#### Environment adaptation
A dedicated Flux Git repository defines the desired state for each environment (staging, pre‑production, production).
In this repository, the released chart version is referenced and configured for the target environment (values, secrets, ingress, resources, etc.).

#### Deployment trigger
Deployment is triggered only by committing changes to the Flux repository.
FluxCD detects the change and reconciles the cluster to match the declared state.
No manual `helm install` or `kubectl apply` is used in production.

This approach ensures:
- Reproducible deployments across environments
- Full traceability of what is running
- Safe and auditable promotion from staging to production
- Clear separation between application release and environment configuration


## Alternative manual deployment (deprecated)

> [!WARNING]
> 
> Manual deployment described below using systemd + Nginx is deprecated.
> It is not tested in CI, or recommended for new deployments.
> The section below is kept for reference only, mainly to document historical setups or for troubleshooting legacy installations.
> New deployments should use Kubernetes + Helm.

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
- The Nginx above is the **bare-metal reverse proxy**, unrelated to the Kubernetes ingress controller.

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

