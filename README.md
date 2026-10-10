# NYC Urban Mobility Data Explorer & Analytical Dashboard

A small Flask dashboard for cleaning and exploring New York City taxi trip data from the TLC.

## Quick Start & Launch Instructions

Ensure you have your raw dataset files (`yellow_tripdata.parquet` and `taxi_zone_lookup.csv`) placed inside a folder named `data/` in the project root.

The `data/` folder is intentionally not committed because the TLC parquet file is large. Download a yellow taxi trip parquet file and the matching taxi zone lookup CSV from the NYC TLC trip record page, then place them at `data/yellow_tripdata.parquet` and `data/taxi_zone_lookup.csv`. The pipeline creates `data/output/quality_log.txt` and `data/output/excluded_rows_sample.csv` after each run.

```bash
cd duplicate-Urban-Mobility-Data-Explorer

pip install -r requirements.txt

python run.py
```

 Once running, navigate directly to **`http://127.0.0.1:5000`** on your web browser to access the live dashboard panel.

Run the synthetic ETL regression test with `python -m unittest tests/test_pipeline.py`. It verifies TLC column normalization, duplicate handling, zero-distance flagging, and quality outputs without requiring the full dataset.

## System Architecture Design

- **Data pipeline:** Cleans, validates, and loads trip records into SQLite.
- **Database:** Stores trips, taxi zones, payment types, rate codes, and flagged records.
- **Top-K heap:** Finds the busiest pickup zones without sorting every result.
- **Dashboard:** Shows summary metrics and three query-backed transport insights.

## Data Quality Policy

- Raw TLC names such as `VendorID` and `RatecodeID` are normalized to the schema names `vendor_id` and `rate_code_id`; unrelated raw columns are ignored.
- Exact duplicate rows and rows missing required fields are excluded and counted. A sample of up to 1,000 excluded rows is saved for inspection.
- Distance, fare, passenger, zone, and duration rules are counted separately in the quality log. The 100-mile and $500 limits are conservative bounds for ordinary NYC taxi trips; the 36-second and 5-hour duration limits remove records that cannot produce a useful speed metric.
- Valid zero-distance trips are retained in `flagged_trips` rather than silently discarded, so high-fare or idling records can be investigated separately.

## Dashboard Insights

The dashboard presents three query-backed views: peak demand and average speed by hour, recorded tipping by payment type, and the busiest borough-to-borough flows. Together they show when demand strains speed, how payment method changes observed tipping, and where trips concentrate across the city.

## Video Walkthrough Reference Link

- **System Tour Link:** [Insert your private YouTube/Loom demonstration link here]
