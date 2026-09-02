"""Module for cleaning, resolving, and structuring raw internship data."""

import re

from loguru import logger
import pandas as pd


def resolve_tag(text_val: str, payload: str) -> str:
    """Resolve encoded string references from a React Server Component (RSC) payload.

    Args:
        text_val: The raw text value potentially containing a reference tag.
        payload: The full React Server Component (RSC) payload string.

    Returns:
        The decoded string if a reference is found, otherwise the original text value.
    """
    if isinstance(text_val, str) and text_val.startswith("$"):
        tag = text_val.replace("$", "")

        # Next.js splits payloads into dictionaries; accommodate both T-prefixed and quoted formats.
        long_match = re.search(rf"^{tag}:T[0-9a-f]+,(.*?)$", payload, re.MULTILINE)
        if long_match:
            return long_match.group(1).replace("\\n", "\n").strip()

        short_match = re.search(rf'^{tag}:"(.*?)"$', payload, re.MULTILINE)
        if short_match:
            return short_match.group(1).replace("\\n", "\n").strip()

    return text_val


def transform_internship_data(raw_vacancies: list[dict], rsc_payload: str) -> list[dict]:
    """Clean, resolve, and flatten raw vacancy data into a standardized schema.

    Args:
        raw_vacancies: The list of raw internship dictionaries extracted from the source.
        rsc_payload: The raw string payload used to resolve reference tags.

    Returns:
        A list of dictionaries conforming to the target structural schema.
    """
    transformed_data = []

    for job in raw_vacancies:
        raw_desc = job.get("taskDescription", "")

        # Bounded loop prevents infinite recursion on chained Next.js references.
        for _ in range(3):
            if isinstance(raw_desc, str) and raw_desc.startswith("$"):
                raw_desc = resolve_tag(raw_desc, rsc_payload)
            else:
                break

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

        transformed_data.append(extracted)

    return transformed_data


def transform_adm_divisions(data: pd.DataFrame) -> pd.DataFrame:
    """Clean and standardize Indonesian administrative division text formatting.

    Args:
        data: The raw administrative division DataFrame containing 'regency' and 'province' columns.

    Returns:
        A formatted pandas DataFrame with standardized administrative names.
    """
    logger.info("Standardizing administrative divisions text formats.")
    adm_divisions = data.copy()

    adm_divisions["regency"] = adm_divisions["regency"].str.title().str.strip()
    adm_divisions["province"] = adm_divisions["province"].str.title().str.strip()
    adm_divisions.loc[adm_divisions.province.str.contains(r"Jakarta|Yogyakarta"), "province"] = (
        adm_divisions["province"].str.replace({"Dki": "DKI", "Di": "DI"})
    )

    # Align standard prefixes with the Maganghub dataset conventions to improve join rates
    adm_divisions["regency"] = adm_divisions["regency"].str.replace("Kabupaten ", "Kab. ")
    adm_divisions["regency"] = adm_divisions["regency"].str.replace(
        "Kota Jakarta", "Kota Adm. Jakarta"
    )

    return adm_divisions
