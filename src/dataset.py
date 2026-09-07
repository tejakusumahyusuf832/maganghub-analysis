"""Module for integrating, engineering, and finalizing the analytical dataset."""

import json
from pathlib import Path
from typing import Annotated

from loguru import logger
import numpy as np
import pandas as pd
import typer

from src.config import EXTERNAL_DATA_DIR, INTERIM_DATA_DIR, RAW_DATA_DIR

app = typer.Typer()


maj_categories = {
    "it_and_computer": r"informatika|komputer|sistem informasi|perangkat lunak|multimedia|jaringan|siber|data|teknologi informasi|piranti lunak|website",
    "engineering": r"teknik(?!\s*(?:informatika|komputer|multimedia))|rekayasa(?!\s*(?:perangkat lunak|internet|komputer))|arsitektur|mesin|elektro|sipil|industri|mekatronika|otomotif|manufaktur|konstruksi|geodesi|geologi|tambang|perkapalan|dirgantara|nautika|listrik|kelistrikan|logam|tekstil|metrologi|instrumentasi|perencanaan|planologi|tata ruang",
    "business": r"manajemen|akuntansi|bisnis|ekonomi|keuangan|administrasi|adminsitrasi|logistik|pemasaran|marketing|pajak|perbankan|retail|niaga|aktiva|kewirausahaan|asuransi",
    "health": r"kedokteran|keperawatan|kebidanan|farmasi|kesehatan|gizi|medik|medis|terapi|radiologi|klinik|apoteker|sanitasi|higiene|hiperkes|optisi|optometri|ortotik|prostetik|darah|audiologi|akupunktur|herbal|rumah sakit|nutrisi",
    "science_and_math": r"matematika|statistik|statistika|biologi|kimia|fisika|sains|aktuaria|geografi|astronomi|lingkungan|bumi|kartografi|penginderaan|oseanografi",
    "agriculture_and_fisheries": r"agribisnis|agribinis|pertanian|peternakan|perikanan|kehutanan|agroteknologi|agroekoteknologi|agro|perkebunan|agronomi|hortikultura|hewan|laut|budidaya|tanaman|pangan|pertanahan",
    "arts_and_media": r"desain|seni|komunikasi|film|televisi|jurnalistik|penyiaran|broadcasting|hubungan masyarakat|humas|fotografi|kriya|tari|musik|karawitan|animasi|media|audio|video|penerbitan",
    "social_and_law": r"hukum|sosiologi|psikologi|sastra|bahasa|kriminologi|kesejahteraan|pemerintahan|politik|hubungan internasional|sejarah|filsafat|antropologi|perpustakaan|kearsipan|arsip|agama|teologi|syariah|islam|kristen|buddha|hindu",
    "education": r"pendidikan|pgsd|pgpaud|tadris|bimbingan|konseling|tarbiyah|guru|kependidikan|penyuluhan",
    "tourism_and_hospitality": r"pariwisata|perhotelan|tata boga|tata rias|tata busana|fashion|kuliner|wisata|mice|travel|hospitaliti|hidang|patiseri",
}


def categorize_job(title: str | None, mapping: dict) -> str:
    """Categorize a job title based on a predefined keyword mapping.

    Args:
        title: The raw job title string to evaluate.
        mapping: A dictionary where keys are category names and values are lists of keywords.

    Returns:
        The matched category name as a string, or "Other" if no keywords match
        or the title is null.
    """
    if pd.isna(title):
        return "Other"

    t = str(title).lower()
    for category, keywords in mapping.items():
        if any(w in t for w in keywords):
            return category

    # Final fallback for anything entirely unmatched
    return "Other"


@app.command()
def make_data(
    internship_data_path: Annotated[
        Path,
        typer.Argument(help="The path of the data containing internship opening records."),
    ] = RAW_DATA_DIR / "internship_positions.parquet",
    adm_division_data_path: Annotated[
        Path,
        typer.Argument(
            help="The path of the standardized data containing administrative divisions."
        ),
    ] = EXTERNAL_DATA_DIR / "administrative_divisions.parquet",
    job_categories_path: Annotated[
        Path,
        typer.Argument(help="The path to the JSON file containing job category mappings."),
    ] = EXTERNAL_DATA_DIR / "job_categories.json",
    output_path: Annotated[
        Path, typer.Argument(help="The path where the output Parquet file will be saved.")
    ] = INTERIM_DATA_DIR / "internship_postings_2.parquet",
    returns_df: bool = False,
) -> pd.DataFrame | None:
    """Integrate and engineer features for the final analytical internship dataset.

    Merge raw internship records with geographic administrative divisions, calculate
    derived metrics, engineer categorical features, and output the structured dataset.

    Args:
        internship_data_path: Path to the raw internship positions Parquet file.
        adm_division_data_path: Path to the administrative divisions Parquet file.
        job_categories_path: Path to the job category mapping JSON file.
        output_path: Path to save the final analytical Parquet file.
        returns_df: If True, return the DataFrame in memory instead of just saving to disk.

    Returns:
        The final pandas DataFrame if `returns_df` is True, otherwise None.
    """
    logger.info("Loading base datasets for integration...")

    # Check the existence of the datasets
    try:
        internship_positions = pd.read_parquet(internship_data_path)
        adm_divisions = pd.read_parquet(adm_division_data_path)
        logger.success("Datasets loaded successfully.")
    except FileNotFoundError:
        logger.error("Cannot find dataset(s). Make sure the data path is correct.")
        logger.error("Aborting dataset generation.")
        return

    # Load the external JSON file to categorize jobs and check its presence
    logger.info(f"Loading job categories mapping from {job_categories_path}.")
    try:
        with open(job_categories_path, "r") as file:
            category_mapping = json.load(file)
    except FileNotFoundError:
        logger.error("Cannot find maping file. Make sure the file path is correct.")
        logger.error("Aborting dataset generation.")
        return

    if not category_mapping:
        logger.error("Job category mapping is empty. Aborting dataset generation.")
        return
    else:
        logger.success("Job category mapping loaded successfully.")

    # ===========================================
    # Data Integration
    # ===========================================
    logger.info("Merging internship data with administrative divisions...")
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

    logger.success("Datasets merged successfully.")

    # ===========================================
    # Data Conversion
    # ===========================================
    # Cast the data type of `weekly_working_day` to string
    internship_positions = internship_positions.astype({"weekly_working_day": "str"})

    # ===========================================
    # Feature Engineering
    # ===========================================
    logger.info("Engineering new features...")

    # 1. Feature Construction
    internship_positions["acceptance_percentage"] = round(
        100
        * internship_positions["approved_quota"]
        / (internship_positions["applicant_count"].add(1)),
        2,
    )

    # 2. Feature Transformation
    # a. Categorize job titles
    internship_positions["job_category"] = internship_positions.job_title.apply(
        lambda title: categorize_job(title, category_mapping)
    )

    # b. Create new Boolean columns
    # Iterate through the `maj_categories` dictionary
    for cat, pattern in maj_categories.items():
        col_name = f"allows_{cat}_majors"

        # Check if any keyword in the pattern exists in the "allowed_major" string
        mask = internship_positions["allowed_major"].str.contains(pattern, case=False, regex=True)
        internship_positions[col_name] = np.where(mask, "Yes", "No")

    # c. Bin `requested_quota` and `approved_quota`
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

    # d. Bin Column `applicant_count`
    applicant_edges = [0, 5, 10, 20, 50, np.inf]
    applicant_labels = ["0 to 5", "6 to 10", "11 to 20", "21 to 50", "50+"]

    internship_positions["applicant_count_category"] = pd.cut(
        internship_positions["applicant_count"],
        bins=applicant_edges,
        labels=applicant_labels,
        include_lowest=True,
    )

    # e. Bin Column `acceptance_percentage`
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

    logger.success("All new features engineered successfully.")

    # ===========================================
    # Schema Finalization
    # ===========================================
    # Reorganize the position of the columns
    final_cols = [
        "job_id",
        "published_at",
        "job_title",
        "job_category",
        "company",
        "organizer_type",
        "regency_city",
        "province",
        "allows_bachelor_level",
        "allows_diploma_level",
        "allows_profession_level",
        "allowed_major",
        "allows_it_and_computer_majors",
        "allows_engineering_majors",
        "allows_business_majors",
        "allows_health_majors",
        "allows_science_and_math_majors",
        "allows_agriculture_and_fisheries_majors",
        "allows_arts_and_media_majors",
        "allows_social_and_law_majors",
        "allows_education_majors",
        "allows_tourism_and_hospitality_majors",
        "allows_all_majors",
        "job_description",
        "interview_type",
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
    internship_postings.to_parquet(output_path, index=False)
    logger.success(f"Successfully saved the final analytical dataset to {output_path}.")

    if returns_df:
        return internship_postings


if __name__ == "__main__":
    app()
