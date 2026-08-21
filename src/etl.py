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


def resolve_tag(text_val, payload):
    if isinstance(text_val, str) and text_val.startswith("$"):
        tag = text_val.replace("$", "")
        long_match = re.search(rf"^{tag}:T[0-9a-f]+,(.*?)$", payload, re.MULTILINE)
        if long_match:
            return long_match.group(1).replace("\\n", "\n").strip()
        short_match = re.search(rf'^{tag}:"(.*?)"$', payload, re.MULTILINE)
        if short_match:
            return short_match.group(1).replace("\\n", "\n").strip()
    return text_val


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
):
    if to_database:
        status, engine = is_connected_to_db(db_uri_key)
    if not status:
        return

    all_results = []
    page = 1

    print(f"\n{'=' * 50}")
    print("Starting massive scrape for ALL Maganghub internships...")
    print(f"{'=' * 50}")

    while True:
        url = f"https://maganghub.kemnaker.go.id/national-batch/vacancy?page={page}"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

        print(f"-> Fetching page {page}...")

        try:
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
        except requests.RequestException as e:
            print(f"   Network error on page {page}: {e}")
            break

        # Force UTF-8 encoding so bullet points (•) and special characters render correctly
        response.encoding = "utf-8"

        # Reconstruct the Next.js stream
        scripts = re.findall(r'__next_f\.push\(\[\d+,\s*(".*?")\]\)', response.text)
        rsc_payload = ""
        for script in scripts:
            try:
                rsc_payload += json.loads(script)
            except json.JSONDecodeError:
                continue

        if not rsc_payload:
            print("   Could not load page data. Stopping loop.")
            break

        # Extract the main JSON block
        match = re.search(
            r'"initialVacancies":(\{"data":\[.*?\],"links":\{.*?\},"meta":\{.*?\}\})',
            rsc_payload,
        )

        if not match:
            print(f"   No job list found on page {page}. Stopping loop.")
            break

        try:
            data = json.loads(match.group(1))
            vacancies = data.get("data", [])

            if not vacancies:
                print(f"   No more jobs found on page {page}.")
                break

            # Extract the data
            for job in vacancies:
                raw_desc = job.get("taskDescription", "")

                for _ in range(3):
                    if isinstance(raw_desc, str) and raw_desc.startswith("$"):
                        raw_desc = resolve_tag(raw_desc, rsc_payload)
                    else:
                        break

                # Handle `null` API responses by falling back to empty dicts/lists
                organizer = job.get("organizer") or {}
                city = job.get("city") or {}
                education = job.get("educationLevels") or []
                study_programs = job.get("studyPrograms") or []

                extracted = {
                    "job_id": job.get("id"),
                    "job_title": job.get("positionName"),
                    "company": organizer.get("name", "Unknown Company"),
                    "requested_quota": job.get("quantityNeeded") or 0,
                    "real_quota": job.get("approvedQuantity") or 0,
                    "applicant_count": job.get("totalApplications") or 0,
                    "education_levels": ", ".join(education).title(),
                    "weekly_working_day": job.get("workingDaysPerWeek"),
                    "location": city.get("name", "Unknown Location"),
                    "allowed_major": ", ".join(
                        [p.get("name", "") for p in study_programs if isinstance(p, dict)]
                    ),
                    "published_at": job.get("publishedAt"),
                    "description": raw_desc,
                }

                all_results.append(extracted)

            # Check pagination
            meta = data.get("meta", {})
            last_page = meta.get("lastPage", 1)

            if page >= last_page:
                print(f"   Reached the final page ({last_page}). Scraping complete!")
                break

            page += 1
            time.sleep(3)

        except Exception as e:  # noqa: BLE001
            print(f"   Error parsing page {page}: {e}")
            break

    if all_results:
        total_scraped = len(all_results)
        if to_database:
            append_to_db(all_results, "internship_positions", engine)
        else:
            df = pd.DataFrame(all_results)
            df = df.drop_duplicates(subset=["job_id"])
            df.to_parquet(output_path, index=False)

        print(f"\n{'=' * 50}")
        print("Massive Scrape Complete!")
        print(f"Total rows scraped: {total_scraped}")
        print(f"Total unique jobs saved: {len(df)}")
        print("File saved successfully.")
        print(f"{'=' * 50}\n")
    else:
        print("\nNo data was collected.")


if __name__ == "__main__":
    app()
