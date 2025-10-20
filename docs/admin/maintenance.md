# Operations & Maintenance

- **DB migrations**: `alembic upgrade head`; maintain CHANGELOG entries for schema changes
- **Backups**: regular PostgreSQL dumps; test restores
- **Logs**: use structured logging; rotate via journald or logrotate
- **Upgrades**: keep FastAPI, dependencies, and Node toolchain current (security fixes)
- **Housekeeping**: clear old preview job artifacts per retention policy
