import csv
import os
import time
import requests

# Source list of countries and their Wikipedia URLs.
input_file = "data/countries.csv"

# Where we save the raw HTML pages.
output_folder = "data/raw_html"

# Where we log any failures.
log_file = "data/logs/download_errors.txt"

# Ensure output and log directories exist/This prevents crashes from missing directories when saving HTML pages or log files.
os.makedirs(output_folder, exist_ok=True)
os.makedirs("data/logs", exist_ok=True)

# Identify the script to Wikipedia so we don't get blocked.
HEADERS = {
    "User-Agent": "LAU-IDPA-Project/1.0 (contact: your_email@example.com)"
}


def safe_filename(country: str) -> str:
    """Create a simple, Windows-safe filename for a country page."""
    country = country.replace("\u2019", "'")
    return (
        country.replace(" ", "_")
        .replace("/", "_")
        .replace(":", "_")
        .replace("'", "")
        + ".html"
    )


# Open the log and country CSV, then stream-download each page.
with open(log_file, "w", encoding="utf-8") as log:
    #It is like saying:Open the notebook where I will record errors, and open the list of countries I want to process.
    with open(input_file, newline="", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)

        for row in reader:
            #This line prepares Python to read the CSV file row by row.
            country = row["country_name"].strip()   #.strip() removes extra spaces at the beginning and end.
            url = row["wiki_url"].strip()

            print("Downloading:", country)

            try:
                # Fetch the page with our custom User-Agent and a 30s timeout.
                r = requests.get(url, headers=HEADERS, timeout=30)

                if r.status_code != 200:
                    # Non-200 responses are logged and skipped.
                    log.write(f"{country}\t{url}\tHTTP {r.status_code}\n")
                    print("  -> skipped (HTTP", r.status_code, ")")
                    time.sleep(1)
                    continue

                # Detect blocked pages from decoded bytes without trusting response text encoding.
                probe = r.content.decode("utf-8", errors="ignore").lower()
                if "please set a user-agent" in probe or "robot policy" in probe:
                    log.write(f"{country}\t{url}\tBLOCKED(User-Agent)\n")
                    print("  -> blocked (user-agent/robot policy)")
                    time.sleep(2)
                    continue

                # Save the raw HTML bytes for later parsing.
                filepath = os.path.join(output_folder, safe_filename(country))
                with open(filepath, "wb") as f:
                    f.write(r.content)

            except Exception as e:
                # Network or unexpected errors get logged.
                log.write(f"{country}\t{url}\tERROR {repr(e)}\n")
                print("  -> error:", e)

            # Throttle requests to be polite to Wikipedia.
            time.sleep(1)
