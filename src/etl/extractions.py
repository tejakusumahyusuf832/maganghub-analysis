"""Module for extracting raw internship data from external web sources."""

import json
import re
import time

from loguru import logger
import pandas as pd
import requests

PROV_URL = "https://raw.githubusercontent.com/edwardsamuel/Wilayah-Administratif-Indonesia/master/csv/provinces.csv"
REG_URL = "https://raw.githubusercontent.com/edwardsamuel/Wilayah-Administratif-Indonesia/master/csv/regencies.csv"


def extract_adm_divisions(prov_url: str = PROV_URL, reg_url: str = REG_URL) -> pd.DataFrame:
    """Extract Indonesian administrative division data from external CSV sources.

    Retrieve province and regency mappings from remote repositories and merge
    them into a single consolidated dataset.

    Args:
        prov_url: The URL pointing to the raw provinces CSV file.
        reg_url: The URL pointing to the raw regencies CSV file.

    Returns:
        A pandas DataFrame containing merged regency and province records.
    """
    logger.info("Extracting administrative divisions data from remote sources.")

    try:
        provinces = pd.read_csv(prov_url, header=None, names=["province_id", "province"])
        regencies = pd.read_csv(
            reg_url, header=None, names=["regency_id", "province_id", "regency"]
        )
    except Exception as e:
        logger.error(f"Failed to fetch administrative divisions data: {e}")
        raise

    adm_divisions = pd.merge(regencies, provinces, on="province_id", how="left")

    logger.info(f"Successfully extracted {len(adm_divisions)} administrative division records.")
    return adm_divisions


def extract_internship_data(page: int) -> tuple[list[dict], str, dict]:
    """Retrieve raw internship position data and metadata for a specific page.

    Args:
        page: The pagination index to fetch.

    Returns:
        A tuple containing the list of raw vacancy dictionaries, the full React
        Server Component (RSC) payload string, and the pagination metadata dictionary.
    """
    url = f"https://maganghub.kemnaker.go.id/national-batch/vacancy?page={page}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    # --- UPDATED: Robust Retry Mechanism ---
    max_retries = 3
    for attempt in range(max_retries):
        try:
            # Increased timeout from 15 to 30 seconds
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            break  # Success! Break out of the retry loop.

        except requests.RequestException as e:
            logger.warning(
                f"Network error on page {page} (Attempt {attempt + 1}/{max_retries}): {e}"
            )
            if attempt == max_retries - 1:
                logger.error(
                    f"Failed to fetch page {page} after {max_retries} attempts. Giving up."
                )
                return [], "", {}
            time.sleep(5)  # Wait 5 seconds before trying again
    # --------------------------------------

    # Force UTF-8 encoding to prevent rendering issues with special characters (e.g., bullet points).
    response.encoding = "utf-8"

    # UPDATED: Added re.DOTALL to span across multiline HTML chunks
    scripts = re.findall(r'__next_f\.push\(\[\d+,\s*(".*?")\]\)', response.text, re.DOTALL)
    rsc_payload = ""
    for script in scripts:
        try:
            rsc_payload += json.loads(script)
        except json.JSONDecodeError:
            continue

    if not rsc_payload:
        logger.warning(f"Failed to load RSC payload on page {page}.")
        return [], "", {}

    # UPDATED: Added re.DOTALL so the wildcard safely ignores newlines inside job descriptions
    match = re.search(
        r'"initialVacancies":(\{"data":\[.*?\],"links":\{.*?\},"meta":\{.*?\}\})',
        rsc_payload,
        re.DOTALL,
    )

    if not match:
        logger.warning(f"No job list structure found on page {page}.")
        return [], rsc_payload, {}
    # ... [Rest of the function continues as normal] ...

    try:
        data = json.loads(match.group(1))
        return data.get("data", []), rsc_payload, data.get("meta", {})
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing JSON on page {page}: {e}")
        return [], rsc_payload, {}
