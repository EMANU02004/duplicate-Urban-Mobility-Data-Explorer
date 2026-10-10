# 🚕 NYC Urban Mobility Data Explorer & Analytical Dashboard

An enterprise-level fullstack data intelligence platform engineered to process, clean, map, and visualize high-throughput urban transit footprints utilizing raw New York City Taxi & Limousine Commission (TLC) spatial and transaction metrics.

## 🚀 Quick Start & Launch Instructions

Ensure you have your raw dataset files (`yellow_tripdata.parquet` and `taxi_zone_lookup.csv`) placed inside a folder named `data/` in the project root.

```bash
# 1. Clone the repository and navigate to the project directory
cd duplicate-Urban-Mobility-Data-Explorer

# 2. Install optimized low-dependency requirements
pip install -r requirements.txt

# 3. Boot the system (Initializes DB, runs the ETL engine, and boots Flask)
python run.py
```
 Once running, navigate directly to **`http://127.0.0.1:5000`** on your web browser to access the live dashboard panel.

## 🛠️ System Architecture Design
- **Data Engineering Layer:** Streamlined analytical pipeline executing automated outliers isolation, timestamp standardization, transaction health logging, and multi-row database writing.
- **Relational Storage Matrix:** Normalized database schema outfitted with custom strategic composite foreign key indexing to reduce query lookups down to optimal execution times.
- **Algorithmic Engine:** A purely custom library-free, zero-dependency **K-Way Min-Heap** structure that ranks transit hubs directly via algorithmic data streams without utilizing database modifiers or memory-intensive collection objects.
- **Interactive UI Panel:** A lightweight, vanilla JavaScript micro-dashboard that binds asynchronous state changes back to live backend REST routes without rendering delay blocks.

## 📹 Video Walkthrough Reference Link
- **System Tour Link:** [Insert your private YouTube/Loom demonstration link here]
