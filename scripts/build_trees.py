"""
Convert cleaned infobox JSON files into rooted, ordered, labeled trees suitable
for TED. Defaults align with project spec:
- Preserves infobox row order as it appears in the source document.
- Values can be stored as a single text leaf OR tokenized into multiple leaves
  (choose via --tokenize {single,tokens}); rationale is exposed via the flag.
- Accepts exactly two input files via --files for pairwise runs, or processes
  an entire folder when no files are specified.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import unicodedata
from pathlib import Path
from typing import Iterable, List

# Default to the cleaned infoboxes.
DEFAULT_INPUT_DIR = Path("data/infobox_json_clean")
DEFAULT_OUTPUT_DIR = Path("data/trees")

# Keep this SMALL and only add mappings when you really need them.
KEY_MAP = {
    "official_language": "official_languages",
    "official_languages": "official_languages",
    "demonym": "demonyms",
    "demonyms": "demonyms",
}

DROP_KEYS = {
    "anthem",
    "motto",
    "demonyms",
    "president",
    "prime_minister",
    "speaker_of_the_parliament",
    "vice_president",
    "deputy_prime_minister",
    "king",
    "queen",
    "governor_general",
    "chancellor",
    "area_code",
    "calling_code",
    "postal_code",
    "internet_tld",
    "cctld",
    "iso_3166_code",
    "date_format",
    "time_zone",
    "currency",
    "currency_code",
    "patron_saint",
    "image_flag",
    "image_coat",
    "flag",
    "coat_of_arms",
    "locator_map",
    "map",
}

HISTORICAL_KEYWORDS = (
    "independ",
    "mandate",
    "kingdom",
    "sultanate",
    "emirate",
    "protectorate",
    "colony",
    "annex",
    "occupation",
    "established",
    "founded",
    "federation",
    "caliphate",
    "dynasty",
    "french_mandate",
    "ottoman",
    "roman",
    "byzantine",
)


def _ascii_fold(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")


def normalize_key(k: str) -> str:
    k = str(k).strip()
    k = k.replace("\u2019", "'")
    k = k.replace("\u00e2\u20ac\u00a2", " ")
    k = k.replace("\u2022", " ")

    # Drop citations and punctuation-heavy separators.
    k = re.sub(r"\[[^\]]*\]", "", k)
    k = k.replace("(", " ").replace(")", " ")
    k = k.replace(":", " ").replace("/", " ")
    k = re.sub(r"\s+", " ", k).strip().lower()

    # Keep semantic category names stable across years.
    k = re.sub(r"\b(19|20)\d{2}\b", "", k)
    k = re.sub(r"\s+", " ", k).strip()

    # Avoid giant synthetic labels from malformed/compound headers.
    if "name in official languages" in k and len(k) > 80:
        k = "official name"

    k = _ascii_fold(k)
    k = k.replace(" ", "_")
    k = re.sub(r"[^a-z0-9_]+", "", k)
    k = re.sub(r"_+", "_", k).strip("_")
    return KEY_MAP.get(k, k)


def should_drop_key(raw_key: str) -> bool:
    key = normalize_key(raw_key)
    if key in DROP_KEYS:
        return True
    return any(token in key for token in HISTORICAL_KEYWORDS)


def normalize_value(v: str) -> str:
    # keep as readable text, just cleanup spacing and obvious decode artifacts
    v = str(v)
    v = v.replace("\u2019", "'")
    v = re.sub(r"\s+", " ", v).strip()
    return v


def tokenize(text: str) -> List[str]:
    # Tokenize on punctuation and whitespace; keeps alphanumerics.
    return re.findall(r"[A-Za-z0-9]+", text)


def make_node(label: str, children=None):
    return {"label": label, "children": children or []}


def add_value_children(parent, value, tokenize_mode: str):
    """
    value can be:
      - string
      - list of strings (repeated keys)

    tokenize_mode:
      - "single": one leaf per value string (structure + content combined)
      - "tokens": one leaf per token to emphasize word-level similarity
    """
    if isinstance(value, list):
        for item in value:
            add_value_children(parent, item, tokenize_mode)
        return

    text = normalize_value(value)
    if not text:
        return

    if tokenize_mode == "tokens":
        # Keep the original value for UI display while storing tokens for TED.
        parent.setdefault("raw_values", []).append(text)
        for t in tokenize(text):
            parent["children"].append(make_node(t))
    else:
        parent["children"].append(make_node(text))


def infobox_to_tree(infobox: dict, tokenize_mode: str):
    root = make_node("country", [])

    # Preserve original row order: dict preserves insertion order from JSON load.
    for raw_key, raw_value in infobox.items():
        key = normalize_key(raw_key)
        if not key:
            continue
        if should_drop_key(key):
            continue

        key_node = make_node(key, [])
        add_value_children(key_node, raw_value, tokenize_mode)

        if key_node["children"]:
            root["children"].append(key_node)

    return root


def process_file(in_path: Path, out_dir: Path, tokenize_mode: str) -> None:
    obj = json.loads(in_path.read_text(encoding="utf-8"))
    country = obj.get("country_name", in_path.stem)
    infobox = obj.get("infobox", {})

    tree = infobox_to_tree(infobox, tokenize_mode)

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / in_path.name
    out_path.write_text(
        json.dumps({"country_name": country, "tree": tree}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def collect_inputs(src: Path, files: Iterable[Path]) -> List[Path]:
    if files:
        out = []
        for f in files:
            p = Path(f)
            if not p.is_absolute():
                p = src / p
            out.append(p)
        return out

    # Glob returns paths rooted at src; make them absolute to avoid double-joining later.
    return [p.resolve() for p in sorted(src.glob("*.json"))]


def main():
    parser = argparse.ArgumentParser(description="Build tree representations from infobox JSON.")
    parser.add_argument("--src", type=Path, default=DEFAULT_INPUT_DIR, help="Source folder of infobox JSON.")
    parser.add_argument("--dst", type=Path, default=DEFAULT_OUTPUT_DIR, help="Destination folder for tree JSON.")
    parser.add_argument(
        "--tokenize",
        choices=["single", "tokens"],
        default="single",
        help="Represent values as one leaf ('single') or one leaf per token ('tokens').",
    )
    parser.add_argument(
        "--files",
        nargs="*",
        default=[],
        help="Explicit infobox JSON files to process (path or filename). Use two to match the assignment.",
    )
    args = parser.parse_args()

    inputs = collect_inputs(args.src, args.files)
    if not inputs:
        raise SystemExit("No input files found.")

    for path in inputs:
        if not Path(path).exists():
            raise SystemExit(f"Missing input file: {path}")
        process_file(Path(path), args.dst, args.tokenize)

    print(f"Built {len(inputs)} trees in {args.dst}")


if __name__ == "__main__":
    main()
