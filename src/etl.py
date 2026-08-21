import json
from pathlib import Path
import re
import time
from typing import Annotated

from loguru import logger
import pandas as pd
import requests
import typer

from src.config import INTERIM_DATA_DIR
from src.db.connection import is_connected_to_db
from src.db.storage import append_to_db

app = typer.Typer()


def resolve_tag(text_val: str, payload: str) -> str:
    """Resolve Next.js encoded string references from the RSC payload.

    Args:
        text_val: The raw text value potentially containing a reference tag.
        payload: The full React Server Component (RSC) payload string.

    Returns:
        The decoded string if a reference is found, otherwise the original text value.
    """
    if isinstance(text_val, str) and text_val.startswith("$"):
        tag = text_val.replace("$", "")

        # Next.js optimizes payloads by splitting strings into a separate dictionary.
        # This parses both long-form (T-prefixed) and short-form quoted string definitions.
        long_match = re.search(rf"^{tag}:T[0-9a-f]+,(.*?)$", payload, re.MULTILINE)
        if long_match:
            return long_match.group(1).replace("\\n", "\n").strip()

        short_match = re.search(rf'^{tag}:"(.*?)"$', payload, re.MULTILINE)
        if short_match:
            return short_match.group(1).replace("\\n", "\n").strip()

    return text_val


def scrape_all_positions() -> list[dict]:
    """Extract all available internship positions from the Maganghub platform.

    Iterates through the paginated API, reconstructs the Next.js Server Component
    payload, and parses the relevant job data into a structured format.

    Returns:
        A list of dictionaries containing the extracted details for each internship position.
    """
    all_results = []
    page = 1

    logger.info("Starting extraction of all internship positions from Maganghub.")

    while True:
        url = f"https://maganghub.kemnaker.go.id/national-batch/vacancy?page={page}"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

        logger.info(f"Fetching data from page {page}.")

        try:
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
        except requests.RequestException as e:
            logger.error(f"Network error encountered on page {page}: {e}")
            break

        # Force UTF-8 encoding so bullet points (•) and special characters render correctly
        response.encoding = "utf-8"

        # The portal utilizes Next.js streaming. The actual JSON data is embedded
        # within JavaScript push arrays, requiring reconstruction before parsing.
        scripts = re.findall(r'__next_f\.push\(\[\d+,\s*(".*?")\]\)', response.text)
        rsc_payload = ""
        for script in scripts:
            try:
                rsc_payload += json.loads(script)
            except json.JSONDecodeError:
                continue

        if not rsc_payload:
            logger.warning(f"Failed to load RSC payload on page {page}. Terminating extraction.")
            break

        # Extract the main JSON block
        match = re.search(
            r'"initialVacancies":(\{"data":\[.*?\],"links":\{.*?\},"meta":\{.*?\}\})',
            rsc_payload,
        )

        if not match:
            logger.warning(f"No job list structure found on page {page}. Terminating extraction.")
            break

        try:
            data = json.loads(match.group(1))
            vacancies = data.get("data", [])

            if not vacancies:
                logger.info(f"No further jobs found on page {page}. Extraction finished.")
                break

            # Extract the data
            for job in vacancies:
                raw_desc = job.get("taskDescription", "")

                # Next.js references can be chained (e.g., $a -> $b -> text).
                # A bounded loop safely resolves these without risking infinite recursion.
                for _ in range(3):
                    if isinstance(raw_desc, str) and raw_desc.startswith("$"):
                        raw_desc = resolve_tag(raw_desc, rsc_payload)
                    else:
                        break

                # Target fields are occasionally null in the backend database.
                # Fallbacks prevent TypeErrors during dictionary extraction.
                organizer = job.get("organizer") or {}
                city = job.get("city") or {}
                education = job.get("educationLevels") or []
                study_programs = job.get("studyPrograms") or []

                extracted = {
                    "job_id": job.get("id"),
                    "published_at": job.get("publishedAt"),
                    "job_title": job.get("positionName"),
                    "company": organizer.get("name", "Unknown Company"),
                    "job_location": city.get("name", "Unknown Location"),
                    "education_level": ", ".join(education).title(),
                    "allowed_major": ", ".join(
                        [p.get("name", "") for p in study_programs if isinstance(p, dict)]
                    ),
                    "job_description": raw_desc,
                    "weekly_working_day": job.get("workingDaysPerWeek"),
                    "requested_quota": job.get("quantityNeeded") or 0,
                    "approved_quota": job.get("approvedQuantity") or 0,
                    "applicant_count": job.get("totalApplications") or 0,
                }

                all_results.append(extracted)

            # Check pagination
            meta = data.get("meta", {})
            last_page = meta.get("lastPage", 1)

            if page >= last_page:
                logger.info(f"Reached the final page ({last_page}). Extraction complete.")
                break

            page += 1
            time.sleep(3)

        except Exception as e:  # noqa: BLE001
            logger.error(f"Error parsing JSON on page {page}: {e}")
            break

    return all_results


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
    """Execute the Maganghub scraping pipeline.

    Extracts internship data and routes the output either to a local Parquet
    file or a target database based on the provided configuration.

    Args:
        output_path: The local path to save the generated Parquet file.
        to_database: Flag indicating whether to store results directly in a database.
        db_uri_key: The environment variable key containing the database connection URI.
    """
    if to_database:
        status, engine = is_connected_to_db(db_uri_key)
        if not status:
            logger.error("Database connection failed. Aborting process.")
            return

    all_results = scrape_all_positions()

    if all_results:
        total_scraped = len(all_results)
        logger.info(f"Total positions extracted: {total_scraped}")

        if to_database:
            append_to_db(all_results, "internship_positions", engine)
            logger.info(f"Successfully stored {total_scraped} positions into the database.")
        else:
            df = pd.DataFrame(all_results)
            df = df.drop_duplicates(subset=["job_id"])
            df.to_parquet(output_path, index=False)
            logger.info(f"Successfully saved {len(df)} unique positions to {output_path}.")

    else:
        logger.warning("No data was collected during the extraction process.")


if __name__ == "__main__":
    app()
