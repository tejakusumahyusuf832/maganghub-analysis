# Maganghub Internship Market Analysis

**Decoding the Indonesian Internship Market: Supply, Demand, and Structural Gatekeeping**

An end-to-end data analytics project exploring 28,000+ internship postings to uncover geographic bottlenecks, industry competitiveness, and educational silos. This repository demonstrates a complete analytical workflow—from automated ETL pipelines to advanced predictive modeling and interactive dashboarding—executed seamlessly across **Python**, **PostgreSQL**, and **Microsoft Excel**.

## Executive Summary & Key Insights

* **The Generalist Surge:** Allowing generalist degrees (Social/Law or Business) mathematically triggers massive applicant volume surges. Tech roles attract steady baseline crowds without viral spikes.
* **Regional Bottlenecks:** While Jakarta dominates the baseline volume (~28% of postings), remote postings outside Java—specifically in Sulawesi Selatan—act as severe geographic bottlenecks with a median acceptance rate of just 7.41%.
* **Educational Gatekeeping:** The market is structurally biased toward Bachelor's degrees (accepted by 94.8% of postings). Sectors like Manufacturing actively hire Diploma students, while Correctional & Social Services strictly filter for Bachelor's degrees.

## Architecture & Technical Stack

**1. Python (Data Engineering & Machine Learning)**

* **Automated ETL Pipeline:** Engineered robust orchestration scripts (`data_pipeline.py`, `dataset.py`) to extract paginated API data, apply complex regex-based job categorization, and handle dynamic binning.
* **Multivariate Modeling:** Utilized Jupyter Notebooks to train Random Forest and Negative Binomial regression models, isolating the multiplier effects of geography and major requirements.
* **Market Segmentation:** Applied K-Prototypes clustering and Multiple Correspondence Analysis (MCA) to map employer hiring archetypes into distinct silos.

**2. PostgreSQL (Relational Profiling & Analytics)**

* **Native Data Transformation:** Built analytical views utilizing Common Table Expressions (CTEs), robust `NULL` handling, and pattern matching (`ILIKE`) to flatten raw data into a structured schema.
* **Advanced Statistical Queries:** Replicated Spearman Rank correlations using Window Functions (`RANK() OVER`) and extracted exact medians via `PERCENTILE_CONT` to identify industry bottlenecks without exporting the data.
* **Contingency Matrices:** Utilized conditional aggregation (`FILTER WHERE`) to natively simulate cross-tabulation and expose educational gatekeeping silos.

**3. Microsoft Excel (Dynamic Array Architecture & Dashboarding)**

* **Modern Formula Engine:** Built automated analytical engines using advanced dynamic arrays (`LET`, `MAKEARRAY`, `FILTER`, `HSTACK`) to calculate exact medians and structural pivots in real-time.
* **Memory Optimization:** Overcame web-calculation memory limits by materializing statistical ranks into physical helper columns, successfully calculating Spearman Rank correlations across 28,322 rows without Lambda loop timeouts.
* **Parameterized Simulation Dashboard:** Designed a custom dynamic dashboard using Data Validation controls to visually simulate the predictive regression drivers natively in a spreadsheet environment.

## Repository Structure

```text
maganghub-analysis/
├── data/
│   ├── external/
│   ├── interim/
│   ├── processed/
│   └── raw/
├── notebooks/                   # Python EDA, Machine Learning & Clustering
├── queries/                     # PostgreSQL Profiling, ETL & Analytics
├── spreadsheets/                # Excel Dynamic Array EDA & Interactive Dashboards
├── src/
│   ├── elt/                     # API Extraction & Database Loading 
│   ├── config.py
│   ├── data_pipeline.py         # Pipeline Orchestration
│   └── dataset.py               # Feature Engineering & Regex Classification
├── pyproject.toml
└── README.md

```

## Execution Guide

**1. Environment Setup**
Ensure Python 3.10+ is installed. Clone the repository and install dependencies using `uv`:

```bash
git clone https://github.com/yourusername/maganghub-analysis.git
cd maganghub-analysis
uv sync

```

**2. Run the Data Pipeline**
Execute the main orchestration script to extract paginated data, apply transformations, and save to local Parquet files (optionally routing to PostgreSQL via the `--to-database` flag):

```bash
uv run python -m src.data_pipeline

```

**3. Generate Analytical Dataset**
Integrate features and categorize job titles into the final analytical schema:

```bash
uv run python -m src.dataset

```