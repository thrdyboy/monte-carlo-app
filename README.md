# Monte Carlo App

A rainfall forecasting and runoff analysis platform using **Monte Carlo simulation** and the **SCS-CN (Soil Conservation Service Curve Number)** method.

The project is divided into two applications:

* **`monte-carlo-parser`** — Backend and ETL pipeline using Docker, Apache Airflow, PostgreSQL, MinIO, and FastAPI.
* **`monte-carlo-viewer`** — React + Vite frontend for running simulations and viewing results.

---

## High-Level Architecture

```text
┌──────────────────────────────────────────────────────────────────────┐
│                        monte-carlo-parser                            │
│                            Docker Stack                              │
│                                                                      │
│  ┌─────────────┐    ┌──────────────────┐    ┌─────────────────────┐  │
│  │   FastAPI   │───►│     Airflow      │───►│    ETL Pipeline     │  │
│  │  Port 8000  │    │                  │    │                     │  │
│  │             │    │ monte_carlo_     │    │ 1. Extract          │  │
│  │  /api/*     │    │ etl_pipeline     │    │ 2. Monte Carlo      │  │
│  └──────┬──────┘    └────────┬─────────┘    │ 3. SCS-CN Runoff    │  │
│         │                    │              │ 4. Save Files       │  │
│         │                    │              │ 5. Generate Plots   │  │
│         │                    │              │ 6. PostgreSQL Load  │  │
│         │                    ▼              │ 7. MinIO Upload     │  │ 
│         │           ┌──────────────────┐    └──────────┬──────────┘  │
│         └──────────►│    PostgreSQL    │◄──────────────┘             │
│                     │   Data Warehouse │                             │
│                     │                  │                             │
│                     │ • mc_combined    │                             │
│                     │ • runoff_details │                             │
│                     │ • rekap_*        │                             │
│                     │ • artifacts      │                             │
│                     │ • run_metrics    │                             │
│                     └──────────────────┘                             │
│                                                                      │
│                     ┌──────────────────┐                             │
│                     │      MinIO       │                             │
│                     │                  │                             │
│                     │ mc-parquet/      │ ← Parquet files             │
│                     │ mc-plots/        │ ← PNG plots                 │
│                     └──────────────────┘                             │
└──────────────────────────────────────────────────────────────────────┘
                              ▲
                              │ HTTP /api/*
                              │
┌─────────────────────────────┴────────────────────────────────────────┐
│                    monte-carlo-viewer                                │
│                         React + Vite                                 │
│                                                                      │
│ • New Run: Manual Input / Excel Upload                               │
│ • Latest Results: Metrics / Plots / Tables                           │
│ • Excel Report Download                                              │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Prerequisites

Before running the project, make sure you have:

* **Docker Desktop** with at least 8 GB RAM allocated
* **Node.js 18+**
* **Conda** *(optional, for local ETL debugging)*

---

# Backend

## `monte-carlo-parser`

The backend contains the ETL pipeline, Airflow DAG, FastAPI service, PostgreSQL warehouse, and MinIO object storage.

## 1. Configure Environment

Copy `.env.example` to `.env` in the project root and fill in the required values.

```env
AIRFLOW_UID=
AIRFLOW_GID=

AIRFLOW_DB_USER=
AIRFLOW_DB_PASSWORD=
AIRFLOW_DB_NAME=

WAREHOUSE_DB_USER=
WAREHOUSE_DB_PASSWORD=
WAREHOUSE_DB_NAME=

MINIO_ROOT_USER=
MINIO_ROOT_PASSWORD=

AIRFLOW_ADMIN_USER=
AIRFLOW_ADMIN_PASSWORD=
```

The Docker Compose configuration and Monte Carlo configuration read these values from the environment.

> **Important:** Do not commit `.env` to version control.


---

## 2. Initialize the Database

Run the Airflow initialization container:

```bash
docker compose up airflow-init
```

This initializes the Airflow database and creates the Airflow administrator account.

---

## 3. Start the Backend Stack

Start all services in detached mode:

```bash
docker compose up -d
```

The stack includes:

| Service              | Purpose                     |           Port |
| -------------------- | --------------------------- | -------------: |
| `postgres`           | Airflow metadata database   |       Internal |
| `warehouse-postgres` | ETL output / data warehouse |         `5433` |
| `minio`              | Object storage              | `9000`, `9001` |
| `airflow-webserver`  | Airflow web interface       |         `8080` |
| `airflow-scheduler`  | DAG scheduler               |       Internal |
| `api`                | FastAPI backend             |         `8000` |

---

## 4. Verify Services

### Airflow

```text
http://localhost:8080
```

Credentials Format:

```text
Username: your-username
Password: your-password
```

### MinIO

```text
http://localhost:9001
```

Credentials Format:

```text
Username: your-username
Password: your-password
```

### FastAPI Documentation

```text
http://localhost:8000/docs
```

### Health Check

```bash
curl http://localhost:8000/health
```

---

# Docker Commands

Common commands for managing the backend:

| Task                             | Command                                                                 |
| -------------------------------- | ----------------------------------------------------------------------- |
| View scheduler logs              | `docker compose logs -f airflow-scheduler`                              |
| Restart scheduler                | `docker compose restart airflow-scheduler`                              |
| Rebuild API                      | `docker compose build api && docker compose up -d --force-recreate api` |
| Stop services                    | `docker compose down`                                                   |
| Stop services and remove volumes | `docker compose down -v`                                                |

Use `docker compose down -v` carefully because it removes the Docker volumes containing database and MinIO data.

---

# Backend API

All API endpoints use the `/api` prefix.

## Trigger a Simulation

### Manual Input

```http
POST /api/runs/from-manual
```

Example request:

```json
{
  "data": {
    "2020": {
      "Jan": 250.5,
      "Feb": 220.2
    },
    "2021": {
      "Jan": 260.0,
      "Feb": 230.0
    }
  },
  "forecast_years": 10,
  "num_simulations": 1000,
  "curve_number": 75,
  "river_basin_area": 58.87,
  "runoff_scope": "forecast"
}
```

Parameters:

| Parameter          | Description                                          |
| ------------------ | ---------------------------------------------------- |
| `data`             | Historical rainfall data organized by year and month |
| `forecast_years`   | Number of years to forecast                          |
| `num_simulations`  | Number of Monte Carlo simulations                    |
| `curve_number`     | SCS-CN curve number                                  |
| `river_basin_area` | River basin area                                     |
| `runoff_scope`     | Determines the period used for runoff calculation    |

---

## Excel Upload

```http
POST /api/runs/from-excel
```

The endpoint accepts a multipart form containing an Excel file.

| Field              | Type    | Required |
| ------------------ | ------- | -------- |
| `file`             | `.xlsx` | Yes      |
| `forecast_years`   | Integer | No       |
| `num_simulations`  | Integer | No       |
| `curve_number`     | Float   | No       |
| `river_basin_area` | Float   | No       |
| `runoff_scope`     | String  | No       |

Both manual and Excel-based requests trigger the same Airflow ETL pipeline.

Example response:

```json
{
  "status": "triggered",
  "dag_run_id": "manual__2026-09-12T...",
  "source": "manual",
  "input_path": "data/raw/uploads/manual_latest.json",
  "conf": {}
}
```

---

# Read Results

| Method | Endpoint                       | Description                           |
| ------ | ------------------------------ | ------------------------------------- |
| `GET`  | `/api/runs/metrics`            | Metrics for all runs                  |
| `GET`  | `/api/runs/metrics/{run_id}`   | Metrics for one run                   |
| `GET`  | `/api/latest/plots`            | Plots from the latest run             |
| `GET`  | `/api/latest/tables`           | Preview of latest Parquet tables      |
| `GET`  | `/api/latest/excel`            | Download latest results as Excel      |
| `GET`  | `/api/artifacts/{id}/view`     | View an artifact inline               |
| `GET`  | `/api/artifacts/{id}/download` | Download an artifact                  |
| `GET`  | `/api/artifacts/{id}/excel`    | Convert one Parquet artifact to Excel |

The metrics endpoint provides values such as:

* MAE
* RMSE
* MAPE
* Number of simulations
* Forecast horizon
* Curve Number
* River basin area
* Runoff scope

---

# Frontend

## `monte-carlo-viewer`

The frontend is built with **React, Vite, Tailwind CSS, and Axios**.

---

## 1. Install Dependencies

```bash
cd monte-carlo-viewer
npm install
```

---

## 2. Configure Environment

Create:

```text
.env.development
```

Add:

```env
VITE_BACKEND_URL=http://localhost:8000/api
```

The Vite development server proxies `/api/*` requests to the FastAPI backend.

You can also create:

```text
.env.development.local
```

for personal local configuration. This file is intended to remain gitignored.

---

## 3. Start Frontend

```bash
npm run dev
```

Open:

```text
http://localhost:5173
```

---

# Frontend Features

## New Run

The **New Run** interface provides two input methods:

### Manual Input

Users can enter rainfall data directly into the table.

The table also supports:

* Copy/paste from Excel
* Automatic grid expansion
* Distribution of pasted values
* Indonesian decimal commas such as `83,32`
* Mixed separators

### Excel Upload

Users can upload an `.xlsx` file containing rainfall data.

Both methods use the same backend ETL pipeline.

---

## Latest Results

The **Latest Results** interface provides:

* MAE
* RMSE
* MAPE
* Number of simulations
* Forecast horizon
* Curve Number
* River basin area
* Runoff scope
* Plot gallery
* Table previews
* Per-table downloads
* Consolidated Excel report

---

# End-to-End Workflow

Start the backend:

```bash
cd monte-carlo-parser
docker compose up -d
```

Then start the frontend:

```bash
cd ../monte-carlo-viewer
npm run dev
```

Open:

```text
http://localhost:5173
```

Then:

1. Open **New Run**.
2. Enter rainfall data manually or upload an Excel file.
3. Configure the simulation parameters.
4. Click **Run Pipeline**.
5. The frontend receives the Airflow `dag_run_id`.
6. The interface switches to **Latest Results**.
7. Results are refreshed while the pipeline executes.
8. View the generated metrics, plots, and tables.
9. Download the consolidated Excel report.

---

# ETL Pipeline

The pipeline follows an **Extract → Transform → Load** architecture.

## Extract

There are two supported input paths.

### Excel

Uploaded files are stored as:

```text
data/raw/uploads/excel_latest.xlsx
```

### Manual Input

Manual JSON input is stored as:

```text
data/raw/uploads/manual_latest.json
```

Both inputs are converted into the same DataFrame structure:

```text
Year × Month
```

---

## Transform

### Monte Carlo Simulation

The Monte Carlo process uses **block bootstrap sampling**.

Instead of sampling individual months independently, each forecast year samples an entire historical year. This preserves the intra-year relationship between monthly rainfall values.

The simulation produces:

* Mean
* Standard deviation
* Representative sample

The number of iterations is controlled by `num_simulations`.

### SCS-CN Runoff

The **SCS-CN runoff calculation** can operate on:

* Forecast-only data
* Historical + forecast data

The behavior is controlled through:

```text
runoff_scope
```

---

# Load

The generated results are persisted in three locations.

## Local Storage

```text
data/warehouse/<run_id>/*.parquet
data/warehouse/<run_id>/plots/*.png
```

## PostgreSQL

The warehouse contains tables including:

```text
mc_combined
runoff_details
rekap_tahunan
rekap_bulanan
artifacts
run_metrics
```

### `artifacts`

Stores information about generated files, including:

* Bucket
* Object key
* File size
* Run ID

### `run_metrics`

Stores execution metrics and configuration, including:

* MAE
* RMSE
* MAPE
* Run configuration

## MinIO

Parquet files:

```text
mc-parquet/runs/<run_id>/*.parquet
```

PNG plots:

```text
mc-plots/runs/<run_id>/*.png
```

---


# Tech Stack

| Layer            | Technology         |
| ---------------- | ------------------ |
| Orchestration    | Apache Airflow 2.9 |
| Containerization | Docker             |
| ETL              | Python 3.11        |
| Data Warehouse   | PostgreSQL 16      |
| Object Storage   | MinIO              |
| API              | FastAPI + Uvicorn  |
| Frontend         | React + Vite       |
| Styling          | Tailwind CSS       |
| HTTP Client      | Axios              |
| Data Format      | Parquet + PNG      |
| Visualization    | PNG plots          |

---

# Architecture Notes

### Airflow is responsible for ETL execution

FastAPI does **not** directly execute the Monte Carlo pipeline.

Instead:

```text
Frontend
   │
   ▼
FastAPI
   │
   ▼
Airflow REST API
   │
   ▼
Airflow DAG
   │
   ▼
ETL Pipeline
```

FastAPI is responsible for triggering DAG runs and serving read-only results from PostgreSQL and MinIO.

### Environment Variables

Credentials are provided through:

```text
.env
   │
   ▼
docker-compose
   │
   ▼
Container Environment
   │
   ▼
Python os.environ
```

Credentials should not be hard-coded inside the application.

### Run Isolation

Generated local files and MinIO objects are organized by:

```text
run_id
```

This keeps individual executions separated.

PostgreSQL uses:

* `replace` for the main data tables
* `append` for `artifacts`
* `append` for `run_metrics`

### DAG Configuration

The Airflow DAG can receive configuration overrides when triggered.

Example:

```json
{
  "forecast_years": 10,
  "source": "manual"
}
```

These values can override the default YAML configuration for a particular run.

---

# Data Flow Summary

```text
             ┌──────────────┐
             │     User     │
             └──────┬───────┘
                    │
                    │
             ┌──────▼───────┐
             │ Manual Input |
             |  / Excel     │
             └──────┬───────┘
                    │
                    ▼
             ┌──────────────┐
             │   Extract    │
             │ DataFrame    │
             └──────┬───────┘
                    │
                    ▼
             ┌──────────────┐
             │ Monte Carlo  │
             │ Simulation   │
             └──────┬───────┘
                    │
                    ▼
             ┌──────────────┐
             │   SCS-CN     │
             │    Runoff    │
             └──────┬───────┘
                    │
                    ▼
             ┌──────────────┐
             │   Generate   │
             │   Parquet    │
             │    + PNG     │
             └──────┬───────┘
                    │
          ┌─────────┴─────────┐
          ▼                   ▼
   ┌──────────────┐    ┌──────────────┐
   │  PostgreSQL  │    │    MinIO     │
   │  Warehouse   │    │Object Storage│
   └──────┬───────┘    └──────┬───────┘
          │                   │
          └─────────┬─────────┘
                    ▼
             ┌──────────────┐
             │   FastAPI    │
             └──────┬───────┘
                    │
                    ▼
             ┌──────────────┐
             │ React Viewer │
             └──────────────┘
```

---

# Project Summary

**Monte Carlo App** combines statistical rainfall simulation, hydrological runoff calculation, ETL orchestration, data warehousing, object storage, and a web-based visualization interface into a single Docker-orchestrated platform.

The architecture separates responsibilities between:

* **React** — user interface
* **FastAPI** — API layer
* **Airflow** — workflow orchestration
* **Python** — ETL and simulation logic
* **PostgreSQL** — structured analytical storage
* **MinIO** — object storage for generated artifacts
* **Parquet** — analytical file format
* **Docker** — containerization and orchest