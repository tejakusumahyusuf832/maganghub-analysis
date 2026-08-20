import json
import re
import time

import pandas as pd
import requests


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


def scrape_all_vacancies():
    all_results = []
    page = 1

    print(f"\n{'=' * 50}")
    print("Starting massive scrape for ALL Maganghub internships...")
    print(f"{'=' * 50}")

    while True:
        url = f"https://maganghub.kemnaker.go.id/national-batch/vacancy?page={page}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

        print(f"-> Fetching page {page}...")

        try:
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
        except requests.RequestException as e:
            print(f"   Network error on page {page}: {e}")
            break

        response.encoding = "utf-8"

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

            # --- THE FIX: Bulletproof Data Extraction ---
            for job in vacancies:
                raw_desc = job.get("taskDescription", "")

                for _ in range(3):
                    if isinstance(raw_desc, str) and raw_desc.startswith("$"):
                        raw_desc = resolve_tag(raw_desc, rsc_payload)
                    else:
                        break

                # We safely handle `null` API responses by falling back to empty dicts/lists
                organizer = job.get("organizer") or {}
                city = job.get("city") or {}
                education = job.get("educationLevels") or []
                study_programs = job.get("studyPrograms") or []

                extracted = {
                    "Job ID": job.get("id"),
                    "Job Title": job.get("positionName"),
                    "Company": organizer.get("name", "Unknown Company"),
                    "Requested Quota": job.get("quantityNeeded") or 0,
                    "Real Quota": job.get("approvedQuantity") or 0,
                    "Total Applicants": job.get("totalApplications") or 0,
                    "Education Levels": ", ".join(education).title(),
                    "Working Days/Week": job.get("workingDaysPerWeek"),
                    "Location": city.get("name", "Unknown Location"),
                    "Majors Allowed": ", ".join(
                        [
                            p.get("name", "")
                            for p in study_programs
                            if isinstance(p, dict)
                        ]
                    ),
                    "Published At": job.get("publishedAt"),
                    "Description": raw_desc,
                }
                all_results.append(extracted)

            meta = data.get("meta", {})
            last_page = meta.get("lastPage", 1)

            if page >= last_page:
                print(f"   Reached the final page ({last_page}). Scraping complete!")
                break

            page += 1
            time.sleep(2)

        except Exception as e:  # noqa: BLE001
            print(f"   Error parsing page {page}: {e}")
            break

    if all_results:
        df = pd.DataFrame(all_results)
        total_scraped = len(df)
        df = df.drop_duplicates(subset=["Job ID"])

        filename = "maganghub_all_internships_master.parquet"
        df.to_parquet(filename, index=False)

        print(f"\n{'=' * 50}")
        print("Massive Scrape Complete!")
        print(f"Total rows scraped: {total_scraped}")
        print(f"Total unique jobs saved: {len(df)}")
        print(f"File saved successfully as: {filename}")
        print(f"{'=' * 50}\n")
    else:
        print("\nNo data was collected.")


if __name__ == "__main__":
    scrape_all_vacancies()
