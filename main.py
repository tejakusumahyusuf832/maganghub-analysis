import json
import re
import time

import pandas as pd
import requests


def scrape_all_keywords():
    keywords = [
        "data scientist",
        "data science",
        "data analyst",
        "data analytics",
        "data analis",
        "analis data",
        "analisis data",
        "sains data",
        "data sains",
        "ilmu data",
    ]

    all_results = []

    for keyword in keywords:
        page = 1
        print(f"\n{'=' * 40}")
        print(f"Starting scrape for keyword: '{keyword}'")
        print(f"{'=' * 40}")

        while True:
            url = f"https://maganghub.kemnaker.go.id/national-batch/vacancy?keyword={keyword}&page={page}"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }

            print(f"  -> Fetching page {page}...")
            response = requests.get(url, headers=headers)
            response.encoding = "utf-8"

            scripts = re.findall(r'__next_f\.push\(\[\d+,\s*(".*?")\]\)', response.text)
            rsc_payload = ""
            for script in scripts:
                try:
                    rsc_payload += json.loads(script)
                except:
                    pass

            if not rsc_payload:
                print("     Could not load page data. Stopping loop.")
                break

            match = re.search(
                r'"initialVacancies":(\{"data":\[.*?\],"links":\{.*?\},"meta":\{.*?\}\})',
                rsc_payload,
            )

            if not match:
                print(f"     No job list found on page {page}. Stopping loop.")
                break

            try:
                data = json.loads(match.group(1))
                vacancies = data.get("data", [])

                if not vacancies:
                    print(f"     No more jobs found on page {page}.")
                    break

                print(f"     Found {len(vacancies)} jobs.")

                def resolve_tag(text_val):
                    if isinstance(text_val, str) and text_val.startswith("$"):
                        tag = text_val.replace("$", "")
                        long_match = re.search(
                            rf"^{tag}:T[0-9a-f]+,(.*?)$", rsc_payload, re.MULTILINE
                        )
                        if long_match:
                            return long_match.group(1).replace("\\n", "\n").strip()
                        short_match = re.search(
                            rf'^{tag}:"(.*?)"$', rsc_payload, re.MULTILINE
                        )
                        if short_match:
                            return short_match.group(1).replace("\\n", "\n").strip()
                    return text_val

                # --- ADDING THE NEW FIELDS HERE ---
                for job in vacancies:
                    raw_desc = job.get("taskDescription", "")
                    for _ in range(3):
                        if isinstance(raw_desc, str) and raw_desc.startswith("$"):
                            raw_desc = resolve_tag(raw_desc)
                        else:
                            break

                    extracted = {
                        "Job ID": job.get("id"),  # We keep this now!
                        "Keyword": keyword,
                        "Job Title": job.get("positionName"),
                        "Company": job.get("organizer", {}).get("name"),
                        "Requested Quota (Ignored)": job.get("quantityNeeded"),
                        "Total Applicants": job.get("totalApplications", 0),
                        "Real Quota": job.get("approvedQuantity", 0),
                        "Education Levels": ", ".join(
                            job.get("educationLevels", [])
                        ).title(),
                        "Working Days/Week": job.get("workingDaysPerWeek"),
                        "Location": job.get("city", {}).get("name"),
                        "Majors Allowed": ", ".join(
                            [p.get("name") for p in job.get("studyPrograms", [])]
                        ),
                        "Published At": job.get("publishedAt"),
                        "Description": raw_desc,
                    }
                    all_results.append(extracted)

                meta = data.get("meta", {})
                last_page = meta.get("lastPage", 1)

                if page >= last_page:
                    print(f"     Reached the final page ({last_page}) for '{keyword}'.")
                    break

                page += 1
                time.sleep(2)

            except Exception as e:
                print(f"     Error parsing page {page}: {e}")
                break

        time.sleep(3)

    if all_results:
        df = pd.DataFrame(all_results)
        total_scraped = len(df)

        # We add the new columns to our deduplication logic
        agg_funcs = {
            "Keyword": lambda x: ", ".join(x.unique()),
            "Job Title": "first",
            "Company": "first",
            "Requested Quota (Ignored)": "first",
            "Total Applicants": "first",
            "Real Quota": "first",
            "Education Levels": "first",
            "Working Days/Week": "first",
            "Location": "first",
            "Majors Allowed": "first",
            "Published At": "first",
            "Description": "first",
        }

        df = df.groupby("Job ID", as_index=False).agg(agg_funcs)

        # We reorder the columns, and we NO LONGER drop the Job ID!
        df = df[
            [
                "Job ID",
                "Keyword",
                "Job Title",
                "Company",
                "Requested Quota (Ignored)",
                "Total Applicants",
                "Real Quota",
                "Education Levels",
                "Working Days/Week",
                "Location",
                "Majors Allowed",
                "Published At",
                "Description",
            ]
        ]

        filename = "data/maganghub_data_master.parquet"
        df.to_parquet(filename)

        print(f"\n{'=' * 40}")
        print("Scraping Complete!")
        print(f"Total rows scraped: {total_scraped}")
        print(
            f"Total unique jobs saved: {len(df)} (Removed {total_scraped - len(df)} duplicates)"
        )
        print(f"File saved successfully as: {filename}")
        print(f"{'=' * 40}\n")
    else:
        print("\nNo data was collected.")


scrape_all_keywords()
