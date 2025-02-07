# CTAO Data Access and Analysis Portal

This project is a web application for accessing, visualizing, and analyzing data from the **Cherenkov Telescope Array Observatory (CTAO)**. It features a **React**-based frontend and a **FastAPI**-powered backend. Users can perform data searches, select relevant results, and explore visualizations through various methods, including an interactive sky map powered by **Aladin Lite**. The project leverages standards from the [International Virtual Observatory Alliance (IVOA)](https://ivoa.net/) to ensure interoperability and accessibility of astronomical data. 

## Table of Contents

- [Features](#features)
- [Requirements](#requirements)
- [Installation](#installation)
  - [Backend Setup](#backend-setup)
  - [Frontend Setup](#frontend-setup)
- [Usage](#usage)
- [About CTAO](#about-ctao)

## Features

- Access and query CTAO data with customizable parameters.
- Display search results in a data table with selectable rows.
- Visualize selected data points on an interactive sky map using **Aladin Lite**.
- Visualize selected data points with timeline chart and electromagnetic range chart.

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
   conda install -c conda-forge fastapi uvicorn aiofiles pyvo numpy requests \
    fastapi-users-db-sqlalchemy authlib itsdangerous asyncpg postgresql alembic psycopg2
   # Set up PostgreSQL
   psql -U postgres
   CREATE DATABASE fastapi_db;
   CREATE USER user WITH PASSWORD 'password'; # Adjust user name and password
   GRANT ALL PRIVILEGES ON DATABASE fastapi_db TO user;
   # Apply Alembic migrations
   alembic upgrade head
   # Run the backend
   uvicorn api.main:app --reload
   ```
### Frontend Setup

   ```bash
   cd ctao-data-explorer/js
   npm install
   npm run build
   ```

# About CTAO

The Cherenkov Telescope Array Observatory (CTAO) is a ground-based observatory for gamma-ray astronomy. This project interacts with CTAO data to provide users with tools for visualization and analysis, enhancing the accessibility and understanding of gamma-ray observations.
- [CTAO website](https://www.ctao.org/)