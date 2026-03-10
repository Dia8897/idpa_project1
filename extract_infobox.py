import csv
import json
import os

from bs4 import BeautifulSoup

INPUT_DIR = "data/raw_html"
OUTPUT_DIR = "data/infobox_json"
LOG_PATH = "data/logs/infobox_errors.txt"
CSV_PATH = "data/countries.csv"

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs("data/logs", exist_ok=True)


def clean(text: str) -> str:
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
    soup = BeautifulSoup(raw_html, "lxml")
    table = soup.find("table", class_="infobox")
    if not table:
        return None

    data = {}
    for row in table.find_all("tr"):
        # Only use direct row cells to avoid pulling nested headers into a key.
        th = row.find("th", recursive=False)
        td = row.find("td", recursive=False)
        if not td:
            continue

        value = clean(td.get_text(" ", strip=True))
        if not value:
            continue

        key = clean(th.get_text(" ", strip=True)) if th else "info"
        if not key:
            key = "info"

        # merge repeated keys
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

            out_path = os.path.join(OUTPUT_DIR, safe_filename(country) + ".json")
            with open(out_path, "w", encoding="utf-8") as out:
                json.dump(
                    {"country_name": country, "infobox": infobox},
                    out,
                    ensure_ascii=False,
                    indent=2,
                )

            ok += 1

        except Exception as e:
            fail += 1
            log.write(f"{country}\tERROR\t{repr(e)}\n")

print(f"Done. Saved {ok} infobox JSON files. Failed: {fail}.")
print(f"See log: {LOG_PATH}")
