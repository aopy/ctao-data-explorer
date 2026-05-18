==============================
Legacy setups (reference only)
==============================

These setups are **not recommended** for new deployments. They are kept for
reference only.

Setup outside Kubernetes
=========================

Directly running services on the host requires PostgreSQL, Redis, and Node.js.

**Install prerequisites (Ubuntu/Debian)**

.. code-block:: bash

    sudo apt update
    sudo apt install -y postgresql postgresql-contrib redis-server
    sudo systemctl enable postgresql
    sudo systemctl start postgresql
    sudo systemctl enable redis-server
    sudo systemctl start redis-server

    curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash -
    sudo apt install -y nodejs

**Install prerequisites (macOS)**

.. code-block:: bash

    brew install postgresql redis node
    brew services start postgresql
    brew services start redis

**Backend**

.. code-block:: bash

    # Set up PostgreSQL
    psql -U postgres
    CREATE DATABASE fastapi_db;
    CREATE USER user WITH PASSWORD 'password';
    GRANT ALL PRIVILEGES ON DATABASE fastapi_db TO user;
    \q

    # Sync dependencies
    cp .env.example .env
    uv sync --locked
    alembic upgrade head

    # Run
    export REDIS_URL="redis://localhost:6379/0"
    set -o allexport
    source .env
    set +o allexport
    uv run uvicorn api.main:app --reload --port 8000
    uv run uvicorn auth_service.main:app --reload --port 8001

**Frontend**

.. code-block:: bash

    cd js
    npm install
    npm run build


Systemd + Nginx (manual deployment)
=====================================

.. code-block:: ini

    [Unit]
    Description=CTAO FastAPI backend (Gunicorn/Uvicorn)
    After=network.target postgresql@15-main.service redis-server.service
    Requires=postgresql@15-main.service redis-server.service

    [Service]
    User=ctao
    WorkingDirectory=/opt/ctao/ctao-data-explorer
    EnvironmentFile=/opt/ctao/ctao-data-explorer/.env
    ExecStart=/usr/bin/env uv run gunicorn -w 3 -k uvicorn.workers.UvicornWorker --bind 127.0.0.1:8000 api.main:app
    Restart=on-failure

    [Install]
    WantedBy=multi-user.target

**Nginx snippet**

.. code-block:: nginx

    server {
      listen 443 ssl http2;
      server_name padc-ctao-data-explorer.obspm.fr;
      location /api/ { proxy_pass http://127.0.0.1:8000/; }
      location /docs { proxy_pass http://127.0.0.1:8000/docs; }
      location /redoc { proxy_pass http://127.0.0.1:8000/redoc; }
      root /opt/ctao/ctao-data-explorer/js/dist;
      try_files $uri /index.html;
    }
