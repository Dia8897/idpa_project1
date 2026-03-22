import csv
import json
import os
import re

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


def parse_inline_key_value(text: str):
    """
    Some unlabeled infobox rows are actually written inline as:
      "Key: Value"
    Return (key, value) when the pattern looks reliable, else (None, None).
    """
    if not text or ":" not in text:
        return None, None

    left, right = text.split(":", 1)
    key = clean(left)
    value = clean(right)

    # Heuristics to avoid converting noisy rows (e.g., decorative strings)
    if not key or not value:
        return None, None
    if len(key) > 40:  # likely sentence/noise, not a field name
        return None, None
    if key.lower() in {"show", "hide"}:
        return None, None

    return key, value


def is_noise_unlabeled_value(text: str) -> bool:
    """
    Detect common Wikipedia infobox display/navigation artefacts that are not
    meaningful country facts.
    """
    raw = clean(text).lower()
    t = re.sub(r"\[[^\]]*\]", " ", raw)
    t = re.sub(r"[^a-z\s]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()

    noise_phrases = [
        "show globe",
        "show map",
        "show all",
        "show coordinates",
        "show location",
        "location of",
        "administrative map",
        "territory claimed but not controlled",
        "flag coat of arms",
        "flag emblem",
        "flag national emblem",
        "flag state emblem",
        "flag imperial crest",
        "flag seal",
        "flag royal arms",
    ]
    if any(p in raw or p in t for p in noise_phrases):
        return True

    # Catch variants like: "Flag [a] Coat of arms", "Flag Emblem", etc.
    has_flag = "flag" in t
    has_visual_partner = any(term in t for term in ["emblem", "coat of arms", "seal", "royal arms", "crest"])
    if has_flag and has_visual_partner:
        return True

    return False


def is_visual_only_key(key: str) -> bool:
    """
    Drop purely visual infobox fields that do not represent country facts.
    """
    k = clean(key).lower()
    visual_keys = {
        "flag",
        "coat of arms",
        "national emblem",
        "royal arms",
        "emblem",
        "seal",
        "location",
        "map",
        "image",
        "image map",
        "locator map",
    }
    return k in visual_keys


def is_noise_value(value: str) -> bool:
    """
    Detect visual/decorative map/flag-style values even when they appear
    under labeled keys.
    """
    if not value:
        return False

    raw = clean(value).lower()
    t = re.sub(r"\[[^\]]*\]", " ", raw)
    t = re.sub(r"[^a-z\s]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()

    noisy_markers = [
        "location of",
        "territory claimed but not controlled",
        "show region",
        "show map",
        "show globe",
        "show all",
        "legend",
        "flag emblem",
        "flag seal",
        "flag coat of arms",
        "state emblem",
        "imperial crest",
    ]

    return any(marker in raw or marker in t for marker in noisy_markers)


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

        key = clean(th.get_text(" ", strip=True)) if th else ""
        if not key:
            inline_key, inline_value = parse_inline_key_value(value)
            if inline_key:
                key = inline_key
                value = inline_value
            else:
                # Unlabeled infobox rows are typically decorative/noisy for
                # country comparison, so skip them unless they can be parsed
                # into a reliable inline key/value.
                continue

        # Remove non-semantic visual-only fields.
        if is_visual_only_key(key):
            continue
        if is_noise_value(value):
            continue

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
