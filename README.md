# CTAO Data Access and Analysis Portal

This project is a web application designed to access, visualize, and analyze data from the **Cherenkov Telescope Array Observatory (CTAO)** project. The application consists of a frontend built with **React** and a backend powered by **FastAPI**. Users can perform searches on CTAO data, select results, and visualize them with different methods, including on an interactive sky map using **Aladin Lite**.

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
- Visualize selected data points with timeline chart and electromagnetic range chart

## Requirements

### Backend

- Python 3.7 or higher
- FastAPI
- Uvicorn
- Aiofiles
- Astropy
- PyVO
- Numpy
- Requests

### Frontend

- Node.js v14 or higher
- React.js
- Axios
- React Data Table Component

## Installation

### Backend Setup

   ```bash
   git clone https://gitlab.obspm.fr/oates/ctao-data-explorer.git
   cd ctao-data-explorer
   conda create -n ctao-backend python=3.8
   conda activate ctao-backend
   conda install -c conda-forge fastapi uvicorn aiofiles pyvo numpy requests
   uvicorn api.main:app --reload
   ```
### Frontend Setup

   ```bash
   cd ctao-data-explorer/js
   npm install
   npm start
   ```

# About CTAO

The Cherenkov Telescope Array Observatory (CTAO) is a ground-based observatory for gamma-ray astronomy. This project interacts with CTAO data to provide users with tools for visualization and analysis, enhancing the accessibility and understanding of gamma-ray observations.
- [CTAO website](https://www.ctao.org/)