"""Orchestration module for the Maganghub ETL pipeline."""

from pathlib import Path
import time
from typing import Annotated

from loguru import logger
import pandas as pd
import typer

from src.config import INTERIM_DATA_DIR
from src.etl.extractions import extract_internship_data
from src.etl.loading.connection import is_connected_to_db
from src.etl.loading.storage import append_to_db
from src.etl.transformations import transform_internship_data

app = typer.Typer()


@app.command()
def main(
    output_path: Annotated[
        Path, typer.Argument(help="The path where the output Parquet file will be saved.")
    ] = INTERIM_DATA_DIR / "internship_positions.parquet",
    to_database: Annotated[
        bool,
        typer.Option(help="If True, store the data into the database instead of saving the file."),
    ] = False,
    db_uri_key: Annotated[
        str, typer.Option(help="The URI key of the database from the .env file to store the data.")
    ] = "DB_URI_KEY",
) -> None:
    """Execute the main ETL pipeline for internship data orchestration.

    Manage the pagination loop to extract raw data, apply transformations,
    and route the structured output to either a local Parquet file or a database.

    Args:
        output_path: The local filesystem path to save the generated Parquet file.
        to_database: Flag indicating whether to store results directly in a database.
        db_uri_key: The environment variable key containing the database connection URI.
    """
    if to_database:
        status, engine = is_connected_to_db(db_uri_key)
        if not status:
            logger.error("Database connection failed. Aborting pipeline execution.")
            return

    all_results = []
    page = 1

    logger.info("Initiating extraction pipeline from Maganghub.")

    while True:
        logger.info(f"Processing data for page {page}.")

        raw_vacancies, rsc_payload, meta = extract_internship_data(page)

        if not raw_vacancies:
            logger.info(f"No additional records found on page {page}. Concluding extraction.")
            break

        clean_vacancies = transform_internship_data(raw_vacancies, rsc_payload)
        all_results.extend(clean_vacancies)

        last_page = meta.get("lastPage", 1)
        if page >= last_page:
            logger.info(f"Reached the final page ({last_page}). Concluding extraction.")
            break

        page += 1
        time.sleep(3)

    if not all_results:
        logger.warning("No data was collected during pipeline execution.")
        return

    total_processed = len(all_results)
    logger.info(f"Total positions processed: {total_processed}")

    if to_database:
        append_to_db(all_results, "internship_positions", engine)
        logger.info(f"Stored {total_processed} records successfully into the database.")
    else:
        df = pd.DataFrame(all_results)
        df = df.drop_duplicates(subset=["job_id"])
        df.to_parquet(output_path, index=False)
        logger.info(f"Saved {len(df)} unique records successfully to {output_path}.")


if __name__ == "__main__":
    app()
