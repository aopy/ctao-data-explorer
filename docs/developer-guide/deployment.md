# Deployment

## Server layout (example)

- **Reverse proxy**: Nginx (TLS, gzip, caching of static assets)
- **App**: Gunicorn+Uvicorn workers (`api.main:app`), systemd unit
- **DB**: PostgreSQL 14/15 with daily backups
- **Cache/queue**: Redis
- **Static frontend**: built in `js/` and served by Nginx

### systemd unit (example)

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

### Nginx (snippet)

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
