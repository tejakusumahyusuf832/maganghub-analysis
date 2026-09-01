"""Module for cleaning, resolving, and structuring raw internship data."""

import re

from loguru import logger
import numpy as np
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


def transform_all_data(
    internship_data: pd.DataFrame, adm_division_data: pd.DataFrame
) -> pd.DataFrame:
    """Merge internship data with administrative divisions and calculate derived metrics.

    Map raw job locations to their corresponding provinces using tiered matching logic,
    engineer new features, and structure the final dataset for loading.

    Args:
        internship_data: The cleaned DataFrame containing internship vacancy records.
        adm_division_data: The standardized DataFrame containing administrative divisions.

    Returns:
        A consolidated pandas DataFrame representing the final internship postings table.
    """
    # ===========================================
    # Data Integration
    # ===========================================
    logger.info("Merging internship data with administrative divisions.")
    internship_positions = internship_data.copy()
    adm_divisions = adm_division_data.copy()

    adm_divisions_dict = dict(zip(adm_divisions["regency"], adm_divisions["province"]))
    internship_positions["province"] = internship_positions["job_location"].map(adm_divisions_dict)

    # Fallback mapping: Stripping punctuation and whitespace resolves mismatches
    # caused by inconsistent data entry on the scraped platform.
    plain_adm_div_dict = dict(
        zip(
            adm_divisions["regency"]
            .str.lower()
            .str.replace(r"\sdan\s", " ", case=False, regex=True)
            .str.replace(r"\W", "", regex=True),
            adm_divisions["province"],
        )
    )

    mask = internship_positions["province"].isnull()
    internship_positions.loc[mask, "province"] = (
        internship_positions.loc[mask, "job_location"]
        .str.lower()
        .str.replace(r"\sdan\s", " ", case=False, regex=True)
        .str.replace(r"\W", "", regex=True)
        .map(plain_adm_div_dict)
    )

    # Manual overrides for edge cases missing from the standard division dataset
    manual_dict = {
        "Kab. Kep. Siau Tagulandang Biaro": "Sulawesi Utara",
        "Kab. Mahakam Ulu": "Kalimantan Timur",
        "Kab. Pahuwato": "Gorontalo",
        "Kepulauan Tanimbar": "Maluku",
        "Unknown Location": "Unknown Location",
    }

    mask = internship_positions["province"].isnull()
    internship_positions.loc[mask, "province"] = internship_positions.loc[
        mask, "job_location"
    ].map(manual_dict)

    unmapped_count = internship_positions["province"].isnull().sum()
    if unmapped_count > 0:
        logger.warning(f"{unmapped_count} job locations could not be mapped to a province.")

    # Rename a column
    internship_positions.rename(columns={"job_location": "regency_city"}, inplace=True)

    # Fix some regency and city names
    internship_positions["regency_city"] = (
        internship_positions.regency_city.str.replace(r"^Kab\s", r"Kab. ", regex=True)
        .str.replace("Pahuwato", "Pohuwato")
        .str.replace(r"^Kepulauan\s", r"Kab. Kep. ", regex=True)
        .str.replace(r"\sKepulauan\s", r" Kep. ", regex=True)
    )

    # ===========================================
    # Data Conversion
    # ===========================================
    # Cast the data type of `weekly_working_day` to string
    internship_positions = internship_positions.astype({"weekly_working_day": "str"})

    # ===========================================
    # Feature Engineering
    # ===========================================
    # 1. Feature Construction
    logger.info("Calculating derived acceptance metrics.")
    internship_positions["acceptance_percentage"] = round(
        100
        * internship_positions["approved_quota"]
        / (internship_positions["applicant_count"].add(1)),
        2,
    )

    # 2. Feature Transformation
    # a. Bin `requested_quota` and `approved_quota`
    quota_edges = [1, 2, 10, 50, np.inf]
    quota_labels = ["1 to 2", "3 to 10", "11 to 50", "50+"]

    internship_positions["requested_quota_category"] = pd.cut(
        internship_positions["requested_quota"],
        bins=quota_edges,
        labels=quota_labels,
        include_lowest=True,
    )
    internship_positions["approved_quota_category"] = pd.cut(
        internship_positions["approved_quota"],
        bins=quota_edges,
        labels=quota_labels,
        include_lowest=True,
    )

    # b. Bin Column `applicant_count`
    applicant_edges = [0, 5, 10, 20, 50, np.inf]
    applicant_labels = ["0 to 5", "6 to 10", "11 to 20", "21 to 50", "50+"]

    internship_positions["applicant_count_category"] = pd.cut(
        internship_positions["applicant_count"],
        bins=applicant_edges,
        labels=applicant_labels,
        include_lowest=True,
    )

    # c. Bin Column `acceptance_percentage`
    acceptance_edges = [0, 10, 25, 50, np.inf]
    acceptance_labels = ["0 - 10%", "11 - 25%", "26 - 50%", "50%+"]

    internship_positions["acceptance_percentage_category"] = pd.cut(
        internship_positions["acceptance_percentage"],
        bins=acceptance_edges,
        labels=acceptance_labels,
        include_lowest=True,
    )

    # 3. Feature Encoding
    # One hot encode `education_level`
    ed_level_dummies = (
        internship_positions["education_level"].str.lower().str.get_dummies(sep=", ")
    )
    ed_level_dummies = ed_level_dummies.replace({0: "No", 1: "Yes"}).add_prefix("allows_")
    ed_level_dummies = ed_level_dummies.add_suffix("_level")

    internship_positions = pd.concat([internship_positions, ed_level_dummies], axis=1)

    # 4. Feature Extraction
    all_majors_condition = internship_positions.job_description.str.contains(
        r"semua\sjurusan|jurusan\sapa.*|all\smajors|any\smajor", case=False
    )

    internship_positions["allows_all_majors"] = np.where(all_majors_condition, "Yes", "No")

    # ===========================================
    # Schema Finalization
    # ===========================================
    # Reorganize the position of the columns
    final_cols = [
        "job_id",
        "published_at",
        "job_title",
        "company",
        "regency_city",
        "province",
        "allowed_major",
        "allows_all_majors",
        "allows_bachelor_level",
        "allows_diploma_level",
        "allows_profession_level",
        "job_description",
        "weekly_working_day",
        "requested_quota_category",
        "approved_quota_category",
        "applicant_count_category",
        "acceptance_percentage_category",
        "requested_quota",
        "approved_quota",
        "applicant_count",
        "acceptance_percentage",
    ]

    internship_postings = internship_positions[final_cols]

    logger.info(f"Final dataset merged and shaped with {len(final_cols)} columns.")
    return internship_postings
