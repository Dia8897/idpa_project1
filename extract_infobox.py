import csv
import json
import os

from bs4 import BeautifulSoup
#BeautifulSoup is the key tool here because it lets Python navigate HTML easily.

# Input: raw Wikipedia HTML pages downloaded earlier.
INPUT_DIR = "data/raw_html"
# Output: one JSON file per country containing only the parsed infobox data.
OUTPUT_DIR = "data/infobox_json"
# Log of failures (missing/blocked/no-infobox/etc.).
LOG_PATH = "data/logs/infobox_errors.txt"
# Country list with wiki URLs; used to know which files to parse.
CSV_PATH = "data/countries.csv"

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs("data/logs", exist_ok=True)


def clean(text: str) -> str:
    """Collapse all whitespace inside a text fragment."""
    return " ".join(text.split())


def safe_filename(name: str) -> str:
    name = name.replace("\u2019", "'")
    return (
        name.replace(" ", "_")
        .replace("/", "_")
        .replace(":", "_")
        .replace("'", "")
    )


def extract_infobox_from_html(raw_html: bytes):
    """
    Parse a single HTML document and extract the key/value pairs
    from the main Wikipedia infobox table (class="infobox").

    Returns a dict of {key: value or [values]} or None if no infobox is found.
    """
    soup = BeautifulSoup(raw_html, "lxml")
    table = soup.find("table", class_="infobox")
    if not table:
        return None

    data = {}
    for row in table.find_all("tr"):
        # Only use direct row cells so we don't accidentally grab nested headers.
        th = row.find("th", recursive=False)
        td = row.find("td", recursive=False)

#         th	key (label)
#         td	value

        if not td:
            continue  # skip rows with no value

        value = clean(td.get_text(" ", strip=True))
        if not value:
            continue  # ignore empty values

        key = clean(th.get_text(" ", strip=True)) if th else "info"
        if not key:
            key = "info"

        # merge repeated keys
        #This code ensures that if a field appears multiple times in the infobox,
        # all its values are stored together in a list instead of overwriting each other.
        # ex: "Official languages": ["Arabic", "French"]
        if key in data:
            if isinstance(data[key], list):
                data[key].append(value)
            else:
                data[key] = [data[key], value]
        else:
            data[key] = value

    return data


ok = 0
fail = 0
#both act as counters

with open(LOG_PATH, "w", encoding="utf-8") as log, open(
    CSV_PATH, newline="", encoding="utf-8"
) as csvfile:
    reader = csv.DictReader(csvfile)

    for row in reader:
        country = row["country_name"].strip()
        html_file = os.path.join(INPUT_DIR, safe_filename(country) + ".html")

        if not os.path.exists(html_file):
            fail += 1
            log.write(f"{country}\tMISSING_HTML\t{html_file}\n")
            continue

        try:
            with open(html_file, "rb") as f:
                raw_html = f.read()

            probe = raw_html.decode("utf-8", errors="ignore").lower()
            if "please set a user-agent" in probe or "robot policy" in probe:
                fail += 1
                log.write(f"{country}\tBLOCKED_HTML\n")
                continue

            infobox = extract_infobox_from_html(raw_html)
            if infobox is None:
                fail += 1
                log.write(f"{country}\tNO_INFOBOX\n")
                continue

            # Save the extracted infobox as JSON for the next pipeline step.
            out_path = os.path.join(OUTPUT_DIR, safe_filename(country) + ".json")
            with open(out_path, "w", encoding="utf-8") as out:
                # json.dump() means: Save a Python object into a JSON file.
                json.dump(
                    {"country_name": country, "infobox": infobox},
                    out,
                    ensure_ascii=False,
                    indent=2,
                )
                # ensure_ascii: Without this:"C\u00f4te d'Ivoire", With this: "Côte d'Ivoire"

            ok += 1

        except Exception as e:
            fail += 1
            log.write(f"{country}\tERROR\t{repr(e)}\n")

print(f"Done. Saved {ok} infobox JSON files. Failed: {fail}.")
print(f"See log: {LOG_PATH}")
