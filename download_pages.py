import csv
import os
import time
import requests

input_file = "data/countries.csv"
output_folder = "data/raw_html"
log_file = "data/logs/download_errors.txt"

os.makedirs(output_folder, exist_ok=True)
os.makedirs("data/logs", exist_ok=True)

HEADERS = {
    "User-Agent": "LAU-IDPA-Project/1.0 (contact: your_email@example.com)"
}

def safe_filename(country: str) -> str:
    # keep it simple + Windows-safe
    return (
        country.replace(" ", "_")
               .replace("/", "_")
               .replace(":", "_")
               .replace("’", "")
               .replace("'", "")
        + ".html"
    )

with open(log_file, "w", encoding="utf-8") as log:
    with open(input_file, newline="", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)

        for row in reader:
            country = row["country_name"].strip()
            url = row["wiki_url"].strip()

            print("Downloading:", country)

            try:
                r = requests.get(url, headers=HEADERS, timeout=30)

                if r.status_code != 200:
                    log.write(f"{country}\t{url}\tHTTP {r.status_code}\n")
                    print("  -> skipped (HTTP", r.status_code, ")")
                    time.sleep(1)
                    continue

                # quick block detection
                if "Please set a user-agent" in r.text or "robot policy" in r.text:
                    log.write(f"{country}\t{url}\tBLOCKED(User-Agent)\n")
                    print("  -> blocked (user-agent/robot policy)")
                    time.sleep(2)
                    continue

                filepath = os.path.join(output_folder, safe_filename(country))
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(r.text)

            except Exception as e:
                log.write(f"{country}\t{url}\tERROR {repr(e)}\n")
                print("  -> error:", e)

            # be nice to Wikipedia
            time.sleep(1)