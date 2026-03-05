import os, csv, json
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
    return (
        name.replace(" ", "_")
            .replace("/", "_")
            .replace(":", "_")
            .replace("’", "")
            .replace("'", "")
    )

def extract_infobox_from_html(html: str):
    soup = BeautifulSoup(html, "lxml")
    table = soup.find("table", class_="infobox")
    if not table:
        return None

    data = {}
    for row in table.find_all("tr"):
        th = row.find("th")
        td = row.find("td")
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

with open(LOG_PATH, "w", encoding="utf-8") as log, \
     open(CSV_PATH, newline="", encoding="utf-8") as csvfile:

    reader = csv.DictReader(csvfile)

    for row in reader:
        country = row["country_name"].strip()
        html_file = os.path.join(INPUT_DIR, safe_filename(country) + ".html")

        if not os.path.exists(html_file):
            fail += 1
            log.write(f"{country}\tMISSING_HTML\t{html_file}\n")
            continue

        try:
            with open(html_file, "r", encoding="utf-8") as f:
                html = f.read()

            # ---- IMPROVEMENT: detect blocked/robot-policy pages ----
            if "Please set a user-agent" in html or "robot policy" in html.lower():
                fail += 1
                log.write(f"{country}\tBLOCKED_HTML\n")
                continue

            infobox = extract_infobox_from_html(html)
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
                    indent=2
                )

            ok += 1

        except Exception as e:
            fail += 1
            log.write(f"{country}\tERROR\t{repr(e)}\n")

print(f"Done. Saved {ok} infobox JSON files. Failed: {fail}.")
print(f"See log: {LOG_PATH}")