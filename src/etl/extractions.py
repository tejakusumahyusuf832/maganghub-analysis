"""Module for extracting raw internship data from external web sources."""

import json
import re

from loguru import logger
import requests


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

    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"Network error encountered on page {page}: {e}")
        return [], "", {}

    # Force UTF-8 encoding to prevent rendering issues with special characters (e.g., bullet points).
    response.encoding = "utf-8"

    scripts = re.findall(r'__next_f\.push\(\[\d+,\s*(".*?")\]\)', response.text)
    rsc_payload = ""
    for script in scripts:
        try:
            rsc_payload += json.loads(script)
        except json.JSONDecodeError:
            continue

    if not rsc_payload:
        logger.warning(f"Failed to load RSC payload on page {page}.")
        return [], "", {}

    match = re.search(
        r'"initialVacancies":(\{"data":\[.*?\],"links":\{.*?\},"meta":\{.*?\}\})',
        rsc_payload,
    )

    if not match:
        logger.warning(f"No job list structure found on page {page}.")
        return [], rsc_payload, {}

    try:
        data = json.loads(match.group(1))
        return data.get("data", []), rsc_payload, data.get("meta", {})
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing JSON on page {page}: {e}")
        return [], rsc_payload, {}
