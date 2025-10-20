# Configuration (.env)

> **Never commit secrets.** Keep real values in deployment‑specific env vars or secret stores.

Copy this template as a starting point:

```dotenv
# OAuth / IAM
CTAO_CLIENT_ID=__set_in_env__
CTAO_CLIENT_SECRET=__set_in_env__

# Backend auth
JWT_SECRET=__set_in_env__
REFRESH_TOKEN_ENCRYPTION_KEY=__set_in_env__

# Database
DATABASE_URL=postgresql+asyncpg://user:pass@127.0.0.1:5432/fastapi_db
DB_URL=postgresql://user:pass@127.0.0.1:5432/fastapi_db

# Redis
REDIS_URL=redis://localhost:6379/0

# Web
BASE_URL=https://padc-ctao-data-explorer.obspm.fr
COOKIE_SAMESITE=None
COOKIE_SECURE=true
COOKIE_DOMAIN=padc-ctao-data-explorer.obspm.fr
LOG_LEVEL=INFO

# OPUS (UWS)
OPUS_ROOT=https://voparis-uws-test.obspm.fr
OPUS_SERVICE=gammapy_source_analysis
OPUS_APP_TOKEN=__set_in_env__
OPUS_APP_USER=ctao

# React build
NODE_OPTIONS=--openssl-legacy-provider

# Misc
SECRET_KEY=__rotate__
```

**Guidelines**
- Provide an **`.env.example`** with placeholders (no secrets). Load from environment in production.
- Prefer **GitLab CI/CD variables**, Kubernetes **Secrets**, or **HashiCorp Vault** for deployments.
- Rotate any credential that was ever shared outside secure channels.
