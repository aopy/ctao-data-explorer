# CTAO Data Explorer

This project is a web application to access, visualize, and analyze data from the **Cherenkov Telescope Array Observatory (CTAO)**. It combines a **React** frontend with a **FastAPI** backend. Users can search the archive, curate results, explore interactive visualizations, and submit selected items as preview jobs to the [OPUS](https://voparis-uws-test.obspm.fr/client/) service. The application adopts standards from the [International Virtual Observatory Alliance (IVOA)](https://ivoa.net/) to ensure interoperability and broad accessibility of astronomical data.

Documentation is available online at https://aopy.github.io/ctao-data-explorer/

## Table of Contents

- [Features](#features)
- [Requirements](#requirements)
- [Installation](#installation)
  - [Backend Setup](#backend-setup)
  - [Frontend Setup](#frontend-setup)
- [Usage](#usage)
- [About CTAO](#about-ctao)

## Features

- Query CTAO data with flexible, customizable parameters.
- Display results in a selectable data table.
- Explore selections on an interactive sky map and a timeline/electromagnetic-spectrum chart.
- Sign in with CTAO IAM.
- Save and reload past queries and results.
- Group selected items into baskets.
- Submit baskets as preview jobs.

## Requirements

### Backend

- Python >=3.10
- FastAPI
- Uvicorn
- Aiofiles
- Astropy
- PyVO
- Numpy
- Requests
- FastAPI Users
- Authlib
- Alembic
- Postgres
- Redis

### Frontend

- Node.js
- React.js
- Axios

## Installation

### Backend Setup

   ```bash
   # Clone the repository
   git clone https://gitlab.obspm.fr/oates/ctao-data-explorer.git
   cd ctao-data-explorer
   # Create and activate a conda environment
   conda create -n ctao-backend python=3.12.7
   conda activate ctao-backend
   # Install dependencies
   conda install -c conda-forge fastapi uvicorn aiofiles pyvo numpy requests cryptography hiredis \
    fastapi-users-db-sqlalchemy authlib itsdangerous asyncpg httpx xmltodict alembic psycopg2
   # Set up PostgreSQL
   psql -U postgres
   CREATE DATABASE fastapi_db;
   CREATE USER user WITH PASSWORD 'password'; # Adjust user name and password
   GRANT ALL PRIVILEGES ON DATABASE fastapi_db TO user;
   # Apply Alembic migrations
   alembic upgrade head
   # Set up Redis
   export REDIS_URL="redis://localhost:6379/0"
   set -o allexport 
   source .env
   set +o allexport
   # Run the backend
   uvicorn api.main:app --reload
   ```
### Frontend Setup

   ```bash
   cd ctao-data-explorer/js
   npm install
   npm run build
   ```
## Usage

1. **Open the site**  
   <https://padc-ctao-data-explorer.obspm.fr/> → you land on **Search**.

2. **Build a query (Search page)**
   - **Sky position:** choose a system (Equatorial deg, Equatorial hms/dms, or Galactic l/b). Enter RA/Dec (or l/b) and **Radius** (default **5°**). Optionally type an object name, click **Simbad/NED**, then pick from the dropdown to autofill coordinates.
   - **Time system:** toggle **TT** (default) or **UTC**.
     - **Inputs per row (Start / End):**
       - **Date** (`YYYY-MM-DD`)
       - **Time** (`HH:MM:SS`)
       - **MJD** — *Modified Julian Date*
       - **MET (s)** — *Mission Elapsed Time, seconds since the fixed CTAO reference epoch*
       - You may fill **any** of these; the others auto-fill and stay in sync.
     - **MET epoch (fixed):** `2001-01-01 00:00:00 TT`
   - Click **Search** to run or **Clear Form** to reset.  
   _Tip: you can use either position, time, or both._

3. **Explore results (Results page)**
   - **Sky map:** markers show matches; the circle is the field of view. Click a marker for details; pan/zoom as needed.
   - **Charts:**
     - **Timeline:** observation start/end per result.
     - **Energy Range:** min/max energy (TeV).
   - **Table:** sortable, with column toggle. **DataLink** buttons download FITS files.

4. **Signed-in features (Profile → CTAO IAM)**
   - **Query Store:** reload or delete past queries.
   - **Baskets:** add items from the map, charts, or table; manage multiple baskets. The **active** basket receives new items.
   - **Run a Preview Job (OPUS):**
     - With a basket active, click **Run Preview Job**. Review the prefilled parameters (e.g., RA, Dec, `nxpix`, `nypix`, `binsz`) and submit.
     - Track progress under **Preview Jobs**. Open a job to **Download** outputs or **Show preview** inline for PNG/SVG/text results.

# About CTAO

The Cherenkov Telescope Array Observatory (CTAO) is a ground-based observatory for gamma-ray astronomy. This project interacts with CTAO data to provide users with tools for visualization and analysis, enhancing the accessibility and understanding of gamma-ray observations.
- [CTAO website](https://www.ctao.org/)