"""Orchestration module for the Maganghub ETL pipeline."""

from pathlib import Path
import time
from typing import Annotated

from loguru import logger
import pandas as pd
import typer

from src.config import EXTERNAL_DATA_DIR, RAW_DATA_DIR
from src.etl.extractions import extract_adm_divisions, extract_internship_data
from src.etl.loading.connection import connect_to_db
from src.etl.loading.storage import append_to_db
from src.etl.transformations import (
    transform_adm_divisions,
    transform_internship_data,
)

app = typer.Typer()


@app.command()
def main(
    internship_output_path: Annotated[
        Path,
        typer.Argument(help="The path where the output internship Parquet file will be saved."),
    ] = RAW_DATA_DIR / "internship_positions.parquet",
    adm_division_output_path: Annotated[
        Path,
        typer.Argument(
            help="The path where the output adiministrative divisions Parquet file will be saved."
        ),
    ] = EXTERNAL_DATA_DIR / "administrative_divisions.parquet",
    to_database: Annotated[
        bool,
        typer.Option(help="If True, store the data into the database as well."),
    ] = False,
    db_uri_key: Annotated[
        str, typer.Option(help="The URI key of the database from the .env file to store the data.")
    ] = "DB_URI_KEY",
) -> None:
    """Execute the main ETL pipeline for internship data orchestration.

    Manage the pagination loop to extract raw internship data, retrieve geographic
    administrative divisions, apply base transformations, and route the raw datasets
    to local Parquet files or a target database.

    Args:
        internship_output_path: The local filesystem path to save the raw internship Parquet file.
        adm_division_output_path: The local filesystem path to save the administrative divisions Parquet file.
        to_database: Flag indicating whether to store results in a database.
        db_uri_key: The environment variable key containing the database connection URI.
    """
    if to_database:
        is_connected, engine = connect_to_db(db_uri_key)
        if not is_connected:
            logger.error("Database connection failed. Aborting pipeline execution.")
            return

    # Extract and transform internship position data
    all_positions = []
    page = 1

    logger.info("Initiating extraction pipeline from Maganghub.")

    while True:
        logger.info(f"Processing data for page {page}.")

        raw_positions, rsc_payload, meta = extract_internship_data(page)

        if not raw_positions:
            logger.info(f"No additional records found on page {page}. Concluding extraction.")
            break

        clean_positions = transform_internship_data(raw_positions, rsc_payload)
        all_positions.extend(clean_positions)

        last_page = meta.get("lastPage", 1)
        if page >= last_page:
            logger.info(f"Reached the final page ({last_page}). Concluding extraction.")
            break

        page += 1
        time.sleep(3)

    if not all_positions:
        logger.warning("No data was collected during pipeline execution.")
        return

    total_processed = len(all_positions)
    logger.info(f"Total internship positions extracted: {total_processed}")

    logger.info("Initiating extraction and transformation of administrative divisions.")
    raw_adm_divisions = extract_adm_divisions()
    clean_adm_divisions = transform_adm_divisions(raw_adm_divisions)

    if to_database:
        append_to_db(all_positions, "internship_positions", engine)
        logger.info(f"Stored {total_processed} internship records successfully into the database.")

        append_to_db(
            clean_adm_divisions.to_dict(orient="records"), "administrative_divisions", engine
        )
        logger.info("Stored administrative division records successfully into the database.")

    # Deduplicate before saving base datasets to ensure integrity for downstream analytical queries
    clean_intern_positions = pd.DataFrame(all_positions).drop_duplicates(subset=["job_id"])

    clean_intern_positions.to_parquet(internship_output_path, index=False)
    clean_adm_divisions.to_parquet(adm_division_output_path, index=False)
    logger.info(
        f"Saved {len(clean_intern_positions)} unique raw internship records and administrative divisions to local storage."
    )


if __name__ == "__main__":
    app()
