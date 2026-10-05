# Urban Mobility Data Explorer

This project is a self-contained full-stack dashboard for exploring NYC taxi mobility patterns. It combines a small relational schema with a lightweight Flask backend and a dynamic HTML/CSS/JavaScript frontend.

## Project goals

- Process and normalize trip-level mobility data
- Store the cleaned records in SQLite for fast exploration
- Expose dashboard-ready API endpoints for summary and trip-level analysis
- Visualize key mobility signals such as hourly demand, borough demand, and zone hotspots

## Stack

- Backend: Python + Flask
- Database: SQLite
- Frontend: HTML, CSS, JavaScript
- Data pipeline: Python scripts that generate demo data and can optionally load official TLC files if they are placed in the `data/` folder

## Quick start

1. Open a terminal in this folder.
2. Create and activate a virtual environment if needed.
3. Install dependencies:

```bash
python -m pip install -r requirements.txt
```

4. Generate the database and start the API server:

```bash
python backend/app.py
```

5. Open the dashboard in a browser at:

```text
http://localhost:5050/
```
## Data source and processing

The project follows the TLC schema for trip records and taxi zone metadata. If the official files are available, place them into the `data/` folder as follows:

- `data/yellow_tripdata.parquet`
- `data/taxi_zone_lookup.csv`
- `data/taxi_zones.geojson`

The app is also seeded with a synthetic demo dataset so it can run immediately without any external downloads.

## API overview

- `GET /api/health` — health check
- `GET /api/overview` — key metrics and summary
- `GET /api/insights` — hourly and borough trends
- `GET /api/trips` — filtered trip records

Example:

```bash
curl "http://localhost:5050/api/overview"
curl "http://localhost:5050/api/trips?borough=Manhattan&sort=fare&limit=10"
```

## Project structure

```text
urban-mobility-data-explorer/
├── backend/
│   ├── app.py
│   └── data_pipeline.py
├── database/
│   └── schema.sql
├── frontend/
│   ├── app.js
│   ├── index.html
│   └── styles.css
├── data/
│   └── urban_mobility.db
├── requirements.txt
├── README.md
└── .gitignore
```

## Custom algorithm requirement

A custom top-zone tracker is implemented in `backend/data_pipeline.py` using an insertion-sort based routine instead of relying on built-in queue or counting libraries. The algorithm keeps the top zone summaries in descending order without external packages.

## Insights from the dashboard

- Manhattan has the highest concentration of trips and pickup demand
- The strongest trip demand clusters around midday and early evening windows
- Higher fare runs are usually associated with longer distances and extended travel times

## Video walkthrough

Video walkthrough: add your link here after recording the demo.

## Notes

This project intentionally uses a compact local SQLite implementation to keep the app runnable and portable. For production-scale workloads, the same schema can be migrated to PostgreSQL with the same relational structure.
