# CTAO Data Explorer

A web platform to **search, visualize, and analyze** high‑energy (gamma‑ray) astrophysics data, built with a **React** frontend and a **FastAPI** backend.

- Search by **sky position** and/or **observation time** (TT/UTC/MJD/MET)
- Explore results on an interactive **sky map**, **timeline**, and **energy range** charts
- Sign in with **CTAO IAM** for saved queries, baskets, and job tracking
- **Curate selections** into baskets, then launch **Preview jobs** via OPUS (UWS) for quick‑look analysis


> Production: <https://padc-ctao-data-explorer.obspm.fr/>

---

## Quick start

```bash
# Install prerequisites (Ubuntu/Debian)
# PostgreSQL
sudo apt update
sudo apt install -y postgresql postgresql-contrib

# Enable/start
sudo systemctl enable postgresql
sudo systemctl start postgresql

# Create DB/user (example)
sudo -u postgres createuser -P ao         # set a password
sudo -u postgres createdb fastapi_db -O ao

# Redis
sudo apt install -y redis-server
sudo systemctl enable redis-server
sudo systemctl start redis-server

# Node.js (LTS via NodeSource)
curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash -
sudo apt install -y nodejs
node -v && npm -v

# Install prerequisites (macOS)

# Homebrew
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# PostgreSQL
brew install postgresql
brew services start postgresql
createdb fastapi_db
createuser -P ao

# Redis
brew install redis
brew services start redis

# Node.js (LTS)
brew install node
node -v && npm -v

# Backend (conda recommended)
conda create -n ctao-backend python=3.12
conda activate ctao-backend
conda install -c conda-forge fastapi uvicorn aiofiles pyvo numpy requests cryptography hiredis \
 fastapi-users-db-sqlalchemy authlib itsdangerous asyncpg httpx xmltodict alembic psycopg2

# .env — create from the template (keep actual secrets private)
cp .env.example .env

# Database & migrations
alembic upgrade head

# Redis (if local)
export REDIS_URL="redis://localhost:6379/0"

# Run
uvicorn api.main:app --reload

# Frontend
cd js
npm install
npm run build
```

For a tour of the UI, see the **User Guide**.
