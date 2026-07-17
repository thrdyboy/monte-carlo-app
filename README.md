# Monte Carlo App

Repository for running Monte Carlo simulations (ETL pipeline) from:
- **conda Python ETL + FastAPI** (backend)
- **React (Vite) frontend** (UI + visualization)

## High-level architecture

### 1) `monte-carlo-parser` (ETL + FastAPI)
Implements an ETL pipeline for the Monte Carlo simulation:
- **Extract**: read historical data from an **Excel file** or from **manual input**
- **Transform**: run the Monte Carlo forecast logic (sampling months from historical distributions)
- **Load**: persist outputs (plots + metrics + combined dataset) into `data/processed/`

Then serves the outputs and endpoints through **FastAPI**.

### 2) `monte-carlo-viewer` (React + Vite)
Provides a UI for:
- uploading an Excel file (or manual inputs)
- calling the FastAPI endpoints
- displaying results (metrics + plot images returned as URLs)

---

## Backend (ETL + FastAPI) using conda

### Requirements
- An installed **Anaconda/Miniconda**
- Python environment based on `monte-carlo-parser/environment.yml`

### Step-by-step setup

#### 1. Create conda environment
From repo root:

```bash
conda env create -f monte-carlo-parser/environment.yml
```

#### 2. Activate environment
```bash
conda activate monte-carlo-etl
```

#### 3. Start FastAPI server
Run the backend entrypoint:

```bash
uvicorn monte-carlo-parser.main:app --reload --port 8000
```

> If you prefer, you can also run from inside `monte-carlo-parser/`.

### Backend endpoints

#### Health
- `GET /`

#### Run simulation from manual inputs (ETL Extract from JSON)
- `POST /run-simulation`
- Body example:

```json
{
  "data": {
    "2020": {"Jan": 10.5, "Feb": 12.0, "Mar": 9.8, "...": 0},
    "2021": {"Jan": 11.2, "Feb": 13.1, "Mar": 10.4, "...": 0}
  },
  "forecast_years": 5
}
```

#### Run simulation from Excel (ETL Extract from file)
- `POST /upload-excel`
- Multipart form field:
  - `file` (required): `.xlsx` or `.xls`
- Optional query parameter:
  - `forecast_years` (number)

#### Get last generated outputs
- `GET /get-data`

Returns:
- `metrics` (`MAE`, `RMSE`, `MAPE`)
- `plot_urls.timeseries` and `plot_urls.heatmap`
- `forecast_years_used`, `random_seed_used`

Plots are served from:
- `GET /static/timeseries_plot.png`
- `GET /static/heatmap_plot.png`

---

## Frontend (React + Vite)

### Requirements
- Node.js 18+

### Step-by-step setup

#### 1. Install dependencies
From repo root:

```bash
cd monte-carlo-viewer
npm install
```

#### 2. Start Vite dev server
```bash
npm run dev
```

By default, Vite serves on `http://localhost:5173` but in Production it would be changed.

### Configure backend base URL
If your frontend currently calls the backend with a different host/port, update:
- `monte-carlo-viewer/src/services/api.ts`

(React uses Axios to call the FastAPI routes like `/run-simulation`, `/upload-excel`, `/get-data`.)

---

## End-to-end run (typical)

1) Start backend:
```bash
conda activate monte-carlo-etl
uvicorn monte-carlo-parser.main:app --reload --port 8000
```

2) Start frontend:
```bash
cd monte-carlo-viewer
npm run dev
```

3) Open the Vite URL in your browser and:
- upload an Excel file (or use manual inputs)
- run simulation
- view metrics and the generated plots

---

## Notes on data flow (ETL)

### Extract
- **Excel path**: `monte-carlo-parser/data/raw/` (uploaded files are stored here)
- **Manual input path**: JSON format converted into a year/month dataframe

### Transform
- Forecasts `forecast_years` future years by sampling each month from historical monthly values.
- Computes metrics comparing historical mean values vs predicted mean values.

### Load
Writes into `monte-carlo-parser/data/processed/`:
- `timeseries_plot.png`
- `heatmap_plot.png`
- `metrics.json`
- `metadata.json`
- a combined dataset file (csv or excel depending on config)

---

## Repository structure

- `monte-carlo-parser/`
  - `main.py` (FastAPI app)
  - `src/etl/` (`extract.py`, `transform.py`, `load.py`)
  - `data/raw/`, `data/processed/`
  - `environment.yml`
- `monte-carlo-viewer/`
  - React + Vite application
  - `src/services/api.ts` (Axios client)
  - `src/components/` (upload/input + display components)

