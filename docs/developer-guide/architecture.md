# Architecture

**Frontend**: React (CRA), Axios, maps/charts widgets, Bootstrap.  
**Backend**: FastAPI (Gunicorn/Uvicorn), PostgreSQL (SQLAlchemy/Alembic), Redis cache/queue.  
**Interop**: IVOA protocols — **ObsCore**, **TAP/ADQL**, **DataLink 1.1**. Quick‑look analysis via **OPUS (UWS)**.

```text
+-------------------+        HTTPS         +---------------------+
|   React frontend  |  <---------------->  |     FastAPI app     |
|   (static build)  |                      |  /api, /docs (OAS)   |
+---------+---------+                      +----+----------+-----+
          |                                       |          |
          | Axios                                  |          |
          v                                       v          v
   CTAO IAM (OIDC)                          PostgreSQL     Redis
         (tokens)                           (metadata)    (cache)
```

- **ObsCore/TAP** queries: dispatched via PyVO/ADQL to upstream services
- **DataLink 1.1**: exposes associated resources and direct downloads when available
- **OPUS**: preview jobs submitted to `gammapy_source_analysis` (UWS pattern)

See also: standards & interop.
